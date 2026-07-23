#!/usr/bin/env python3
"""Pro winrates by champion/role from Oracle's Elixir player rows."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
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
PRESENCE_SCORE_WEIGHT = 0.15  # score_final = meta_score + weight * presence_score
DEFAULT_ORACLE_CSV = Path("data/2026_LoL_esports_match_data_from_OraclesElixir.csv")
DEFAULT_META_TIERLIST_CSV = Path("data/meta_tierlist.csv")
ROLES_ORDER = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]

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
_presence_lookup: dict[tuple[str, str], float] | None = None
_presence_csv_path: Path | None = None


def reset_pro_force_state() -> None:
    global _pro_winrate_lookup, _pro_oracle_path, _role_pro_volume_cache
    global _champion_pro_roles_cache, _presence_lookup, _presence_csv_path
    _pro_winrate_lookup = None
    _pro_oracle_path = None
    _role_pro_volume_cache = {}
    _champion_pro_roles_cache = {}
    _presence_lookup = None
    _presence_csv_path = None


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


def load_presence_lookup(
    tierlist_csv: Path = DEFAULT_META_TIERLIST_CSV,
) -> dict[tuple[str, str], float]:
    """Charge presence_score (pick_rate + ban_rate) depuis meta_tierlist.csv."""
    global _presence_lookup, _presence_csv_path
    if _presence_csv_path == tierlist_csv and _presence_lookup is not None:
        return _presence_lookup

    if not tierlist_csv.exists():
        logger.warning(
            "meta_tierlist.csv introuvable (%s) — presence_score=0 pour le tri pool.",
            tierlist_csv,
        )
        _presence_lookup = {}
        _presence_csv_path = tierlist_csv
        return _presence_lookup

    df = pd.read_csv(tierlist_csv)
    lookup: dict[tuple[str, str], float] = {}
    for _, row in df.iterrows():
        champion = str(row["champion"]).strip()
        role = _normalize_role(str(row["role"]))
        lookup[(champion, role)] = float(row["presence_score"])
    _presence_lookup = lookup
    _presence_csv_path = tierlist_csv
    logger.info("Presence lookup charge: %d entrees depuis %s", len(lookup), tierlist_csv)
    return lookup


def get_presence_score(
    champion: str,
    role: str,
    tierlist_csv: Path = DEFAULT_META_TIERLIST_CSV,
) -> float:
    role = _normalize_role(role)
    lookup = load_presence_lookup(tierlist_csv)
    return lookup.get((champion.strip(), role), 0.0)


def compute_final_meta_score(
    meta_score: float,
    presence_score: float,
    *,
    presence_weight: float = PRESENCE_SCORE_WEIGHT,
) -> float:
    return meta_score + presence_weight * presence_score


@dataclass(frozen=True)
class MetaPoolEntry:
    name: str
    meta_score: float
    presence_score: float
    final_score: float
    games: int
    fitness: float


def _rank_meta_pool_for_role(
    role: str,
    patch: str,
    *,
    candidates: list[str] | None = None,
    champion_features: dict[str, dict[str, Any]] | None = None,
    lookup_by_norm: dict[str, str] | None = None,
    min_fitness: float = PRO_OFF_ROLE_MIN_RATIO,
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
    tierlist_csv: Path = DEFAULT_META_TIERLIST_CSV,
    apply_presence_bonus: bool = True,
    presence_weight: float = PRESENCE_SCORE_WEIGHT,
) -> list[MetaPoolEntry]:
    """Classe les candidats apres filtre dur MIN_GAMES_EXCLUSION."""
    del patch
    role = _normalize_role(role)

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

    presence_lookup = load_presence_lookup(tierlist_csv) if apply_presence_bonus else {}
    ranked: list[MetaPoolEntry] = []

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

        meta_score, games, _, fitness, name = scored
        presence = presence_lookup.get((name, role), 0.0) if apply_presence_bonus else 0.0
        final_score = (
            compute_final_meta_score(meta_score, presence, presence_weight=presence_weight)
            if apply_presence_bonus
            else meta_score
        )
        ranked.append(
            MetaPoolEntry(
                name=name,
                meta_score=meta_score,
                presence_score=presence,
                final_score=final_score,
                games=games,
                fitness=fitness,
            )
        )

    ranked.sort(
        key=lambda item: (-item.final_score, -item.games, item.name.casefold())
    )
    return ranked


def print_meta_pool_comparison(
    patch: str = "16.13",
    top_n: int = 15,
    *,
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
    tierlist_csv: Path = DEFAULT_META_TIERLIST_CSV,
    presence_weight: float = PRESENCE_SCORE_WEIGHT,
) -> None:
    """Compare top-N pool par role : meta_score seul vs meta_score + presence."""
    from predict_draft import get_meraki_context

    get_meraki_context()
    print("\n" + "=" * 88)
    print(
        f"COMPARAISON POOL TOP-{top_n} — meta_score seul vs "
        f"meta_score + {presence_weight} x presence_score"
    )
    print(f"(filtre dur >= {MIN_GAMES_EXCLUSION} games inchange)")
    print("=" * 88)

    for role in ROLES_ORDER:
        before = _rank_meta_pool_for_role(
            role,
            patch,
            apply_presence_bonus=False,
            oracle_csv=oracle_csv,
            tierlist_csv=tierlist_csv,
        )[:top_n]
        after = _rank_meta_pool_for_role(
            role,
            patch,
            apply_presence_bonus=True,
            oracle_csv=oracle_csv,
            tierlist_csv=tierlist_csv,
            presence_weight=presence_weight,
        )[:top_n]

        before_names = {entry.name for entry in before}
        after_names = {entry.name for entry in after}
        only_before = sorted(before_names - after_names, key=str.casefold)
        only_after = sorted(after_names - before_names, key=str.casefold)

        print(f"\n--- {role} ---")
        print(f"{'#':>2}  {'meta_score seul':<32}  {'+ presence bonus':<32}")
        for index in range(top_n):
            left = (
                f"{index + 1:2}. {before[index].name:<16} "
                f"(m={before[index].meta_score:.3f})"
                if index < len(before)
                else ""
            )
            right = (
                f"{index + 1:2}. {after[index].name:<16} "
                f"(f={after[index].final_score:.3f} m={after[index].meta_score:.3f} "
                f"p={after[index].presence_score:.3f})"
                if index < len(after)
                else ""
            )
            print(f"{index + 1:2}  {left:<32}  {right}")

        if only_before:
            print(f"  Sortis du top-{top_n} : {', '.join(only_before)}")
        if only_after:
            print(f"  Entres dans top-{top_n} : {', '.join(only_after)}")
        if not only_before and not only_after:
            print(f"  Meme set top-{top_n} (ordre possiblement different).")


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
    """Pool meta pro : exclusion dure >= MIN_GAMES_EXCLUSION, tri score_final_meta.

    score_final_meta = meta_score + PRESENCE_SCORE_WEIGHT * presence_score
    (presence depuis meta_tierlist.csv). Wilson LB n'entre pas dans le tri.
    """
    top_n = max(1, top_n)
    ranked = _rank_meta_pool_for_role(
        role,
        patch,
        candidates=candidates,
        champion_features=champion_features,
        lookup_by_norm=lookup_by_norm,
        min_fitness=min_fitness,
        oracle_csv=oracle_csv,
        tierlist_csv=DEFAULT_META_TIERLIST_CSV,
        apply_presence_bonus=True,
    )
    selected = [entry.name for entry in ranked[:top_n]]

    logger.debug(
        "Meta pool %s: %d candidats (>=%d games), retourne top_%d=%s",
        _normalize_role(role),
        len(ranked),
        MIN_GAMES_EXCLUSION,
        top_n,
        selected,
    )
    return selected
