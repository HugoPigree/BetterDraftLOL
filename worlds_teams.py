"""Équipes pro pour le mode Worlds."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

DEFAULT_WORLDS_TEAMS_JSON = Path("data/worlds_teams.json")
ROLES_ORDER = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]


def load_pro_teams(json_path: Path = DEFAULT_WORLDS_TEAMS_JSON) -> list[dict[str, Any]]:
    if not json_path.exists():
        raise FileNotFoundError(f"Fichier équipes Worlds introuvable: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    teams = payload.get("teams") or []
    if len(teams) < 7:
        raise ValueError("Au moins 7 équipes pro sont requises pour un tournoi à 8.")
    return teams


def pick_opponent_teams(
    teams: list[dict[str, Any]],
    *,
    count: int = 7,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    pool = list(teams)
    rng.shuffle(pool)
    return pool[:count]


def build_player_team(
    *,
    team_name: str,
    coach_name: str,
    roster: dict[str, str],
) -> dict[str, Any]:
    missing = [role for role in ROLES_ORDER if not str(roster.get(role, "")).strip()]
    if missing:
        raise ValueError(f"Roster incomplet, rôles manquants: {', '.join(missing)}")
    return {
        "id": "player",
        "name": team_name.strip(),
        "region": "CUSTOM",
        "coach": coach_name.strip(),
        "roster": {role: roster[role].strip() for role in ROLES_ORDER},
        "is_player_team": True,
    }


def create_bracket(
    player_team: dict[str, Any],
    opponent_teams: list[dict[str, Any]],
    *,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """Bracket à 8 : quarts → demis → finale."""
    rng = random.Random(seed)
    opponents = list(opponent_teams[:7])
    rng.shuffle(opponents)
    slots = [player_team, *opponents]

    def team_slot(index: int) -> dict[str, Any]:
        return {"team": slots[index], "source_match_id": None}

    return [
        {
            "id": "qf1",
            "round": "quarter",
            "round_label": "Quarts de finale",
            "team_a": team_slot(0),
            "team_b": team_slot(1),
            "winner_id": None,
        },
        {
            "id": "qf2",
            "round": "quarter",
            "round_label": "Quarts de finale",
            "team_a": team_slot(2),
            "team_b": team_slot(3),
            "winner_id": None,
        },
        {
            "id": "qf3",
            "round": "quarter",
            "round_label": "Quarts de finale",
            "team_a": team_slot(4),
            "team_b": team_slot(5),
            "winner_id": None,
        },
        {
            "id": "qf4",
            "round": "quarter",
            "round_label": "Quarts de finale",
            "team_a": team_slot(6),
            "team_b": team_slot(7),
            "winner_id": None,
        },
        {
            "id": "sf1",
            "round": "semi",
            "round_label": "Demi-finales",
            "team_a": {"team": None, "source_match_id": "qf1"},
            "team_b": {"team": None, "source_match_id": "qf2"},
            "winner_id": None,
        },
        {
            "id": "sf2",
            "round": "semi",
            "round_label": "Demi-finales",
            "team_a": {"team": None, "source_match_id": "qf3"},
            "team_b": {"team": None, "source_match_id": "qf4"},
            "winner_id": None,
        },
        {
            "id": "final",
            "round": "final",
            "round_label": "Finale",
            "team_a": {"team": None, "source_match_id": "sf1"},
            "team_b": {"team": None, "source_match_id": "sf2"},
            "winner_id": None,
        },
    ]
