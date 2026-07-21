"""Tests pour champion_profile_stats (texte descriptif uniquement)."""

from __future__ import annotations

import ast
from pathlib import Path

import predict_draft as pd
from champion_profile_stats import (
    ALLOWED_DESCRIPTIVE_CALLERS,
    DESCRIPTIVE_DISCLAIMER,
    assert_descriptive_use_only,
    compute_champion_profile_stats,
    enrich_predict_response_descriptions,
    format_descriptive_stats_clause,
    reset_champion_profile_stats_state,
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


def test_compute_champion_profile_stats_returns_averages() -> None:
    reset_champion_profile_stats_state()
    lookup = compute_champion_profile_stats()
    assert lookup

    fiora = lookup.get(("Fiora", "TOP"))
    assert fiora is not None
    assert fiora.games >= 10
    assert fiora.golddiffat15 is not None
    assert fiora.dpm is not None
    assert fiora.csdiffat15 is not None


def test_descriptive_clause_includes_disclaimer() -> None:
    reset_champion_profile_stats_state()
    clause = format_descriptive_stats_clause(
        "Fiora",
        "TOP",
        caller="champion_profile_stats",
        role_fr="top",
        context="counter",
    )
    assert clause is not None
    assert DESCRIPTIVE_DISCLAIMER in clause
    assert "historiquement" in clause


def test_assert_descriptive_use_only_blocks_scoring_modules() -> None:
    try:
        assert_descriptive_use_only("predict_draft")
        blocked = False
    except RuntimeError:
        blocked = True
    assert blocked
    assert "predict_draft" not in ALLOWED_DESCRIPTIVE_CALLERS


def test_predict_draft_module_does_not_import_profile_stats() -> None:
    """Garde-fou : predict_draft ne doit pas importer champion_profile_stats."""
    source = Path("predict_draft.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
    assert "champion_profile_stats" not in imported_modules


def test_enrich_predict_response_adds_synergy_explanation() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()
    reset_champion_profile_stats_state()

    raw = pd.predict_draft(BLUE, RED, patch=PATCH)
    enriched = enrich_predict_response_descriptions(raw)

    for side in ("blue", "red"):
        explanation = enriched[side]["synergy_insight"]["explanation"]
        assert explanation
        assert enriched[side]["score_synergie"] == raw[side]["score_synergie"]
