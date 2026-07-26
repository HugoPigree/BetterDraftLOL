"""Tests mode carrière LEC."""

from __future__ import annotations

from lec_season import (
    build_playoff_bracket,
    build_standings,
    generate_round_robin_schedule,
    get_next_player_fixture,
    load_lec_teams,
    mark_player_fixtures,
    record_fixture_result,
    resolve_week_npc_matches,
    simulate_npc_fixture,
    start_lec_season,
)


def test_load_lec_teams_has_ten_teams():
    teams = load_lec_teams()
    assert len(teams) == 10
    assert any(team["id"] == "g2" for team in teams)


def test_round_robin_schedule_shape():
    team_ids = [f"t{i}" for i in range(10)]
    fixtures = generate_round_robin_schedule(team_ids, seed=42)
    assert len(fixtures) == 45
    assert len({fixture["week"] for fixture in fixtures}) == 9
    for week in range(1, 10):
        week_fixtures = [fixture for fixture in fixtures if fixture["week"] == week]
        assert len(week_fixtures) == 5


def test_player_gets_nine_regular_matches():
    season = start_lec_season(
        team_name="Neon Dragons",
        coach_name="Coach",
        roster={
            "TOP": "Top",
            "JUNGLE": "Jgl",
            "MIDDLE": "Mid",
            "BOTTOM": "Adc",
            "UTILITY": "Sup",
        },
        replace_team_id="sk",
        seed=7,
    )
    player_matches = [fixture for fixture in season["fixtures"] if fixture["is_player_match"]]
    assert len(player_matches) == 9


def test_standings_update_after_results():
    season = start_lec_season(
        team_name="Neon Dragons",
        coach_name="Coach",
        roster={
            "TOP": "Top",
            "JUNGLE": "Jgl",
            "MIDDLE": "Mid",
            "BOTTOM": "Adc",
            "UTILITY": "Sup",
        },
        seed=3,
    )
    fixtures = season["fixtures"]
    mark_player_fixtures(fixtures, "player")
    first_week = [fixture for fixture in fixtures if fixture["week"] == 1]
    teams_by_id = {team["id"]: team for team in season["teams"]}
    for fixture in first_week:
        simulate_npc_fixture(fixture, teams_by_id, seed=11)

    standings = build_standings(fixtures, season["teams"])
    assert len(standings) == 10
    assert sum(row["wins"] + row["losses"] for row in standings) == len(first_week) * 2


def test_record_player_result_and_next_fixture():
    season = start_lec_season(
        team_name="Neon Dragons",
        coach_name="Coach",
        roster={
            "TOP": "Top",
            "JUNGLE": "Jgl",
            "MIDDLE": "Mid",
            "BOTTOM": "Adc",
            "UTILITY": "Sup",
        },
        seed=5,
    )
    fixtures = season["fixtures"]
    next_fixture = get_next_player_fixture(fixtures, "player")
    assert next_fixture is not None
    winner = next_fixture["team_a_id"] if next_fixture["team_a_id"] == "player" else next_fixture["team_b_id"]
    record_fixture_result(fixtures, next_fixture["id"], winner)
    resolve_week_npc_matches(fixtures, season["teams"], next_fixture["week"], seed=99)

    next_after = get_next_player_fixture(fixtures, "player")
    assert next_after is None or next_after["week"] >= next_fixture["week"]


def test_playoff_bracket_top_six():
    season = start_lec_season(
        team_name="Neon Dragons",
        coach_name="Coach",
        roster={
            "TOP": "Top",
            "JUNGLE": "Jgl",
            "MIDDLE": "Mid",
            "BOTTOM": "Adc",
            "UTILITY": "Sup",
        },
        seed=1,
    )
    fixtures = season["fixtures"]
    teams_by_id = {team["id"]: team for team in season["teams"]}
    for fixture in fixtures:
        simulate_npc_fixture(fixture, teams_by_id, seed=fixture["id"].__hash__() & 0xFFFF)

    standings = build_standings(fixtures, season["teams"])
    bracket = build_playoff_bracket(standings, season["teams"])
    assert len(bracket) == 5
    assert bracket[0]["team_a"]["team"]["playoff_seed"] == 3
