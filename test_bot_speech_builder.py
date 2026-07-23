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
        "meta": "Ahri est un pick établi en mid pro (900 games, Wilson LB 53%, tendance en hausse)",
        "composition": "Ce pick comble un manque de peel dans la composition",
        "duo": "En mid, le duo jungle-support avec Thresh est solide (meta_score 0.72).",
        "stats": "presence_score élevé et damage_profile magic.",
        "meta_kind": "established",
        "trend": "hausse",
        "composition_shifts": ["peel"],
        "coherence": "ok",
        "duo_partner": "Thresh",
        "lane_opponent": "Zed",
        "technical_full": "Ahri est un pick établi… Wilson LB 53%… archétype Meraki…",
    }

    spoken = build_plain_pick_explanation("Ahri", "MIDDLE", technical)

    assert spoken
    assert "Ahri" in spoken
    for banned in TECHNICAL_BLACKLIST:
        assert banned not in spoken, f"Jargon technique trouvé: {banned!r} dans {spoken!r}"


def test_build_plain_pick_explanation_covers_matchup_and_duo() -> None:
    spoken = build_plain_pick_explanation(
        "Jinx",
        "BOTTOM",
        {
            "meta_kind": "established",
            "trend": None,
            "composition_shifts": ["engage"],
            "duo_partner": "Nautilus",
            "lane_opponent": "Kai'Sa",
        },
    )
    assert "Jinx" in spoken or "Nautilus" in spoken or "Kai'Sa" in spoken
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
                "magic_ratio": 0.45,
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
