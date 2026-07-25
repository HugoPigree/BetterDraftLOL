"""Simulation de match post-draft — timeline détaillée avec rosters."""

from __future__ import annotations

import random
from typing import Any, Literal

Side = Literal["blue", "red"]
Roster = dict[str, str]

DRAFT_WEIGHT = 0.80
ROSTER_WEIGHT = 0.15
NOISE_WEIGHT = 0.05
MIN_WIN_PROB = 0.12
MAX_WIN_PROB = 0.88

ROLE_ORDER = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def compute_final_win_probability(
    *,
    player_side: Side,
    draft_blue_win_prob: float,
    player_roster_power: float = 0.5,
    opponent_roster_power: float = 0.5,
    noise: float,
) -> float:
    player_draft_prob = (
        draft_blue_win_prob if player_side == "blue" else 1.0 - draft_blue_win_prob
    )
    roster_delta = (player_roster_power - opponent_roster_power) * 0.5 + 0.5
    blended = (
        DRAFT_WEIGHT * player_draft_prob
        + ROSTER_WEIGHT * roster_delta
        + NOISE_WEIGHT * noise
    )
    return clamp(blended, MIN_WIN_PROB, MAX_WIN_PROB)


def _player(roster: Roster, role: str, fallback: str = "Joueur") -> str:
    return roster.get(role) or fallback


def _build_timeline(
    *,
    winner_side: Side,
    loser_side: Side,
    winner_name: str,
    loser_name: str,
    winner_roster: Roster,
    loser_roster: Roster,
    rng: random.Random,
) -> list[dict[str, Any]]:
    w_top = _player(winner_roster, "TOP")
    w_jgl = _player(winner_roster, "JUNGLE")
    w_mid = _player(winner_roster, "MIDDLE")
    w_adc = _player(winner_roster, "BOTTOM")
    w_sup = _player(winner_roster, "UTILITY")
    l_top = _player(loser_roster, "TOP")
    l_jgl = _player(loser_roster, "JUNGLE")
    l_mid = _player(loser_roster, "MIDDLE")
    l_adc = _player(loser_roster, "BOTTOM")
    l_sup = _player(loser_roster, "UTILITY")

    early_pool = [
        (
            "early",
            f"{w_jgl} pathing vers bot — prio wave pour {winner_name}.",
        ),
        (
            "early",
            f"First blood : {w_mid} puni {l_mid} level 2, avantage mid pour {winner_name}.",
        ),
        (
            "early",
            f"{w_top} trade favorable top vs {l_top}, {winner_name} contrôle la side.",
        ),
        (
            "early",
            f"{l_jgl} tente un gank bot mais {w_sup} ward clean — rien pour {loser_name}.",
        ),
    ]
    mid_pool = [
        (
            "mid",
            f"Herald pour {winner_name} : {w_jgl} + {w_top} convertissent la plate.",
        ),
        (
            "mid",
            f"Teamfight mid : {w_mid} trouve l'angle, {winner_name} remporte l'échange 3 pour 1.",
        ),
        (
            "mid",
            f"Drake pour {winner_name} — {w_adc} sécurise l'objectif sous pression de {l_sup}.",
        ),
        (
            "mid",
            f"{l_adc} outplay en 2v2 bot mais {w_sup} roam mid sauve {w_mid}.",
        ),
        (
            "mid",
            f"Pick off {l_jgl} dans la jungle, {winner_name} ouvre la map.",
        ),
    ]
    late_pool = [
        (
            "late",
            f"{winner_name} pose la vision Baron — {l_jgl} ne peut pas contest.",
        ),
        (
            "late",
            f"Baron rush {winner_name} : {w_adc} DPS insane, {l_sup} peel parfait.",
        ),
        (
            "late",
            f"Teamfight décisive : {w_mid} flash engage, {winner_name} ace.",
        ),
        (
            "late",
            f"{l_top} split push stoppé par {w_jgl}, {winner_name} force le Nashor.",
        ),
        (
            "late",
            f"Siege mid : {w_adc} destroy les inhibs, {loser_name} crack.",
        ),
    ]

    loser_early = [
        (
            "early",
            f"{l_jgl} gank top réussi — first blood sur {w_top}, {loser_name} ouvre la game.",
        ),
        (
            "early",
            f"{l_mid} solo kill sur {w_mid}, tempo mid pour {loser_name}.",
        ),
    ]
    loser_mid = [
        (
            "mid",
            f"Drake volé par {l_jgl} — {loser_name} reprend le tempo objectifs.",
        ),
        (
            "mid",
            f"Teamfight mid : {l_adc} carry le fight pour {loser_name}.",
        ),
    ]

    rng.shuffle(early_pool)
    rng.shuffle(mid_pool)
    rng.shuffle(late_pool)
    rng.shuffle(loser_early)
    rng.shuffle(loser_mid)

    minutes = [4, 8, 13, 17, 22, 26, 31, 35]
    scripted: list[tuple[str, str, Side]] = [
        (early_pool[0][0], early_pool[0][1], winner_side),
        (loser_early[0][0], loser_early[0][1], loser_side),
        (mid_pool[0][0], mid_pool[0][1], winner_side),
        (loser_mid[0][0], loser_mid[0][1], loser_side),
        (mid_pool[1][0], mid_pool[1][1], winner_side),
        (late_pool[0][0], late_pool[0][1], winner_side),
        (late_pool[1][0], late_pool[1][1], winner_side),
        (late_pool[2][0], late_pool[2][1], winner_side),
    ]

    timeline: list[dict[str, Any]] = []
    for minute, (phase, text, side) in zip(minutes, scripted):
        timeline.append(
            {
                "minute": minute,
                "phase": phase,
                "side": side,
                "text": text,
            }
        )

    timeline.append(
        {
            "minute": 38,
            "phase": "late",
            "side": winner_side,
            "text": (
                f"Nexus de {loser_name} tombe — {w_mid} et {w_adc} "
                f"clôturent la game pour {winner_name}."
            ),
        }
    )
    return timeline


