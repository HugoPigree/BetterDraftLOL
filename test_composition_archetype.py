"""Tests cohérence d'archétype de composition (Partie A)."""

from __future__ import annotations

import predict_draft as pd

from composition_archetype import (
    compute_composition_archetype,
    score_archetype_coherence,
)
from suggest_draft import decompose_bot_candidate_score

PATCH = "16.13"

# 4 picks all-in early sans peel : top/jungle/mid/adc agressifs physiques.
EARLY_DIVE_FOUR = [
    {"champion": "Renekton", "role": "TOP"},
    {"champion": "LeeSin", "role": "JUNGLE"},
    {"champion": "Pantheon", "role": "MIDDLE"},
    {"champion": "Lucian", "role": "BOTTOM"},
]

# Comp mixte : engage + scaling + AD/AP equilibres (pas 100% early dive).
MIXED_FOUR = [
    {"champion": "Ornn", "role": "TOP"},
    {"champion": "Maokai", "role": "JUNGLE"},
    {"champion": "Orianna", "role": "MIDDLE"},
    {"champion": "Jhin", "role": "BOTTOM"},
]

DEFAULT_OPPONENT = [
    {"champion": "Gnar", "role": "TOP"},
    {"champion": "Vi", "role": "JUNGLE"},
]


def _pool_excluding(*teams: list[dict[str, str]]) -> list[str]:
    from suggest_draft import get_champion_role_catalog

    catalog = get_champion_role_catalog()
    used = {slot["champion"].casefold() for team in teams for slot in team}
    return [name for name in sorted(catalog) if name.casefold() not in used]


def _decompose(
    bot_partial: list[dict[str, str]],
    candidate: str,
    role: str,
) -> dict:
    row = decompose_bot_candidate_score(
        bot_partial,
        DEFAULT_OPPONENT,
        candidate,
        role,
        PATCH,
        _pool_excluding(bot_partial, DEFAULT_OPPONENT),
    )
    assert row is not None, f"decomposition impossible pour {candidate} ({role})"
    return row


def test_compute_composition_archetype_early_dive_profile() -> None:
    pd.reset_predict_state()
    archetype = compute_composition_archetype(
        [slot["champion"] for slot in EARLY_DIVE_FOUR]
    )

    assert archetype["team_size"] == 4
    assert archetype["power_curve"] < -0.15
    assert archetype["engage_score"] > 0.4
    assert archetype["peel_score"] < 0.1
    assert archetype["damage_profile"]["physical_count"] == 4
    assert archetype["damage_profile"]["damage_balance"] < 0.1


def test_fifth_pick_fragile_scaling_penalized_vs_peel_enchanter() -> None:
    pd.reset_predict_state()

    team_names = [slot["champion"] for slot in EARLY_DIVE_FOUR]
    fragile_score = score_archetype_coherence(team_names, "Jinx")
    peel_score = score_archetype_coherence(team_names, "Lulu")

    assert peel_score > fragile_score
    assert fragile_score <= 0.35
    assert peel_score >= 0.85


def test_enchanter_support_improves_coherence_on_early_dive() -> None:
    pd.reset_predict_state()

    team_names = [slot["champion"] for slot in EARLY_DIVE_FOUR]
    enchanter = score_archetype_coherence(team_names, "Nami")
    fragile = score_archetype_coherence(team_names, "KogMaw")

    assert enchanter > fragile
    assert enchanter >= 0.85


def test_peel_candidate_raises_score_vs_baseline() -> None:
    pd.reset_predict_state()

    team_names = [slot["champion"] for slot in EARLY_DIVE_FOUR]
    baseline = score_archetype_coherence(team_names, "Jinx")
    with_peel = score_archetype_coherence(team_names, "Lulu")

    assert with_peel - baseline >= 0.5


def test_mixed_comp_archetype_does_not_dominate_meta_advantage() -> None:
    """Sur comp mixte, l'avantage meta/synergie reste plus grand que l'ecart archétype."""
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    strong_meta = _decompose(MIXED_FOUR, "Bard", "UTILITY")
    weak_meta = _decompose(MIXED_FOUR, "Brand", "UTILITY")

    total_gap = strong_meta["selection_score"] - weak_meta["selection_score"]
    arch_gap = strong_meta["score_archetype"] - weak_meta["score_archetype"]
    non_arch_gap = total_gap - arch_gap

    assert total_gap > 0
    assert non_arch_gap > arch_gap * 2
    assert non_arch_gap > 10.0


def test_aligned_meta_and_archetype_only_marginally_differs() -> None:
    """Quand meta et archétype pointent dans le même sens, l'écart archétype reste faible."""
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    top_meta = _decompose(MIXED_FOUR, "Bard", "UTILITY")
    second_meta = _decompose(MIXED_FOUR, "Nautilus", "UTILITY")

    assert top_meta["meta_raw"] >= second_meta["meta_raw"]
    assert top_meta["selection_score"] >= second_meta["selection_score"]
    assert abs(top_meta["score_archetype"] - second_meta["score_archetype"]) <= 1.0


def test_archetype_coherent_filler_prefers_peel_on_early_dive() -> None:
    """Les fillers de simulation complètent l'archétype au lieu de prendre le #1 meta aveugle."""
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    from suggest_draft import (
        get_champion_role_catalog,
        pick_archetype_coherent_filler_for_role,
        pick_meta_filler_for_role,
    )

    early_dive = ["Renekton", "LeeSin", "Pantheon", "Lucian"]
    catalog = get_champion_role_catalog()
    pool = _pool_excluding()
    reserved: set[str] = set()

    coherent = pick_archetype_coherent_filler_for_role(
        "UTILITY", catalog, pool, reserved, PATCH, "pro", early_dive
    )
    blind_meta = pick_meta_filler_for_role(
        "UTILITY", catalog, pool, reserved, PATCH, "pro"
    )

    assert coherent
    assert blind_meta
    coherent_score = score_archetype_coherence(early_dive, coherent)
    blind_score = score_archetype_coherence(early_dive, blind_meta)
    assert coherent_score >= blind_score
    assert coherent_score >= 0.75
