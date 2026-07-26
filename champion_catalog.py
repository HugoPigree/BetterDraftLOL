"""Catalogue unifié Meraki + Data Dragon + rôles pro Oracle."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd

from data_refresh.constants import (
    DEFAULT_ORACLE_CSV,
    DDRAGON_CACHE_PATH,
    DDRAGON_META_PATH,
    MERAKI_CACHE_PATH,
    MERAKI_URL,
)
from data_refresh.ddragon import load_ddragon_champions, refresh_ddragon_champions

logger = logging.getLogger(__name__)

ATTRIBUTE_COLUMNS = ["damage", "toughness", "control", "mobility", "utility"]

ORACLE_POSITION_MAP = {
    "top": "TOP",
    "jng": "JUNGLE",
    "mid": "MIDDLE",
    "bot": "BOTTOM",
    "sup": "SUPPORT",
}

TAG_DEFAULT_POSITIONS: dict[str, list[str]] = {
    "Marksman": ["BOTTOM"],
    "Support": ["SUPPORT"],
    "Mage": ["MIDDLE"],
    "Assassin": ["MIDDLE", "JUNGLE"],
    "Fighter": ["TOP", "JUNGLE"],
    "Tank": ["TOP", "JUNGLE", "SUPPORT"],
}

DDTAG_TO_MERAKI_ROLES: dict[str, list[str]] = {
    "Assassin": ["ASSASSIN"],
    "Fighter": ["FIGHTER", "SKIRMISHER"],
    "Tank": ["VANGUARD", "WARDEN"],
    "Mage": ["BURST", "BATTLEMAGE"],
    "Marksman": ["MARKSMAN"],
    "Support": ["ENCHANTER", "CATCHER"],
}


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _scale_1_10_to_1_3(value: float) -> int:
    return max(1, min(3, round(value / 3.5) or 1))


def ddragon_tags_to_roles(tags: list[str]) -> list[str]:
    roles: list[str] = []
    for tag in tags:
        for role in DDTAG_TO_MERAKI_ROLES.get(tag, []):
            if role not in roles:
                roles.append(role)
    if not roles:
        roles.append("SPECIALIST")
    return roles


def infer_positions_from_tags(tags: list[str]) -> list[str]:
    positions: list[str] = []
    for tag in tags:
        for position in TAG_DEFAULT_POSITIONS.get(tag, []):
            if position not in positions:
                positions.append(position)
    return positions or ["MIDDLE"]


def synthesize_attribute_ratings(dd_champion: dict[str, Any]) -> dict[str, int | float]:
    info = dd_champion.get("info") or {}
    tags = dd_champion.get("tags") or []
    stats = dd_champion.get("stats") or {}

    attack = float(info.get("attack", 5))
    magic = float(info.get("magic", 5))
    defense = float(info.get("defense", 5))
    difficulty = float(info.get("difficulty", 5))
    movespeed = float(stats.get("movespeed", 340))

    damage = _scale_1_10_to_1_3((attack + magic) / 2)
    toughness = _scale_1_10_to_1_3(defense)
    control = 2 if "Mage" in tags or "Tank" in tags else 1
    if "Support" in tags:
        control = max(control, 2)
    mobility = 3 if "Assassin" in tags else (2 if movespeed >= 345 else 1)
    utility = 3 if "Support" in tags else (2 if "Tank" in tags else 1)

    return {
        "damage": damage,
        "toughness": toughness,
        "control": control,
        "mobility": mobility,
        "utility": utility,
        "abilityReliance": int(min(90, max(35, 35 + magic * 5))),
        "difficulty": _scale_1_10_to_1_3(difficulty),
    }


_oracle_positions_cache: dict[str, list[str]] | None = None
_unified_champions_cache: dict[str, Any] | None = None


def reset_champion_catalog_cache() -> None:
    global _oracle_positions_cache, _unified_champions_cache
    _oracle_positions_cache = None
    _unified_champions_cache = None


def infer_oracle_positions(
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
    *,
    min_games: int = 1,
) -> dict[str, list[str]]:
    """Infère les lanes pro depuis le lookup Oracle déjà agrégé (pas de relecture CSV)."""
    from draft_profiling import profile_step, record_data_load
    from pro_force import get_pro_winrate_lookup

    global _oracle_positions_cache
    if _oracle_positions_cache is not None:
        record_data_load("oracle_csv_catalog_positions", hit=True)
        return _oracle_positions_cache

    with profile_step("infer_oracle_positions_from_lookup"):
        lookup = get_pro_winrate_lookup(oracle_csv)
        pro_to_meraki = {
            "TOP": "TOP",
            "JUNGLE": "JUNGLE",
            "MIDDLE": "MIDDLE",
            "BOTTOM": "BOTTOM",
            "UTILITY": "SUPPORT",
        }
        by_champion: dict[str, list[tuple[str, int]]] = {}
        for (champion, role), (_winrate, games) in lookup.items():
            if games < min_games:
                continue
            meraki_role = pro_to_meraki.get(role.upper())
            if not meraki_role:
                continue
            by_champion.setdefault(champion, []).append((meraki_role, games))

        _oracle_positions_cache = {
            champion: [
                position
                for position, _games in sorted(entries, key=lambda item: item[1], reverse=True)
            ]
            for champion, entries in by_champion.items()
        }

    record_data_load(
        "oracle_csv_catalog_positions",
        hit=False,
        detail="derived_from_pro_winrate_lookup",
    )
    return _oracle_positions_cache


def _meraki_match_keys(meraki: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for key, payload in meraki.items():
        keys.add(normalize_name(key))
        keys.add(normalize_name(str(payload.get("name", key))))
        keys.add(normalize_name(str(payload.get("key", key))))
    return keys


def _is_meraki_covered(dd_entry: dict[str, Any], meraki_keys: set[str]) -> bool:
    candidates = [
        str(dd_entry.get("id", "")),
        str(dd_entry.get("name", "")),
        str(dd_entry.get("key", "")),
    ]
    return any(normalize_name(candidate) in meraki_keys for candidate in candidates if candidate)


def synthesize_meraki_profile(
    dd_entry: dict[str, Any],
    *,
    positions: list[str],
    ddragon_version: str,
) -> dict[str, Any]:
    champion_id = str(dd_entry.get("id") or dd_entry.get("name"))
    name = str(dd_entry.get("name") or champion_id)
    tags = list(dd_entry.get("tags") or [])
    attack_type = "MELEE" if "Range" not in str(dd_entry.get("stats", {})) else "RANGED"
    stats = dd_entry.get("stats") or {}
    if float(stats.get("attackrange", 125)) >= 300:
        attack_type = "RANGED"

    return {
        "id": int(dd_entry.get("key", 0) or 0),
        "key": champion_id,
        "name": name,
        "title": dd_entry.get("title", ""),
        "icon": f"https://ddragon.leagueoflegends.com/cdn/{ddragon_version}/img/champion/{champion_id}.png",
        "attackType": attack_type,
        "adaptiveType": "MAGIC_DAMAGE" if "Mage" in tags else "PHYSICAL_DAMAGE",
        "positions": positions,
        "roles": ddragon_tags_to_roles(tags),
        "attributeRatings": synthesize_attribute_ratings(dd_entry),
        "profileSource": "estimated",
        "profileSources": ["ddragon", "oracle" if positions else "ddragon_tags"],
    }


def merge_champion_catalog(
    meraki: dict[str, Any],
    ddragon: dict[str, Any],
    oracle_positions: dict[str, list[str]],
    *,
    ddragon_version: str = "latest",
) -> tuple[dict[str, Any], list[str]]:
    """Fusionne Meraki (prioritaire) avec profils estimés Data Dragon."""
    merged = dict(meraki)
    meraki_keys = _meraki_match_keys(meraki)
    estimated_names: list[str] = []

    for dd_entry in ddragon.values():
        if _is_meraki_covered(dd_entry, meraki_keys):
            continue

        champion_id = str(dd_entry.get("id") or dd_entry.get("name"))
        name = str(dd_entry.get("name") or champion_id)
        tags = list(dd_entry.get("tags") or [])

        positions = oracle_positions.get(name) or oracle_positions.get(champion_id)
        if not positions:
            positions = infer_positions_from_tags(tags)

        profile = synthesize_meraki_profile(
            dd_entry,
            positions=positions,
            ddragon_version=ddragon_version,
        )
        merged[champion_id] = profile
        estimated_names.append(name)
        logger.info(
            "Profil estimé ajouté: %s (positions=%s, roles=%s)",
            name,
            positions,
            profile["roles"],
        )

    return merged, sorted(estimated_names)


def load_meraki_champions(
    url: str = MERAKI_URL,
    cache_path: Path = MERAKI_CACHE_PATH,
) -> dict[str, Any]:
    """Charge Meraki depuis le cache local (sans fusion)."""
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    import requests

    response = requests.get(url, timeout=60)
    response.raise_for_status()
    champions = response.json()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(champions, indent=2), encoding="utf-8")
    return champions


def load_unified_champions(
    *,
    meraki_cache: Path = MERAKI_CACHE_PATH,
    ddragon_cache: Path = DDRAGON_CACHE_PATH,
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
    ensure_ddragon: bool = True,
) -> dict[str, Any]:
    """Catalogue complet : Meraki + nouveaux champions Data Dragon + rôles Oracle."""
    global _unified_champions_cache
    if _unified_champions_cache is not None:
        return _unified_champions_cache

    from draft_profiling import profile_step

    with profile_step("load_unified_champions"):
        meraki = load_meraki_champions(MERAKI_URL, meraki_cache)

        if ensure_ddragon and not ddragon_cache.exists():
            refresh_ddragon_champions(ddragon_cache)

        ddragon = load_ddragon_champions(ddragon_cache) if ddragon_cache.exists() else {}
        ddragon_version = "latest"
        if DDRAGON_META_PATH.exists():
            meta = json.loads(DDRAGON_META_PATH.read_text(encoding="utf-8"))
            ddragon_version = str(meta.get("version") or ddragon_version)

        oracle_positions = infer_oracle_positions(oracle_csv)
        merged, _estimated = merge_champion_catalog(
            meraki,
            ddragon,
            oracle_positions,
            ddragon_version=ddragon_version,
        )
        _unified_champions_cache = merged
        return merged


def list_estimated_champion_names(champions: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key, payload in champions.items():
        if payload.get("profileSource") == "estimated":
            names.append(str(payload.get("name", key)))
    return sorted(names)


def build_api_position_catalog(champions: dict[str, Any]) -> dict[str, list[str]]:
    """Positions par nom affiché, lanes API (SUPPORT → UTILITY)."""
    position_map = {
        "TOP": "TOP",
        "JUNGLE": "JUNGLE",
        "MIDDLE": "MIDDLE",
        "BOTTOM": "BOTTOM",
        "SUPPORT": "UTILITY",
        "UTILITY": "UTILITY",
    }
    catalog: dict[str, list[str]] = {}

    for key, payload in champions.items():
        name = str(payload.get("name", key)).strip()
        if not name:
            continue

        positions: list[str] = []
        for position in payload.get("positions", []):
            mapped = position_map.get(str(position).upper(), str(position).upper())
            if mapped not in positions:
                positions.append(mapped)

        catalog[name] = positions

    return catalog
