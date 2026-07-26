"""Mode carrière LEC — calendrier, classement et simulation NPC."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from worlds_teams import ROLES_ORDER, build_player_team

DEFAULT_LEC_TEAMS_JSON = Path("data/lec_teams.json")
PLAYOFFS_SIZE = 6
WORLDS_SLOTS = 3


def load_lec_teams(json_path: Path = DEFAULT_LEC_TEAMS_JSON) -> list[dict[str, Any]]:
    if not json_path.exists():
        raise FileNotFoundError(f"Fichier équipes LEC introuvable: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    teams = payload.get("teams") or []
    if len(teams) != 10:
        raise ValueError("Le mode LEC requiert exactement 10 équipes.")
    return teams


def load_lec_meta(json_path: Path = DEFAULT_LEC_TEAMS_JSON) -> dict[str, Any]:
    if not json_path.exists():
        raise FileNotFoundError(f"Fichier équipes LEC introuvable: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    return {
        "season_label": payload.get("season_label", "LEC 2025"),
        "format": payload.get("format") or {},
    }


def _team_lookup(teams: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {team["id"]: team for team in teams}


def generate_round_robin_schedule(
    team_ids: list[str],
    *,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """Round-robin à 10 équipes : 9 semaines, 5 matchs par semaine."""
    if len(team_ids) != 10:
        raise ValueError("Le calendrier LEC requiert 10 équipes.")

    rng = random.Random(seed)
    rotating = list(team_ids[1:])
    rng.shuffle(rotating)
    fixed = team_ids[0]
    order = [fixed, *rotating]

    fixtures: list[dict[str, Any]] = []
    fixture_index = 0

    for week in range(1, 10):
        week_matches: list[tuple[str, str]] = []
        for slot in range(5):
            home = order[slot]
            away = order[9 - slot]
            week_matches.append((home, away))

        for home_id, away_id in week_matches:
            fixture_index += 1
            fixtures.append(
                {
                    "id": f"lec-w{week}-m{fixture_index}",
                    "week": week,
                    "stage": "regular",
                    "format": "bo1",
                    "round_label": f"Semaine {week} — LEC Bo1",
                    "team_a_id": home_id,
                    "team_b_id": away_id,
                    "winner_id": None,
                    "is_player_match": False,
                    "played": False,
                }
            )

        order = [order[0], order[9], *order[1:9]]

    return fixtures


def mark_player_fixtures(fixtures: list[dict[str, Any]], player_team_id: str) -> None:
    for fixture in fixtures:
        involves_player = player_team_id in (fixture["team_a_id"], fixture["team_b_id"])
        fixture["is_player_match"] = involves_player


def simulate_npc_fixture(
    fixture: dict[str, Any],
    teams_by_id: dict[str, dict[str, Any]],
    *,
    seed: int | None = None,
) -> str:
    rng = random.Random(seed)
    team_a = teams_by_id[fixture["team_a_id"]]
    team_b = teams_by_id[fixture["team_b_id"]]
    power_a = float(team_a.get("power_rating", 0.5))
    power_b = float(team_b.get("power_rating", 0.5))
    noise = rng.uniform(-0.12, 0.12)
    win_prob_a = max(0.08, min(0.92, 0.5 + (power_a - power_b) * 0.55 + noise))
    winner_id = fixture["team_a_id"] if rng.random() < win_prob_a else fixture["team_b_id"]
    fixture["winner_id"] = winner_id
    fixture["played"] = True
    return winner_id


def resolve_week_npc_matches(
    fixtures: list[dict[str, Any]],
    teams: list[dict[str, Any]],
    week: int,
    *,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    teams_by_id = _team_lookup(teams)
    rng = random.Random(seed)
    updated: list[dict[str, Any]] = []

    for fixture in fixtures:
        if fixture["week"] != week or fixture.get("played"):
            continue
        if fixture.get("is_player_match"):
            continue
        simulate_npc_fixture(fixture, teams_by_id, seed=rng.randint(0, 2_000_000_000))
        updated.append(fixture)

    return updated


def build_standings(
    fixtures: list[dict[str, Any]],
    teams: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {
        team["id"]: {
            "team_id": team["id"],
            "wins": 0,
            "losses": 0,
            "head_to_head": {},
        }
        for team in teams
    }

    for fixture in fixtures:
        if not fixture.get("played") or not fixture.get("winner_id"):
            continue
        winner_id = fixture["winner_id"]
        loser_id = (
            fixture["team_b_id"]
            if winner_id == fixture["team_a_id"]
            else fixture["team_a_id"]
        )
        records[winner_id]["wins"] += 1
        records[loser_id]["losses"] += 1
        h2h = records[winner_id]["head_to_head"]
        h2h[loser_id] = h2h.get(loser_id, 0) + 1

    standings: list[dict[str, Any]] = []
    for team in teams:
        team_id = team["id"]
        record = records[team_id]
        played = record["wins"] + record["losses"]
        standings.append(
            {
                "team_id": team_id,
                "team_name": team["name"],
                "short_name": team.get("short_name", team["name"][:3].upper()),
                "brand_color": team.get("brand_color", "#888888"),
                "wins": record["wins"],
                "losses": record["losses"],
                "played": played,
                "win_rate": round(record["wins"] / played, 3) if played else 0.0,
                "is_player_team": bool(team.get("is_player_team")),
            }
        )

    standings.sort(
        key=lambda row: (
            -row["wins"],
            row["losses"],
            -row["win_rate"],
        )
    )

    for index, row in enumerate(standings, start=1):
        row["rank"] = index
        row["playoffs_cutoff"] = index <= PLAYOFFS_SIZE
        row["worlds_cutoff"] = index <= WORLDS_SLOTS

    return standings


def get_next_player_fixture(fixtures: list[dict[str, Any]], player_team_id: str) -> dict[str, Any] | None:
    player_fixtures = [
        fixture
        for fixture in fixtures
        if fixture.get("is_player_match") and not fixture.get("played")
    ]
    if not player_fixtures:
        return None
    return min(player_fixtures, key=lambda item: (item["week"], item["id"]))


def record_fixture_result(
    fixtures: list[dict[str, Any]],
    fixture_id: str,
    winner_id: str,
) -> dict[str, Any]:
    for fixture in fixtures:
        if fixture["id"] != fixture_id:
            continue
        if winner_id not in (fixture["team_a_id"], fixture["team_b_id"]):
            raise ValueError("Le vainqueur doit être l'une des deux équipes.")
        fixture["winner_id"] = winner_id
        fixture["played"] = True
        return fixture
    raise ValueError(f"Match introuvable: {fixture_id}")


def build_playoff_bracket(
    standings: list[dict[str, Any]],
    teams: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Playoffs simplifiés top 6 — double élimination light en Bo3."""
    qualified = [row for row in standings if row["rank"] <= PLAYOFFS_SIZE]
    if len(qualified) < PLAYOFFS_SIZE:
        raise ValueError("Classement incomplet pour les playoffs.")

    seed_map = {row["team_id"]: row["rank"] for row in qualified}
    teams_by_id = _team_lookup(teams)

    def team_payload(team_id: str) -> dict[str, Any]:
        team = dict(teams_by_id[team_id])
        team["playoff_seed"] = seed_map[team_id]
        return team

    return [
        {
            "id": "po-qf1",
            "round": "quarter",
            "round_label": "Playoffs — Quart de finale Bo3",
            "format": "bo3",
            "team_a": {"team": team_payload(qualified[2]["team_id"]), "source_match_id": None},
            "team_b": {"team": team_payload(qualified[5]["team_id"]), "source_match_id": None},
            "winner_id": None,
        },
        {
            "id": "po-qf2",
            "round": "quarter",
            "round_label": "Playoffs — Quart de finale Bo3",
            "format": "bo3",
            "team_a": {"team": team_payload(qualified[3]["team_id"]), "source_match_id": None},
            "team_b": {"team": team_payload(qualified[4]["team_id"]), "source_match_id": None},
            "winner_id": None,
        },
        {
            "id": "po-sf1",
            "round": "semi",
            "round_label": "Playoffs — Demi-finale Bo3",
            "format": "bo3",
            "team_a": {"team": team_payload(qualified[0]["team_id"]), "source_match_id": None},
            "team_b": {"team": None, "source_match_id": "po-qf1"},
            "winner_id": None,
        },
        {
            "id": "po-sf2",
            "round": "semi",
            "round_label": "Playoffs — Demi-finale Bo3",
            "format": "bo3",
            "team_a": {"team": team_payload(qualified[1]["team_id"]), "source_match_id": None},
            "team_b": {"team": None, "source_match_id": "po-qf2"},
            "winner_id": None,
        },
        {
            "id": "po-final",
            "round": "final",
            "round_label": "Finale LEC Bo5",
            "format": "bo5",
            "team_a": {"team": None, "source_match_id": "po-sf1"},
            "team_b": {"team": None, "source_match_id": "po-sf2"},
            "winner_id": None,
        },
    ]


