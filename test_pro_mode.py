"""Tests du mode PRO : aucune donnée soloQ dans la réponse /predict."""

from __future__ import annotations

import json
import re

import predict_draft as pd
from fastapi.testclient import TestClient

from api import create_app
from suggest_draft import get_champion_role_catalog, suggest_improvements

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


def _assert_no_soloq_in_payload(payload: dict) -> None:
    serialized = json.dumps(payload).lower()
    assert "soloq" not in serialized
    assert "solo queue" not in serialized
    assert "soloq_composite" not in serialized

    for side in ("blue", "red"):
        team = payload[side]
        for champ in team["champions"]:
            assert champ.get("data_source") != "soloq"
            if champ.get("insufficient_data"):
                assert champ.get("winrate") is None

    for duo_side in payload["duo_synergies"].values():
        for duo_key in ("duo_jungle_support", "duo_bot_lane"):
            duo = duo_side[duo_key]
            assert duo.get("is_fallback") is False
            if duo.get("insufficient_data"):
                assert duo.get("score") is None

    for matchup_key in ("bot_lane_matchup", "jungle_support_matchup"):
        matchup = payload[matchup_key]
        assert matchup["method"] != "blended"
        assert matchup["method"] != "soloq_composite"
        assert matchup.get("is_fallback") is False
        if matchup.get("insufficient_data"):
            assert matchup.get("blue_win_probability") is None


def test_predict_pro_mode_direct() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    result = pd.predict_draft(BLUE, RED, patch=PATCH, mode="pro")

    assert result["mode"] == "pro"
    _assert_no_soloq_in_payload(result)


def test_predict_mixed_mode_still_works() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    result = pd.predict_draft(BLUE, RED, patch=PATCH, mode="mixed")

    assert result["mode"] == "mixed"
    assert 0.0 <= result["blue_win_probability"] <= 1.0
    assert result["blue"]["score_force"] is not None


def test_api_predict_pro_mode() -> None:
    pd.reset_predict_state()
    client = TestClient(create_app())

    response = client.post(
        "/predict",
        json={
            "blue_team": BLUE,
            "red_team": RED,
            "patch": PATCH,
            "mode": "pro",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "pro"
    _assert_no_soloq_in_payload(payload)


def test_pro_mode_reasons_exclude_soloq() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    catalog = get_champion_role_catalog()
    used = {slot["champion"].casefold() for slot in BLUE + RED}
    available = sorted(
        [name for name in catalog if name.casefold() not in used],
        key=str.casefold,
    )

    result = suggest_improvements(
        team_picks=BLUE,
        opponent_picks=RED,
        role_to_improve="MIDDLE",
        patch=PATCH,
        available_champions=available,
        team_side="blue",
        top_n=3,
        mode="pro",
    )
    assert result["suggestions"]
    for item in result["suggestions"]:
        assert not re.search(r"solo\s*q", item["reason"], re.IGNORECASE)


def test_pro_mode_internal_duo_advantage_one_side_missing() -> None:
    from predict_draft import compute_internal_duo_advantage

    blue = {"score": 0.654, "games": 26, "insufficient_data": False}
    red = {"score": None, "games": 3, "insufficient_data": True}

    adv = compute_internal_duo_advantage(blue, red, mode="pro")
    assert adv["insufficient_data"] is True
    assert adv["insufficient_sides"] == ["red"]
    assert "Red" in adv["comparison_message"]
    assert blue["score"] == 0.654


def test_pro_mode_internal_duo_advantage_both_present() -> None:
    from predict_draft import compute_internal_duo_advantage

    blue = {"score": 0.54, "games": 20, "insufficient_data": False}
    red = {"score": 0.48, "games": 18, "insufficient_data": False}

    adv = compute_internal_duo_advantage(blue, red, mode="pro")
    assert adv["insufficient_data"] is False
    assert adv["stronger_side"] == "blue"
    assert adv["difference"] == round(0.54 - 0.48, 4)

