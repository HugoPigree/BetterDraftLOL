"""Tests pour suggest_draft.py."""

from __future__ import annotations

import pytest
import predict_draft as pd

from champion_profile_stats import DESCRIPTIVE_DISCLAIMER
from justification_builder import assert_narrative_order, section_positions
from pro_force import MIN_GAMES_EXCLUSION
from suggest_draft import (
    champions_playable_on_role,
    get_champion_role_catalog,
    suggest_ban,
    suggest_improvements,
    suggest_retrospective_bans,
    suggest_retrospective_picks,
)

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
PATCH = "16.13"


def _available_excluding(*teams: list[dict[str, str]]) -> list[str]:
    catalog = get_champion_role_catalog()
    used = {slot["champion"].casefold() for team in teams for slot in team}
    return sorted(
        [name for name in catalog if name.casefold() not in used],
        key=str.casefold,
    )


def test_champions_playable_on_role_filters_by_meraki() -> None:
    catalog = get_champion_role_catalog()
    pool = _available_excluding(BLUE, RED)
    jungle = champions_playable_on_role(pool, "JUNGLE", catalog)
    assert all("JUNGLE" in catalog.get(name, []) for name in jungle)


def _assert_decomposition(item: dict) -> None:
    assert "delta_force" in item
    assert "delta_synergie" in item
    assert "delta_duo" in item
    assert "delta_total" in item
    assert "reason" in item and item["reason"]
    summed = round(
        item["delta_force"] + item["delta_synergie"] + item["delta_duo"],
        2,
    )
    assert summed == item["delta_total"]
    assert item["delta_total"] == item["gain_percentage_points"]


def test_suggest_improvements_returns_top_candidates() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    result = suggest_improvements(
        team_picks=BLUE,
        opponent_picks=RED,
        role_to_improve="JUNGLE",
        patch=PATCH,
        available_champions=_available_excluding(BLUE, RED),
        team_side="blue",
        top_n=5,
    )

    assert result["role"] == "JUNGLE"
    assert result["current_win_probability"] is not None
    assert len(result["suggestions"]) <= 5
    for item in result["suggestions"]:
        assert "champion" in item
        assert "win_probability" in item
        assert "gain_percentage_points" in item
        _assert_decomposition(item)


def test_suggest_ban_returns_threat_ranking() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    opponent_partial = RED[:3]
    remaining = ["BOTTOM", "UTILITY"]

    result = suggest_ban(
        available_champions=_available_excluding(BLUE, opponent_partial),
        opponent_partial_picks=opponent_partial,
        opponent_remaining_roles=remaining,
        patch=PATCH,
        team_picks=BLUE,
        team_side="blue",
        top_n=5,
    )

    assert result["baseline_opponent_win_probability"] is not None
    assert len(result["suggestions"]) <= 5
    for item in result["suggestions"]:
        assert item["best_opponent_role"] in remaining
        assert item["opponent_win_probability"] >= 0.0
        assert item["reason"]
        assert item["delta_total"] <= 0
        summed = round(
            item["delta_force"] + item["delta_synergie"] + item["delta_duo"],
            2,
        )
        assert summed == item["delta_total"]


def test_suggest_endpoints_via_api() -> None:
    from fastapi.testclient import TestClient

    from api import create_app

    client = TestClient(create_app())
    available = _available_excluding(BLUE, RED)

    pick_response = client.post(
        "/suggest-pick",
        json={
            "team_side": "blue",
            "team_picks": BLUE,
            "opponent_picks": RED,
            "role_to_improve": "JUNGLE",
            "patch": PATCH,
            "available_champions": available,
        },
    )
    assert pick_response.status_code == 200, pick_response.text

    ban_response = client.post(
        "/suggest-ban",
        json={
            "team_side": "blue",
            "team_picks": BLUE,
            "opponent_picks": RED[:3],
            "opponent_remaining_roles": ["BOTTOM", "UTILITY"],
            "patch": PATCH,
            "available_champions": _available_excluding(BLUE, RED[:3]),
        },
    )
    assert ban_response.status_code == 200, ban_response.text

    retro_response = client.post(
        "/suggest-retrospective-ban",
        json={
            "team_side": "blue",
            "team_picks": BLUE,
            "opponent_picks": RED,
            "patch": PATCH,
            "available_champions": available,
        },
    )
    assert retro_response.status_code == 200, retro_response.text
    retro_payload = retro_response.json()
    assert retro_payload["current_win_probability"] is not None
    for item in retro_payload["suggestions"]:
        assert "champion" in item
        assert "reason" in item
        assert item["reason"]
        assert item["gain_percentage_points"] >= 0.35
        _assert_decomposition(item)


def test_suggest_retrospective_bans_ranks_enemy_picks() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    result = suggest_retrospective_bans(
        team_picks=BLUE,
        opponent_picks=RED,
        patch=PATCH,
        available_champions=_available_excluding(BLUE, RED),
        team_side="blue",
        top_n=3,
    )

    assert result["current_win_probability"] is not None
    assert len(result["suggestions"]) <= 3
    enemy_names = {slot["champion"] for slot in RED}
    for item in result["suggestions"]:
        assert item["champion"] in enemy_names
        assert item["gain_percentage_points"] >= 0.35
        assert item["reason"]
        assert item["replacement_champion"]
        _assert_decomposition(item)


