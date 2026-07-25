"""Comfort picks par joueur pro — Oracle's Elixir."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from build_duo_dataset import load_player_rows
from pro_force import DEFAULT_ORACLE_CSV, ORACLE_POSITION_TO_ROLE

logger = logging.getLogger(__name__)

MIN_GAMES_SIGNATURE = 5
SIGNATURE_PICK_RATE_THRESHOLD = 0.12

_signature_lookup: dict[tuple[str, str, str], tuple[float, float, int]] | None = None
_signature_oracle_path: Path | None = None


@dataclass(frozen=True)
class PlayerSignature:
    player: str
    role: str
    champion: str
    games: int
    pick_rate: float
    winrate: float
    score: float


def reset_signature_state() -> None:
    global _signature_lookup, _signature_oracle_path
    _signature_lookup = None
    _signature_oracle_path = None


def build_signature_lookup(
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
    min_games: int = MIN_GAMES_SIGNATURE,
) -> dict[tuple[str, str, str], tuple[float, float, int]]:
    """(player, role, champion) -> (pick_rate, winrate, games)."""
    if not oracle_csv.exists():
        logger.warning("Oracle CSV introuvable pour signatures: %s", oracle_csv)
        return {}

    players = load_player_rows(oracle_csv)
    if players.empty:
        return {}

    frame = players.copy()
    frame["role"] = frame["position"].map(ORACLE_POSITION_TO_ROLE)
    frame = frame.dropna(subset=["role", "champion", "playername"])
    frame["playername"] = frame["playername"].astype(str).str.strip()
    frame["champion"] = frame["champion"].astype(str).str.strip()
    frame["result"] = frame["result"].astype(int)

    player_totals = (
        frame.groupby(["playername", "role"], as_index=False)
        .agg(player_games=("result", "count"))
    )
    grouped = (
        frame.groupby(["playername", "role", "champion"], as_index=False)
        .agg(games=("result", "count"), wins=("result", "sum"))
    )
    grouped = grouped.merge(player_totals, on=["playername", "role"], how="left")
    grouped = grouped[grouped["games"] >= min_games]
    grouped["pick_rate"] = grouped["games"] / grouped["player_games"].clip(lower=1)
    grouped["winrate"] = grouped["wins"] / grouped["games"].clip(lower=1)

    lookup: dict[tuple[str, str, str], tuple[float, float, int]] = {}
    for row in grouped.itertuples(index=False):
        key = (row.playername, row.role, row.champion)
        lookup[key] = (float(row.pick_rate), float(row.winrate), int(row.games))
    return lookup


def _get_lookup(oracle_csv: Path = DEFAULT_ORACLE_CSV) -> dict[tuple[str, str, str], tuple[float, float, int]]:
    global _signature_lookup, _signature_oracle_path
    if _signature_lookup is None or _signature_oracle_path != oracle_csv:
        _signature_lookup = build_signature_lookup(oracle_csv)
        _signature_oracle_path = oracle_csv
    return _signature_lookup


def signature_score(pick_rate: float, winrate: float, games: int) -> float:
    volume = min(1.0, games / 40.0)
    return pick_rate * 100.0 * volume + winrate * 20.0


def get_player_signatures(
    player: str,
    role: str,
    *,
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
    top_n: int = 8,
) -> list[PlayerSignature]:
    lookup = _get_lookup(oracle_csv)
    role_upper = role.strip().upper()
    player_clean = player.strip()
    entries: list[PlayerSignature] = []
    for (p, r, champion), (pick_rate, winrate, games) in lookup.items():
        if p != player_clean or r != role_upper:
            continue
        entries.append(
            PlayerSignature(
                player=p,
                role=r,
                champion=champion,
                games=games,
                pick_rate=pick_rate,
                winrate=winrate,
                score=signature_score(pick_rate, winrate, games),
            )
        )
    entries.sort(key=lambda item: item.score, reverse=True)
    return entries[:top_n]


def get_signature_bonus(
    player: str,
    role: str,
    champion: str,
    *,
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
) -> float:
    lookup = _get_lookup(oracle_csv)
    key = (player.strip(), role.strip().upper(), champion.strip())
    row = lookup.get(key)
    if not row:
        return 0.0
    pick_rate, winrate, games = row
    if pick_rate < SIGNATURE_PICK_RATE_THRESHOLD:
        return 0.0
    return signature_score(pick_rate, winrate, games) * 0.4
