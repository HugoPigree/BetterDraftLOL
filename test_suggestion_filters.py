"""Garde-fous : pool meta pro (>= MIN_GAMES_EXCLUSION) pour toutes les suggestions joueur."""

from __future__ import annotations

import re
from unittest.mock import patch

import predict_draft as pd
import pro_force

from justification_builder import assert_justification_role_consistency, generate_pick_justification
from pro_force import MIN_GAMES_EXCLUSION, get_pro_winrate_lookup
from suggest_draft import (
    get_champion_role_catalog,
    normalize_role,
    suggest_ban,
    suggest_improvements,
    suggest_retrospective_bans,
    suggest_retrospective_picks,
)

PATCH = "16.13"
MOCK_LOW_VOLUME = "MockLowVolume"
MOCK_LOW_VOLUME_ON_TEAM = "Riven"

BLUE = [
    {"champion": "Gnar", "role": "TOP"},
    {"champion": "Xin Zhao", "role": "JUNGLE"},
    {"champion": "Ahri", "role": "MIDDLE"},
    {"champion": "Corki", "role": "BOTTOM"},
    {"champion": "Leona", "role": "UTILITY"},
]
RED = [
    {"champion": "Renekton", "role": "TOP"},
    {"champion": "Graves", "role": "JUNGLE"},
    {"champion": "Syndra", "role": "MIDDLE"},
    {"champion": "Jhin", "role": "BOTTOM"},
    {"champion": "Nautilus", "role": "UTILITY"},
]
RED_WITH_LOW_VOLUME = [
    {"champion": "Renekton", "role": "TOP"},
    {"champion": MOCK_LOW_VOLUME_ON_TEAM, "role": "JUNGLE"},
    {"champion": "Syndra", "role": "MIDDLE"},
    {"champion": "Jhin", "role": "BOTTOM"},
    {"champion": "Nautilus", "role": "UTILITY"},
]


def _available_excluding(*teams: list[dict[str, str]]) -> list[str]:
    catalog = get_champion_role_catalog()
    used = {slot["champion"].casefold() for team in teams for slot in team}
    return sorted(
        [name for name in catalog if name.casefold() not in used],
        key=str.casefold,
    )


def _mock_low_volume_lookup() -> dict[tuple[str, str], tuple[float, int]]:
    mocked = dict(get_pro_winrate_lookup())
    mocked[(MOCK_LOW_VOLUME, "JUNGLE")] = (0.80, 14)
    mocked[(MOCK_LOW_VOLUME_ON_TEAM, "JUNGLE")] = (0.80, 14)
    return mocked


def _assert_suggestions_meet_min_games(
    items: list[dict],
    *,
    role: str | None = None,
    role_key: str = "role",
    champion_key: str = "champion",
) -> None:
    lookup = get_pro_winrate_lookup()
    for item in items:
        item_role = item.get(role_key) or item.get("best_opponent_role") or role
        champion = item[champion_key]
        assert item_role is not None, f"Rôle manquant pour {champion}: {item}"
        entry = lookup.get((champion, item_role))
        games = entry[1] if entry else 0
        assert games >= MIN_GAMES_EXCLUSION, (
            f"{champion} ({item_role}) n'a que {games} games pro, "
            f"attendu >= {MIN_GAMES_EXCLUSION}"
        )


def test_low_volume_mock_excluded_from_suggest_improvements() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    pool = [MOCK_LOW_VOLUME, *_available_excluding(BLUE, RED)]

    with patch.object(pro_force, "get_pro_winrate_lookup", return_value=_mock_low_volume_lookup()):
        pro_force.reset_pro_force_state()
        result = suggest_improvements(
            team_picks=BLUE,
            opponent_picks=RED,
            role_to_improve="JUNGLE",
            patch=PATCH,
            available_champions=pool,
            top_n=10,
        )

    champions = {item["champion"] for item in result["suggestions"]}
    assert MOCK_LOW_VOLUME not in champions
    _assert_suggestions_meet_min_games(result["suggestions"], role="JUNGLE")


def test_low_volume_mock_excluded_from_suggest_ban() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    opponent_partial = RED[:3]
    pool = [MOCK_LOW_VOLUME, *_available_excluding(BLUE, opponent_partial)]

    with patch.object(pro_force, "get_pro_winrate_lookup", return_value=_mock_low_volume_lookup()):
        pro_force.reset_pro_force_state()
        result = suggest_ban(
            available_champions=pool,
            opponent_partial_picks=opponent_partial,
            opponent_remaining_roles=["JUNGLE", "BOTTOM", "UTILITY"],
            patch=PATCH,
            team_picks=BLUE,
            top_n=10,
        )

    champions = {item["champion"] for item in result["suggestions"]}
    assert MOCK_LOW_VOLUME not in champions
    _assert_suggestions_meet_min_games(
        result["suggestions"],
        role_key="best_opponent_role",
    )


def test_low_volume_mock_excluded_from_suggest_retrospective_bans() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    pool = _available_excluding(BLUE, RED_WITH_LOW_VOLUME)

    with patch.object(pro_force, "get_pro_winrate_lookup", return_value=_mock_low_volume_lookup()):
        pro_force.reset_pro_force_state()
        result = suggest_retrospective_bans(
            team_picks=BLUE,
            opponent_picks=RED_WITH_LOW_VOLUME,
            patch=PATCH,
            available_champions=pool,
            top_n=5,
        )

    champions = {item["champion"] for item in result["suggestions"]}
    assert MOCK_LOW_VOLUME_ON_TEAM not in champions
    _assert_suggestions_meet_min_games(result["suggestions"])


def test_low_volume_mock_excluded_from_suggest_retrospective_picks() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    pool = [MOCK_LOW_VOLUME, *_available_excluding(BLUE, RED)]

    with patch.object(pro_force, "get_pro_winrate_lookup", return_value=_mock_low_volume_lookup()):
        pro_force.reset_pro_force_state()
        result = suggest_retrospective_picks(
            team_picks=BLUE,
            opponent_picks=RED,
            patch=PATCH,
            available_champions=pool,
            picks_per_role=2,
        )

    champions = {item["champion"] for item in result["suggestions"]}
    assert MOCK_LOW_VOLUME not in champions
    _assert_suggestions_meet_min_games(result["suggestions"])


def test_flex_champion_justification_keeps_single_assigned_role() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    team = [
        {"champion": "Gnar", "role": "TOP"},
        {"champion": "Vi", "role": "JUNGLE"},
        {"champion": "Ahri", "role": "MIDDLE"},
        {"champion": "Jhin", "role": "BOTTOM"},
        {"champion": "Nautilus", "role": "UTILITY"},
    ]

    for role in ("UTILITY", "BOTTOM"):
        text = generate_pick_justification(
            "Seraphine",
            role,
            team_context=replace_slot(team, role, "Seraphine"),
            opponent_context=[],
            source_data={"mode": "pro", "pick_side": "team"},
        )
        assert_justification_role_consistency(text, role)


def replace_slot(
    team: list[dict[str, str]],
    role: str,
    champion: str,
) -> list[dict[str, str]]:
    target = normalize_role(role)
    return [
        {"champion": champion, "role": target}
        if normalize_role(slot["role"]) == target
        else dict(slot)
        for slot in team
    ]
