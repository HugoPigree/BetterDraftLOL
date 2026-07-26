"""Tests pour le mode Worlds."""

from __future__ import annotations

import json
import random
from pathlib import Path

from match_simulator import (
    MAX_WIN_PROB,
    MIN_WIN_PROB,
    adjust_phase_probability,
    compute_final_win_probability,
    compute_phase_advantages,
    determine_match_winner,
    pts_to_phase_advantage,
    resolve_phase_outcome,
    resolve_simulation_phase,
    simulate_match,
    start_simulation,
)
from worlds_teams import build_player_team, create_bracket, load_pro_teams


def _strong_bot_prediction(*, draft_blue: float = 0.35) -> dict:
    return {
        "blue_win_probability": draft_blue,
        "bot_lane_matchup": {
            "blue_champions": ["Jinx", "Lulu"],
            "red_champions": ["Caitlyn", "Lux"],
            "blue_win_probability": 0.65,
            "games": 120,
            "is_fallback": False,
            "method": "measured",
        },
        "jungle_support_matchup": {
            "blue_champions": ["LeeSin", "Nami"],
            "red_champions": ["Vi", "Leona"],
            "blue_win_probability": 0.52,
            "games": 80,
            "is_fallback": False,
            "method": "measured",
        },
        "blue": {"score_final": 52.0, "score_synergie": 0.54},
        "red": {"score_final": 48.0, "score_synergie": 0.49},
    }


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
    assert MIN_WIN_PROB <= value <= MAX_WIN_PROB


def test_worlds_teams_json_valid():
    path = Path("data/worlds_teams.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(payload["teams"]) == 7


def test_early_engage_beats_temporize_with_bot_lane_advantage():
    base = compute_final_win_probability(
        player_side="blue",
        draft_blue_win_prob=0.35,
        noise=0.5,
    )
    early_adv = pts_to_phase_advantage(15.0)
    engage_wins = 0
    tempo_wins = 0
    runs = 200
    for seed in range(runs):
        rng = random.Random(seed)
        engage_prob = adjust_phase_probability(
            base=base,
            phase_advantage=early_adv,
            choice="engage",
            noise=0.5,
        )
        tempo_prob = adjust_phase_probability(
            base=base,
            phase_advantage=early_adv,
            choice="temporize",
            noise=0.5,
        )
        engage_wins += int(rng.random() < engage_prob)
        tempo_wins += int(rng.random() < tempo_prob)
    assert engage_wins > tempo_wins
    assert MIN_WIN_PROB <= engage_prob <= MAX_WIN_PROB
    assert MIN_WIN_PROB <= tempo_prob <= MAX_WIN_PROB


def test_phase_probability_stays_clamped_with_extremes():
    base = compute_final_win_probability(
        player_side="blue",
        draft_blue_win_prob=0.95,
        noise=1.0,
    )
    for choice in ("engage", "temporize"):
        value = adjust_phase_probability(
            base=base,
            phase_advantage=0.35,
            choice=choice,  # type: ignore[arg-type]
            noise=1.0,
        )
        assert MIN_WIN_PROB <= value <= MAX_WIN_PROB


def test_bad_draft_can_still_win_with_favorable_decisions():
    prediction = _strong_bot_prediction(draft_blue=0.28)
    wins = 0
    runs = 120
    for seed in range(runs):
        started = start_simulation(
            player_side="blue",
            player_team_name="Player",
            opponent_team_name="T1",
            draft_blue_win_prob=0.28,
            prediction=prediction,
            seed=seed,
        )
        resolve_simulation_phase(
            simulation_id=started["simulation_id"],
            phase="early",
            choice="engage",
        )
        final = resolve_simulation_phase(
            simulation_id=started["simulation_id"],
            phase="mid",
            choice="engage",
        )
        wins += int(final["player_wins"])
    assert wins >= 8
    assert wins / runs < 0.75


def test_majority_rule_and_tiebreak_on_base():
    rng = random.Random(0)
    assert determine_match_winner(
        phase_results={"early": True, "mid": True, "late": False},
        base=0.4,
        rng=rng,
    )
    assert not determine_match_winner(
        phase_results={"early": False, "mid": False, "late": False},
        base=0.9,
        rng=random.Random(1),
    )
    tiebreak_wins = sum(
        int(
            determine_match_winner(
                phase_results={"early": True, "mid": False, "late": False},
                base=0.85,
                rng=random.Random(seed),
            )
        )
        for seed in range(100)
    )
    assert tiebreak_wins >= 60


def test_sequential_simulation_returns_decision_events():
    prediction = _strong_bot_prediction(draft_blue=0.55)
    started = start_simulation(
        player_side="blue",
        player_team_name="Player",
        opponent_team_name="T1",
        draft_blue_win_prob=0.55,
        prediction=prediction,
        seed=123,
    )
    token = started["simulation_token"]
    mid = resolve_simulation_phase(
        simulation_token=token,
        phase="early",
        choice="temporize",
    )
    assert mid["simulation_token"]
    final = resolve_simulation_phase(
        simulation_token=mid["simulation_token"],
        phase="mid",
        choice="engage",
    )
    assert final["status"] == "complete"
    events = final["events"]
    assert any(event.get("type") == "decision" for event in events)
    assert any(event.get("type") == "phase_result" for event in events)
    assert sum(1 for event in events if event.get("type") == "flavor") >= 9


def test_compute_phase_advantages_uses_bot_lane():
    prediction = _strong_bot_prediction()
    advantages = compute_phase_advantages(prediction, player_side="blue")
    assert advantages["early"] > 0.05


def test_resolve_soloq_patch_fallback():
    from predict_draft import resolve_soloq_patch, soloq_file_for_patch

    resolved = resolve_soloq_patch("14.14")
    assert resolved in {"latest", "16.13"}
    assert soloq_file_for_patch("14.14").exists()
