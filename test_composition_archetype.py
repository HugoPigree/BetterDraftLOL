"""Tests cohérence d'archétype de composition (Partie A)."""

from __future__ import annotations

import predict_draft as pd

from composition_archetype import (
    compute_composition_archetype,
    score_archetype_coherence,
)

# 4 picks all-in early sans peel : top/jungle/mid/adc agressifs physiques.
EARLY_DIVE_FOUR = ["Renekton", "LeeSin", "Pantheon", "Lucian"]


def test_compute_composition_archetype_early_dive_profile() -> None:
    pd.reset_predict_state()
    archetype = compute_composition_archetype(EARLY_DIVE_FOUR)

    assert archetype["team_size"] == 4
    assert archetype["power_curve"] < -0.15
    assert archetype["engage_score"] > 0.4
    assert archetype["peel_score"] < 0.1
    assert archetype["damage_profile"]["physical_count"] == 4
    assert archetype["damage_profile"]["damage_balance"] < 0.1


def test_fifth_pick_fragile_scaling_penalized_vs_peel_enchanter() -> None:
    pd.reset_predict_state()

    fragile_score = score_archetype_coherence(EARLY_DIVE_FOUR, "Jinx")
    peel_score = score_archetype_coherence(EARLY_DIVE_FOUR, "Lulu")

    assert peel_score > fragile_score
    assert fragile_score <= 0.35
    assert peel_score >= 0.85


def test_enchanter_support_improves_coherence_on_early_dive() -> None:
    pd.reset_predict_state()

    enchanter = score_archetype_coherence(EARLY_DIVE_FOUR, "Nami")
    fragile = score_archetype_coherence(EARLY_DIVE_FOUR, "KogMaw")

    assert enchanter > fragile
    assert enchanter >= 0.85


def test_peel_candidate_raises_score_vs_baseline() -> None:
    pd.reset_predict_state()

    baseline = score_archetype_coherence(EARLY_DIVE_FOUR, "Jinx")
    with_peel = score_archetype_coherence(EARLY_DIVE_FOUR, "Lulu")

    assert with_peel - baseline >= 0.5