def simulate_match(
    *,
    player_side: Side,
    player_team_name: str,
    opponent_team_name: str,
    draft_blue_win_prob: float,
    player_roster: Roster | None = None,
    opponent_roster: Roster | None = None,
    player_roster_power: float = 0.5,
    opponent_roster_power: float = 0.55,
    seed: int | None = None,
) -> dict[str, Any]:
    rng = random.Random(seed)
    noise = rng.random()
    player_win_prob = compute_final_win_probability(
        player_side=player_side,
        draft_blue_win_prob=draft_blue_win_prob,
        player_roster_power=player_roster_power,
        opponent_roster_power=opponent_roster_power,
        noise=noise,
    )
    player_wins = rng.random() < player_win_prob

    default_roster = {role: role.title() for role in ROLE_ORDER}
    player_roster = player_roster or default_roster
    opponent_roster = opponent_roster or default_roster

    if player_wins:
        winner_side: Side = player_side
        winner_name = player_team_name
        loser_side: Side = "red" if player_side == "blue" else "blue"
        loser_name = opponent_team_name
        winner_roster = player_roster
        loser_roster = opponent_roster
    else:
        winner_side = "red" if player_side == "blue" else "blue"
        winner_name = opponent_team_name
        loser_side = player_side
        loser_name = player_team_name
        winner_roster = opponent_roster
        loser_roster = player_roster

    blue_win_prob = player_win_prob if player_side == "blue" else 1.0 - player_win_prob
    events = _build_timeline(
        winner_side=winner_side,
        loser_side=loser_side,
        winner_name=winner_name,
        loser_name=loser_name,
        winner_roster=winner_roster,
        loser_roster=loser_roster,
        rng=rng,
    )

    return {
        "player_wins": player_wins,
        "player_win_probability": round(player_win_prob, 4),
        "draft_blue_win_probability": round(draft_blue_win_prob, 4),
        "winner_side": winner_side,
        "winner_team_name": winner_name,
        "loser_team_name": loser_name,
        "blue_win_probability": round(blue_win_prob, 4),
        "events": events,
        "game_length_minutes": events[-1]["minute"] if events else 30,
    }
