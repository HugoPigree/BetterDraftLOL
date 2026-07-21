"""Tests pour les contributions de synergie globale (ablation)."""

from __future__ import annotations

import predict_draft as pd

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


def test_predict_includes_synergy_insight() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    result = pd.predict_draft(BLUE, RED, patch=PATCH)

    for side in ("blue", "red"):
        insight = result[side]["synergy_insight"]
        assert len(insight["contributions"]) == 5
        assert insight["top_contributor"]["champion"]
        assert insight["least_contributor"]["champion"]
        champions = {entry["champion"] for entry in insight["contributions"]}
        assert len(champions) == 5


def test_synergy_contributions_have_distinct_top_and_least() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    result = pd.predict_draft(BLUE, RED, patch=PATCH)
    insight = result["blue"]["synergy_insight"]
    top_pts = insight["top_contributor"]["marginal_points"]
    least_pts = insight["least_contributor"]["marginal_points"]
    assert top_pts >= least_pts
