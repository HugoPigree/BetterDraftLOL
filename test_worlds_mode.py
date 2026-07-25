"""Tests pour le mode Worlds."""

from __future__ import annotations

import json
from pathlib import Path

from match_simulator import compute_final_win_probability, simulate_match
from worlds_teams import build_player_team, create_bracket, load_pro_teams


def test_load_pro_teams_has_seven_entries():
    teams = load_pro_teams()
    assert len(teams) >= 7


def test_create_bracket_has_seven_matches():
    player = build_player_team(
        team_name="Test Esports",
        coach_name="Coach",
        roster={
            "TOP": "A",
            "JUNGLE": "B",
            "MIDDLE": "C",
            "BOTTOM": "D",
            "UTILITY": "E",
        },
    )
    opponents = load_pro_teams()[:7]
    bracket = create_bracket(player, opponents, seed=42)
    assert len(bracket) == 7
    assert bracket[0]["id"] == "qf1"


def test_simulate_match_favors_draft_winner():
    high_draft_wins = 0
    low_draft_wins = 0
    for seed in range(50):
        high = simulate_match(
            player_side="blue",
            player_team_name="Player",
            opponent_team_name="T1",
            draft_blue_win_prob=0.72,
            player_roster_power=0.5,
            opponent_roster_power=0.55,
            seed=seed,
        )
        low = simulate_match(
            player_side="blue",
            player_team_name="Player",
            opponent_team_name="T1",
            draft_blue_win_prob=0.28,
            player_roster_power=0.5,
            opponent_roster_power=0.55,
            seed=seed + 1000,
        )
        high_draft_wins += int(high["player_wins"])
        low_draft_wins += int(low["player_wins"])
    assert high_draft_wins > low_draft_wins
    assert high_draft_wins / 50 >= 0.45


def test_compute_final_win_probability_clamped():
    value = compute_final_win_probability(
        player_side="blue",
        draft_blue_win_prob=0.95,
        noise=1.0,
    )
    assert 0.12 <= value <= 0.88


def test_worlds_teams_json_valid():
    path = Path("data/worlds_teams.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(payload["teams"]) == 7


def test_resolve_soloq_patch_fallback():
    from predict_draft import resolve_soloq_patch, soloq_file_for_patch

    resolved = resolve_soloq_patch("14.14")
    assert resolved in {"latest", "16.13"}
    assert soloq_file_for_patch("14.14").exists()
