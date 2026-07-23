"""Tests pour bot_speech_builder.py — langage naturel sans jargon technique."""

from __future__ import annotations

from bot_speech_builder import (
    TECHNICAL_BLACKLIST,
    build_plain_pick_explanation,
    build_plain_team_synergy_summary,
    build_pick_justification_dict,
)


def test_build_plain_pick_explanation_has_no_technical_jargon() -> None:
    technical = {
        "meta_kind": "established",
        "trend": "hausse",
        "ban_rate": 0.12,
        "games": 900,
        "composition_shifts": ["peel"],
        "duo": {
            "partner": "Thresh",
            "lane_label": "bot lane",
            "winrate": 0.54,
            "games": 80,
        },
        "lane_opponent": "Zed",
        "my_gold_at_15": 145.0,
        "opp_gold_at_15": 20.0,
    }

    spoken = build_plain_pick_explanation("Ahri", "MIDDLE", technical)

    assert spoken
    assert "Ahri" in spoken
    assert "900" in spoken or "Thresh" in spoken or "145" in spoken
    for banned in TECHNICAL_BLACKLIST:
        assert banned not in spoken, f"Jargon technique trouvé: {banned!r} dans {spoken!r}"


def test_build_plain_pick_explanation_duo_and_matchup_are_concrete() -> None:
    spoken = build_plain_pick_explanation(
        "Sivir",
        "BOTTOM",
        {
            "meta_kind": "established",
            "games": 400,
            "composition_shifts": ["damage_balance"],
            "duo": {
                "partner": "Bard",
                "lane_label": "bot lane",
                "winrate": 0.553,
                "games": 62,
            },
            "lane_opponent": "Caitlyn",
            "my_gold_at_15": 120.0,
            "opp_gold_at_15": 40.0,
            "damage_before": {
                "damage_profile": {"physical_count": 3, "magic_count": 1},
            },
            "damage_after": {
                "damage_profile": {"physical_count": 3, "magic_count": 2},
            },
        },
    )
    assert "Bard" in spoken
    assert "55.3%" in spoken or "55%" in spoken or "winrate" in spoken.lower()
    assert "Caitlyn" in spoken
    assert "gold" in spoken.lower()
    for banned in ("Wilson", "meta_score", "presence_score", "damage_profile"):
        assert banned not in spoken


def test_build_plain_team_synergy_summary_has_no_technical_jargon() -> None:
    summary = build_plain_team_synergy_summary(
        ["Gnar", "Lee Sin", "Ahri", "Jinx", "Thresh"],
        {
            "power_curve": -0.4,
            "engage_score": 0.7,
            "peel_score": 0.6,
            "damage_profile": {
                "physical_count": 3,
                "magic_count": 2,
                "magic_ratio": 0.4,
                "damage_balance": 0.9,
            },
        },
    )
    assert summary
    for banned in TECHNICAL_BLACKLIST:
        assert banned not in summary, f"Jargon technique trouvé: {banned!r} dans {summary!r}"


def test_build_pick_justification_dict_feeds_plain_speech() -> None:
    technical = build_pick_justification_dict(
        "Ahri",
        "MIDDLE",
        [{"champion": "Ahri", "role": "MIDDLE"}],
        [{"champion": "Zed", "role": "MIDDLE"}],
        mode="pro",
    )
    spoken = build_plain_pick_explanation("Ahri", "MIDDLE", technical)
    assert spoken
    for banned in TECHNICAL_BLACKLIST:
        assert banned not in spoken
