"""Tests de non-régression pour POST /predict après hot-reload simulé."""

from __future__ import annotations

import importlib
from unittest.mock import patch

import build_training_dataset as btd
import predict_draft as pd
from fastapi.testclient import TestClient

from api import create_app

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
PAYLOAD = {"blue_team": BLUE, "red_team": RED, "patch": PATCH}


def test_predict_twice_with_different_teams() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    first = pd.predict_draft(BLUE, RED, patch=PATCH)
    alt_red = [
        {"champion": "Aatrox", "role": "TOP"},
        {"champion": "Amumu", "role": "JUNGLE"},
        {"champion": "Anivia", "role": "MIDDLE"},
        {"champion": "Ashe", "role": "BOTTOM"},
        {"champion": "Alistar", "role": "UTILITY"},
    ]
    second = pd.predict_draft(BLUE, alt_red, patch=PATCH)

    assert 0.0 <= first["blue_win_probability"] <= 1.0
    assert 0.0 <= second["blue_win_probability"] <= 1.0
    assert first["blue_win_probability"] != second["blue_win_probability"]


def test_predict_survives_simulated_hot_reload() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()
    before = pd.predict_draft(BLUE, RED, patch=PATCH)

    importlib.reload(btd)
    importlib.reload(pd)
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    after = pd.predict_draft(BLUE, RED, patch=PATCH)
    assert before["blue_win_probability"] == after["blue_win_probability"]


def test_malformed_meraki_features_raises_clear_error() -> None:
    pd.reset_predict_state()

    def bad_build(_champions: object) -> tuple[object, object, object]:
        return {}, [], {}

    with patch.object(btd, "build_champion_feature_dict", bad_build):
        try:
            pd.get_meraki_context()
        except ValueError as exc:
            assert "3 valeurs" in str(exc)
        else:
            raise AssertionError("ValueError attendue pour un retour Meraki malformé")


def test_api_predict_endpoint_after_reset() -> None:
    client = TestClient(create_app())

    first = client.post("/predict", json=PAYLOAD)
    assert first.status_code == 200, first.text

    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    second = client.post("/predict", json=PAYLOAD)
    assert second.status_code == 200, second.text
    assert first.json()["blue_win_probability"] == second.json()["blue_win_probability"]


def test_predict_includes_duo_synergies() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    result = pd.predict_draft(BLUE, RED, patch=PATCH)

    blue_js = result["duo_synergies"]["blue"]["duo_jungle_support"]
    assert blue_js["champions"] == ["Xin Zhao", "Leona"]
    assert "score" in blue_js
    assert "games" in blue_js
    assert "is_fallback" in blue_js

    blue_bl = result["duo_synergies"]["blue"]["duo_bot_lane"]
    assert blue_bl["champions"] == ["Corki", "Leona"]

    js_adv = result["duo_differential"]["jungle_support_advantage"]
    assert js_adv["stronger_side"] in {"blue", "red", "even"}
    assert js_adv["difference"] >= 0

    matchup = result["bot_lane_matchup"]
    assert matchup["blue_champions"] == ["Corki", "Leona"]
    assert matchup["red_champions"] == ["Jhin", "Nautilus"]
    assert 0.0 <= matchup["blue_win_probability"] <= 1.0
    assert matchup["method"] in {"measured", "blended", "soloq_composite"}

    bl_adv = result["duo_differential"]["bot_lane_advantage"]
    assert bl_adv["stronger_side"] in {"blue", "red", "even"}
    assert bl_adv["difference"] == round(abs(matchup["blue_win_probability"] - 0.5), 4)

    js_matchup = result["jungle_support_matchup"]
    assert js_matchup["blue_champions"] == ["Xin Zhao", "Leona"]
    assert js_matchup["red_champions"] == ["Graves", "Nautilus"]
    assert 0.0 <= js_matchup["blue_win_probability"] <= 1.0

    js_adv = result["duo_differential"]["jungle_support_advantage"]
    assert js_adv["stronger_side"] in {"blue", "red", "even"}
    assert js_adv["difference"] == round(abs(js_matchup["blue_win_probability"] - 0.5), 4)

    client = TestClient(create_app())
    response = client.post("/predict", json=PAYLOAD)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "duo_synergies" in payload
    assert "bot_lane_matchup" in payload
    assert "jungle_support_matchup" in payload
    assert "duo_differential" in payload
