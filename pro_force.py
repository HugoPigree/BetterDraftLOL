#!/usr/bin/env python3
"""Pro winrates by champion/role from Oracle's Elixir player rows."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import pandas as pd

import build_training_dataset as btd
from build_duo_dataset import load_player_rows

logger = logging.getLogger(__name__)

MIN_GAMES_PRO_FORCE = 10
MIN_GAMES_EXCLUSION = 30  # exclusion dure du pool bot (ajuster si trop restrictif)
PRO_VOLUME_WEIGHT = 0.55
PRO_WINRATE_WEIGHT = 0.45
PRO_WINRATE_PRIOR_RATIO = 0.15
PRO_OFF_ROLE_MIN_RATIO = 0.20
DEFAULT_ORACLE_CSV = Path("data/2026_LoL_esports_match_data_from_OraclesElixir.csv")

ORACLE_POSITION_TO_ROLE = {
    "top": "TOP",
    "jng": "JUNGLE",
    "mid": "MIDDLE",
    "bot": "BOTTOM",
    "sup": "UTILITY",
}

_pro_winrate_lookup: dict[tuple[str, str], tuple[float, int]] | None = None
_pro_oracle_path: Path | None = None
_role_pro_volume_cache: dict[str, dict[str, float]] = {}
_champion_pro_roles_cache: dict[str, dict[str, int]] = {}


def reset_pro_force_state() -> None:
    global _pro_winrate_lookup, _pro_oracle_path, _role_pro_volume_cache, _champion_pro_roles_cache
    _pro_winrate_lookup = None
    _pro_oracle_path = None
    _role_pro_volume_cache = {}
    _champion_pro_roles_cache = {}


def build_pro_winrate_lookup(
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
) -> dict[tuple[str, str], tuple[float, int]]:
    """Aggregate (champion, role) -> (winrate, games) from Oracle player lines."""
    if not oracle_csv.exists():
        logger.warning("Oracle CSV introuvable pour winrates pro: %s", oracle_csv)
        return {}

    players = load_player_rows(oracle_csv)
    if players.empty:
        return {}

    players = players.copy()
    players["role"] = players["position"].map(ORACLE_POSITION_TO_ROLE)
    players = players.dropna(subset=["role", "champion"])
    players["champion"] = players["champion"].astype(str).str.strip()
    players["result"] = players["result"].astype(int)

    grouped = (
        players.groupby(["champion", "role"], as_index=False)
        .agg(games=("result", "count"), wins=("result", "sum"))
    )
    grouped["winrate"] = grouped["wins"] / grouped["games"]

    lookup: dict[tuple[str, str], tuple[float, int]] = {}
    for _, row in grouped.iterrows():
        key = (str(row["champion"]), str(row["role"]))
        lookup[key] = (float(row["winrate"]), int(row["games"]))

    logger.info("Winrates pro chargés: %d paires champion/rôle", len(lookup))
    return lookup


def get_pro_winrate_lookup(oracle_csv: Path = DEFAULT_ORACLE_CSV) -> dict[tuple[str, str], tuple[float, int]]:
    global _pro_winrate_lookup, _pro_oracle_path
    if _pro_winrate_lookup is None or _pro_oracle_path != oracle_csv:
        _pro_winrate_lookup = build_pro_winrate_lookup(oracle_csv)
        _pro_oracle_path = oracle_csv
    return _pro_winrate_lookup


def resolve_pro_champion_name(
    champion_name: str,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
) -> str | None:
    return btd.resolve_champion_name(champion_name, champion_features, lookup_by_norm)


def compute_pro_winrate_by_champion(
    champion: str,
    role: str,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
    min_games: int = MIN_GAMES_PRO_FORCE,
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
) -> tuple[float, int] | None:
    """Winrate pro pour un champion/rôle, ou None si données insuffisantes."""
    role_upper = role.strip().upper()
    if role_upper not in ORACLE_POSITION_TO_ROLE.values():
        return None

    resolved = resolve_pro_champion_name(champion, champion_features, lookup_by_norm)
    if resolved is None:
        return None

    pro_lookup = get_pro_winrate_lookup(oracle_csv)
    entry = pro_lookup.get((resolved, role_upper))
    if entry is None:
        entry = pro_lookup.get((champion.strip(), role_upper))
    if entry is None:
        return None

    winrate, games = entry
    if games < min_games:
        return None
    return winrate, games


def _normalize_role(role: str) -> str:
    return role.strip().upper()


def get_champion_pro_games_by_role(
    champion: str,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
) -> dict[str, int]:
    """Games pro par rôle pour un champion (rôles avec >= MIN_GAMES)."""
    resolved = resolve_pro_champion_name(champion, champion_features, lookup_by_norm)
    if resolved is None:
        return {}

    cached = _champion_pro_roles_cache.get(resolved)
    if cached is not None:
        return cached

    pro_lookup = get_pro_winrate_lookup(oracle_csv)
    by_role: dict[str, int] = {}
    for (name, role), (_, games) in pro_lookup.items():
        if name != resolved or games < MIN_GAMES_PRO_FORCE:
            continue
        by_role[role] = games

    _champion_pro_roles_cache[resolved] = by_role
    return by_role


def get_pro_primary_role(
    champion: str,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
) -> tuple[str, int] | None:
    """Rôle pro principal (plus de games Oracle)."""
    by_role = get_champion_pro_games_by_role(
        champion, champion_features, lookup_by_norm, oracle_csv
    )
    if not by_role:
        return None
    role = max(by_role, key=by_role.get)  # type: ignore[arg-type]
    return role, by_role[role]


def pro_role_fitness(
    champion: str,
    role: str,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
) -> float:
    """Adéquation rôle pro : 1.0 si rôle principal, sinon ratio games vs rôle principal."""
    role = _normalize_role(role)
    by_role = get_champion_pro_games_by_role(
        champion, champion_features, lookup_by_norm, oracle_csv
    )
    if not by_role or role not in by_role:
        return 0.0

    role_games = by_role[role]
    primary_role = max(by_role, key=by_role.get)  # type: ignore[arg-type]
    if role == primary_role:
        return 1.0

    max_games = by_role[primary_role]
    if max_games <= 0:
        return 0.0
    return role_games / max_games


def is_pro_viable_on_role(
    champion: str,
    role: str,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
    min_fitness: float = PRO_OFF_ROLE_MIN_RATIO,
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
) -> bool:
    """Filtre les flex off-meta (ex. Taliyah jungle quand mid domine)."""
    fitness = pro_role_fitness(
        champion, role, champion_features, lookup_by_norm, oracle_csv
    )
    return fitness >= min_fitness


def get_role_pro_volume_context(
    role: str,
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
) -> dict[str, float]:
    """Volume max / médian par rôle pour relativiser winrates pro."""
    role = _normalize_role(role)
    cached = _role_pro_volume_cache.get(role)
    if cached is not None:
        return cached

    lookup = get_pro_winrate_lookup(oracle_csv)
    games_counts = [
        games
        for (_, slot_role), (_, games) in lookup.items()
        if slot_role == role and games >= MIN_GAMES_PRO_FORCE
    ]
    if not games_counts:
        context = {"max_games": 1.0, "median_games": 1.0}
    else:
        games_counts.sort()
        context = {
            "max_games": float(games_counts[-1]),
            "median_games": float(games_counts[len(games_counts) // 2]),
        }

    _role_pro_volume_cache[role] = context
    return context


def shrink_pro_winrate(
    winrate: float,
    games: int,
    role: str,
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
) -> float:
    context = get_role_pro_volume_context(role, oracle_csv)
    prior_games = max(30.0, context["max_games"] * PRO_WINRATE_PRIOR_RATIO)
    return (winrate * games + 0.5 * prior_games) / (games + prior_games)


def pro_volume_norm(
    games: int,
    role: str,
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
) -> float:
    context = get_role_pro_volume_context(role, oracle_csv)
    max_games = context["max_games"]
    if max_games <= 0:
        return 0.0
    return math.log1p(games) / math.log1p(max_games)


def pro_meta_score(
    champion: str,
    role: str,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
) -> tuple[float, int, float, float, str] | None:
    """Score meta pro : volume + winrate lissé, pénalisé si off-role."""
    role = _normalize_role(role)
    entry = compute_pro_winrate_by_champion(
        champion, role, champion_features, lookup_by_norm, oracle_csv=oracle_csv
    )
    if entry is None:
        return None

    winrate, games = entry
    resolved = resolve_pro_champion_name(champion, champion_features, lookup_by_norm)
    name = resolved or champion.strip()

    volume_norm = pro_volume_norm(games, role, oracle_csv)
    shrunk_wr = shrink_pro_winrate(winrate, games, role, oracle_csv)
    fitness = pro_role_fitness(
        name, role, champion_features, lookup_by_norm, oracle_csv
    )
    raw_meta = PRO_VOLUME_WEIGHT * volume_norm + PRO_WINRATE_WEIGHT * shrunk_wr
    meta_score = raw_meta * (0.35 + 0.65 * fitness)

    return (meta_score, games, shrunk_wr, fitness, name)


def rank_pro_champions_for_role(
    champions: list[str],
    role: str,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
    *,
    min_fitness: float = PRO_OFF_ROLE_MIN_RATIO,
    min_games: int = MIN_GAMES_PRO_FORCE,
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
) -> list[tuple[float, int, float, float, str]]:
    ranked: list[tuple[float, int, float, float, str]] = []
    for champion in champions:
        scored = pro_meta_score(
            champion, role, champion_features, lookup_by_norm, oracle_csv
        )
        if scored is None:
            continue
        if scored[1] < min_games:
            continue
        if scored[3] < min_fitness:
            continue
        ranked.append(scored)
    ranked.sort(key=lambda item: (-item[0], -item[1], item[4].casefold()))
    return ranked


def get_meta_pool_for_role(
    role: str,
    patch: str,
    top_n: int = 15,
    *,
    candidates: list[str] | None = None,
    champion_features: dict[str, dict[str, Any]] | None = None,
    lookup_by_norm: dict[str, str] | None = None,
    min_fitness: float = PRO_OFF_ROLE_MIN_RATIO,
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
) -> list[str]:
    """Pool meta pro pour le bot : exclusion dure < MIN_GAMES_EXCLUSION, tri par meta_score.

    Ne complète jamais avec des champions sous le seuil, même si moins de top_n disponibles.
    ``patch`` est réservé pour un filtrage futur par patch Oracle.
    """
    del patch  # réservé pour filtrage patch futur
    role = _normalize_role(role)
    top_n = max(1, top_n)

    if champion_features is None or lookup_by_norm is None:
        from predict_draft import get_meraki_context

        champion_features, _, lookup_by_norm = get_meraki_context()

    pool_candidates = candidates if candidates is not None else []
    if not pool_candidates:
        pro_lookup = get_pro_winrate_lookup(oracle_csv)
        pool_candidates = sorted(
            {
                champion
                for (champion, slot_role), (_, games) in pro_lookup.items()
                if slot_role == role and games >= MIN_GAMES_EXCLUSION
            },
            key=str.casefold,
        )

    ranked: list[tuple[float, int, float, float, str]] = []
    for champion in pool_candidates:
        entry = compute_pro_winrate_by_champion(
            champion,
            role,
            champion_features,
            lookup_by_norm,
            min_games=MIN_GAMES_EXCLUSION,
            oracle_csv=oracle_csv,
        )
        if entry is None:
            continue

        scored = pro_meta_score(
            champion, role, champion_features, lookup_by_norm, oracle_csv
        )
        if scored is None or scored[1] < MIN_GAMES_EXCLUSION:
            continue
        if scored[3] < min_fitness:
            continue
        ranked.append(scored)

    ranked.sort(key=lambda item: (-item[0], -item[1], item[4].casefold()))
    selected = [name for _, _, _, _, name in ranked[:top_n]]

    logger.debug(
        "Meta pool %s: %d candidats (>=%d games), retourne top_%d=%s",
        role,
        len(ranked),
        MIN_GAMES_EXCLUSION,
        top_n,
        selected,
    )
    return selected
