#!/usr/bin/env python3
"""Pro winrates by champion/role from Oracle's Elixir player rows."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

import build_training_dataset as btd
from build_duo_dataset import load_player_rows

logger = logging.getLogger(__name__)

MIN_GAMES_PRO_FORCE = 10
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


def reset_pro_force_state() -> None:
    global _pro_winrate_lookup, _pro_oracle_path
    _pro_winrate_lookup = None
    _pro_oracle_path = None


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