def test_suggest_retrospective_picks_returns_up_to_three_per_role() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    result = suggest_retrospective_picks(
        team_picks=BLUE,
        opponent_picks=RED,
        patch=PATCH,
        available_champions=_available_excluding(BLUE, RED),
        team_side="blue",
        picks_per_role=3,
    )

    assert result["current_win_probability"] is not None
    by_role: dict[str, list[dict]] = {}
    for item in result["suggestions"]:
        by_role.setdefault(item["role"], []).append(item)

    assert by_role, "Au moins un rôle devrait avoir des alternatives"
    for role, items in by_role.items():
        assert len(items) <= 3
        assert len(items) >= 1, (
            f"Au moins 1 alternative meta-viable (>= {MIN_GAMES_EXCLUSION} games) "
            f"attendue pour {role}, got {len(items)}"
        )
        assert role in {"TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"}
        champions = {entry["champion"] for entry in items}
        assert len(champions) == len(items)
        for item in items:
            assert item["current_champion"]
            assert item["champion"] != item["current_champion"]
            assert item["gain_percentage_points"] > 0
            assert item["reason"]
            _assert_decomposition(item)


def test_suggest_reason_may_include_descriptive_historical_stats() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    result = suggest_improvements(
        team_picks=BLUE,
        opponent_picks=RED,
        role_to_improve="TOP",
        patch=PATCH,
        available_champions=_available_excluding(BLUE, RED),
        team_side="blue",
        top_n=25,
    )

    with_stats = [item for item in result["suggestions"] if DESCRIPTIVE_DISCLAIMER in item["reason"]]
    assert with_stats, "Au moins une suggestion top devrait inclure des stats historiques"
    for item in with_stats:
        pos = section_positions(item["reason"])
        assert "meta" in pos
        assert "stats" in pos
        assert pos["stats"] > pos["meta"]


def test_justification_narrative_order_on_concrete_cases() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    jungle_result = suggest_improvements(
        team_picks=BLUE,
        opponent_picks=RED,
        role_to_improve="JUNGLE",
        patch=PATCH,
        available_champions=_available_excluding(BLUE, RED),
        team_side="blue",
        top_n=5,
    )
    assert jungle_result["suggestions"]
    assert_narrative_order(jungle_result["suggestions"][0]["reason"])

    bot_partial = [
        {"champion": "Corki", "role": "BOTTOM"},
        {"champion": "Leona", "role": "UTILITY"},
    ]
    opponent_partial = RED[:3]
    from suggest_draft import suggest_bot_pick

    bot_result = suggest_bot_pick(
        bot_partial_picks=bot_partial,
        opponent_partial_picks=opponent_partial,
        patch=PATCH,
        available_champions=_available_excluding(BLUE, RED),
        team_side="blue",
        mode="pro",
        rng_seed=42,
    )
    assert bot_result.get("reason")
    assert_narrative_order(bot_result["reason"])
    bot_pos = section_positions(bot_result["reason"])
    if "duo" in bot_pos:
        assert bot_pos["duo"] > bot_pos.get("meta", -1)

    ban_result = suggest_ban(
        available_champions=_available_excluding(BLUE, RED[:3]),
        opponent_partial_picks=RED[:3],
        opponent_remaining_roles=["BOTTOM", "UTILITY"],
        patch=PATCH,
        team_picks=BLUE,
        team_side="blue",
        top_n=5,
    )
    assert ban_result["suggestions"]
    assert_narrative_order(ban_result["suggestions"][0]["reason"])


def test_lane_gain_synergy_loss_mentioned_in_composition() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    result = suggest_improvements(
        team_picks=BLUE,
        opponent_picks=RED,
        role_to_improve="TOP",
        patch=PATCH,
        available_champions=_available_excluding(BLUE, RED),
        team_side="blue",
        top_n=20,
    )

    for item in result["suggestions"]:
        if item["delta_force"] > 0.05 and item["delta_synergie"] < -0.05:
            assert "synergie globale" in item["reason"]
            assert_narrative_order(item["reason"])
            break
    else:
        pytest.skip("Aucun candidat top avec gain lane / perte synergie dans ce draft")


def test_suggest_retrospective_pick_endpoint() -> None:
    from fastapi.testclient import TestClient

    from api import create_app

    client = TestClient(create_app())
    available = _available_excluding(BLUE, RED)

    response = client.post(
        "/suggest-retrospective-pick",
        json={
            "team_side": "blue",
            "team_picks": BLUE,
            "opponent_picks": RED,
            "patch": PATCH,
            "available_champions": available,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["current_win_probability"] is not None
    for item in payload["suggestions"]:
        assert "current_champion" in item
        assert item["gain_percentage_points"] > 0
        _assert_decomposition(item)
