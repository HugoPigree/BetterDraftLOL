"""Tests meta et bot carrière."""

from __future__ import annotations

from career_draft_bot import choose_career_bot_action
from career_meta import generate_career_universe, get_career_patch_for_week, patch_index_for_week
from lec_season import start_lec_season


def test_generate_career_universe_deterministic():
    teams = [{"id": "g2", "roster": {"TOP": "A", "JUNGLE": "B", "MIDDLE": "C", "BOTTOM": "D", "UTILITY": "E"}}]
    first = generate_career_universe(teams, seed=42)
    second = generate_career_universe(teams, seed=42)
    assert first == second
    assert first["team_identities"]["g2"]["label"]
    assert len(first["team_profiles"]["g2"]) == 5


def test_patch_rotates_every_two_weeks():
    assert patch_index_for_week(1) == patch_index_for_week(2)
    assert patch_index_for_week(3) == patch_index_for_week(4)
    assert patch_index_for_week(1) != patch_index_for_week(3)


def test_start_lec_season_includes_career_universe():
    season = start_lec_season(
        team_name="Test Team",
        coach_name="Coach",
        roster={
            "TOP": "Top",
            "JUNGLE": "Jgl",
            "MIDDLE": "Mid",
            "BOTTOM": "Adc",
            "UTILITY": "Sup",
        },
        seed=99,
    )
    assert season["career_universe"] is not None
    assert "patch" in season["career_universe"]
    assert "g2" in season["career_universe"]["team_identities"]


def test_career_bot_pick_is_available():
    universe = generate_career_universe(
        [{"id": "kc", "roster": {"TOP": "A", "JUNGLE": "B", "MIDDLE": "C", "BOTTOM": "D", "UTILITY": "E"}}],
        seed=7,
    )
    move = choose_career_bot_action(
        action_type="ban",
        bot_side="red",
        bot_picks=[],
        opponent_picks=[],
        available_champions=["Ahri", "Vi", "Lucian", "Nautilus", "Gnar"],
        team_identity=universe["team_identities"]["kc"],
        team_profiles=universe["team_profiles"]["kc"],
        patch=universe["patch"],
        seed=123,
    )
    assert move["action"] == "ban"
    assert move["champion"] in {"Ahri", "Vi", "Lucian", "Nautilus", "Gnar"}


def test_career_bot_varies_with_seed():
    universe = generate_career_universe(
        [{"id": "g2", "roster": {"TOP": "A", "JUNGLE": "B", "MIDDLE": "C", "BOTTOM": "D", "UTILITY": "E"}}],
        seed=11,
    )
    pool = ["Ahri", "Vi", "Lucian", "Nautilus", "Gnar", "Renekton", "Leona", "Jinx"]
    moves = {
        choose_career_bot_action(
            action_type="ban",
            bot_side="red",
            bot_picks=[],
            opponent_picks=[],
            available_champions=pool,
            team_identity=universe["team_identities"]["g2"],
            team_profiles=universe["team_profiles"]["g2"],
            patch=get_career_patch_for_week(universe["universe_seed"], week=1),
            seed=seed,
        )["champion"]
        for seed in range(20, 35)
    }
    assert len(moves) >= 2


def test_preferred_picks_loaded_from_file():
    universe = generate_career_universe(
        [{"id": "g2", "roster": {"TOP": "A", "JUNGLE": "B", "MIDDLE": "C", "BOTTOM": "D", "UTILITY": "E"}}],
        seed=1,
    )
    mid = next(item for item in universe["team_profiles"]["g2"] if item["role"] == "MIDDLE")
    assert mid["signature_picks"]
    assert "Ahri" in mid["signature_picks"]
    assert universe["team_preferred_picks"]["g2"]


def test_signature_picks_stable_when_patch_changes():
    from career_meta import refresh_career_universe_week

    team = {"id": "kc", "roster": {"TOP": "A", "JUNGLE": "B", "MIDDLE": "C", "BOTTOM": "D", "UTILITY": "E"}}
    universe = generate_career_universe([team], seed=5)
    refreshed = refresh_career_universe_week(universe, [team], week=5)
    before = universe["team_profiles"]["kc"]
    after = refreshed["team_profiles"]["kc"]
    for role in ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"):
        assert next(p for p in before if p["role"] == role)["signature_picks"] == next(
            p for p in after if p["role"] == role
        )["signature_picks"]


def test_career_bot_first_pick_not_always_identical():
    universe = generate_career_universe(
        [{"id": "mkoi", "roster": {"TOP": "A", "JUNGLE": "B", "MIDDLE": "C", "BOTTOM": "D", "UTILITY": "E"}}],
        seed=3,
    )
    pool = universe["patch"]["viable_by_role"]["TOP"] + ["Aatrox", "Sion", "Ornn"]
    picks = {
        choose_career_bot_action(
            action_type="pick",
            bot_side="red",
            bot_picks=[],
            opponent_picks=[],
            available_champions=sorted(set(pool)),
            team_identity=universe["team_identities"]["mkoi"],
            team_profiles=universe["team_profiles"]["mkoi"],
            patch=universe["patch"],
            seed=seed,
        )["champion"]
        for seed in range(100, 130)
    }
    assert len(picks) >= 2