def start_lec_season(
    *,
    team_name: str,
    coach_name: str,
    roster: dict[str, str],
    replace_team_id: str | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    lec_teams = load_lec_teams()
    meta = load_lec_meta()

    player_team = build_player_team(
        team_name=team_name,
        coach_name=coach_name,
        roster=roster,
    )
    player_team["region"] = "LEC"
    player_team["short_name"] = team_name.strip()[:4].upper() or "YOU"
    player_team["brand_color"] = "#9B59B6"
    player_team["power_rating"] = 0.5

    league_teams: list[dict[str, Any]] = []
    replaced = False
    for team in lec_teams:
        if replace_team_id and team["id"] == replace_team_id:
            league_teams.append({**player_team, "id": "player", "is_player_team": True})
            replaced = True
        else:
            league_teams.append(dict(team))

    if not replaced:
        league_teams[0] = {**player_team, "id": "player", "is_player_team": True}

    team_ids = [team["id"] for team in league_teams]
    fixtures = generate_round_robin_schedule(team_ids, seed=seed)
    mark_player_fixtures(fixtures, "player")

    return {
        "season_label": meta["season_label"],
        "format": meta["format"],
        "teams": league_teams,
        "fixtures": fixtures,
        "standings": build_standings([], league_teams),
        "current_week": 1,
        "story_chapter": 0,
    }


def validate_roster(roster: dict[str, str]) -> None:
    missing = [role for role in ROLES_ORDER if not str(roster.get(role, "")).strip()]
    if missing:
        raise ValueError(f"Roster incomplet, rôles manquants: {', '.join(missing)}")
