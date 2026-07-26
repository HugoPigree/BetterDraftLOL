"""Simulation de match post-draft — phases séquentielles avec décisions interactives."""

from __future__ import annotations

import base64
import json
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

Side = Literal["blue", "red"]
PhaseName = Literal["early", "mid", "late"]
Choice = Literal["engage", "temporize"]
Roster = dict[str, str]

DRAFT_WEIGHT = 0.80
ROSTER_WEIGHT = 0.15
NOISE_WEIGHT = 0.05
PHASE_ADVANTAGE_WEIGHT = 0.15
ENGAGE_BONUS = 0.08
ENGAGE_CAPITALIZE = 0.25
TEMPORIZE_NEUTRAL = 0.51
MIN_WIN_PROB = 0.12
MAX_WIN_PROB = 0.88

ROLE_ORDER = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
DECISION_PHASES: tuple[PhaseName, ...] = ("early", "mid")
SIMULATION_TTL_SECONDS = 1800

_store: dict[str, "SimulationState"] = {}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def sign(value: float) -> float:
    if value > 0:
        return 1.0
    if value < 0:
        return -1.0
    return 0.0


def pts_to_phase_advantage(pts: float) -> float:
    return clamp(pts / 100.0, -0.35, 0.35)


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


def _player_side_prob(blue_prob: float | None, *, player_side: Side) -> float | None:
    if blue_prob is None:
        return None
    return blue_prob if player_side == "blue" else 1.0 - blue_prob


def _matchup_player_advantage(matchup: dict[str, Any] | None, *, player_side: Side) -> float:
    if not matchup or matchup.get("insufficient_data"):
        return 0.0
    player_prob = _player_side_prob(matchup.get("blue_win_probability"), player_side=player_side)
    if player_prob is None:
        return 0.0
    return pts_to_phase_advantage((player_prob - 0.5) * 100.0)


def _score_delta_advantage(player_score: float, opponent_score: float) -> float:
    return pts_to_phase_advantage(player_score - opponent_score)


def _our_team_detail(prediction: dict[str, Any], *, player_side: Side) -> dict[str, Any]:
    return prediction["blue"] if player_side == "blue" else prediction["red"]


def _their_team_detail(prediction: dict[str, Any], *, player_side: Side) -> dict[str, Any]:
    return prediction["red"] if player_side == "blue" else prediction["blue"]


def compute_phase_advantages(
    prediction: dict[str, Any],
    *,
    player_side: Side,
) -> dict[PhaseName, float]:
    bot = prediction.get("bot_lane_matchup")
    js = prediction.get("jungle_support_matchup")
    ours = _our_team_detail(prediction, player_side=player_side)
    theirs = _their_team_detail(prediction, player_side=player_side)

    early = _matchup_player_advantage(bot, player_side=player_side)
    if abs(early) < 1e-6:
        early = _matchup_player_advantage(js, player_side=player_side)

    mid_js = _matchup_player_advantage(js, player_side=player_side)
    mid_syn = _score_delta_advantage(
        float(ours.get("score_synergie", 0.5)),
        float(theirs.get("score_synergie", 0.5)),
    )
    mid = mid_js if abs(mid_js) >= abs(mid_syn) else mid_syn

    late = _score_delta_advantage(
        float(ours.get("score_final", 0.0)),
        float(theirs.get("score_final", 0.0)),
    )
    if abs(late) < 1e-6:
        player_draft = _player_side_prob(
            prediction.get("blue_win_probability", 0.5),
            player_side=player_side,
        )
        late = pts_to_phase_advantage(((player_draft or 0.5) - 0.5) * 100.0)

    return {"early": early, "mid": mid, "late": late}


def adjust_phase_probability(
    *,
    base: float,
    phase_advantage: float,
    choice: Choice | None,
    noise: float,
) -> float:
    phase_prob = base + PHASE_ADVANTAGE_WEIGHT * phase_advantage + NOISE_WEIGHT * noise
    phase_prob = clamp(phase_prob, MIN_WIN_PROB, MAX_WIN_PROB)
    if choice == "engage":
        phase_prob += ENGAGE_BONUS * sign(phase_advantage)
        if phase_advantage > 0:
            phase_prob += ENGAGE_CAPITALIZE * phase_advantage
    elif choice == "temporize":
        phase_prob = TEMPORIZE_NEUTRAL + 0.02 * sign(phase_advantage)
    return clamp(phase_prob, MIN_WIN_PROB, MAX_WIN_PROB)


def resolve_phase_outcome(
    *,
    base: float,
    phase_advantage: float,
    choice: Choice | None,
    rng: random.Random,
) -> tuple[bool, float]:
    noise = rng.random()
    prob = adjust_phase_probability(
        base=base,
        phase_advantage=phase_advantage,
        choice=choice,
        noise=noise,
    )
    return rng.random() < prob, prob


def determine_match_winner(
    *,
    phase_results: dict[PhaseName, bool],
    base: float,
    rng: random.Random,
) -> bool:
    wins = sum(1 for won in phase_results.values() if won)
    if wins >= 2:
        return True
    if wins == 0:
        return False
    return rng.random() < base


def _phase_context_text(phase: PhaseName, *, player_roster: Roster, opponent_roster: Roster) -> str:
    p_adc = _player(player_roster, "BOTTOM")
    p_sup = _player(player_roster, "UTILITY")
    p_jgl = _player(player_roster, "JUNGLE")
    o_adc = _player(opponent_roster, "BOTTOM")
    o_jgl = _player(opponent_roster, "JUNGLE")

    if phase == "early":
        return (
            f"Minute 8 — la wave bot se stack. {p_jgl} est en position de gank "
            f"pendant que {p_adc}/{p_sup} jouent la lane contre {o_adc}. "
            f"Engager maintenant ou temporiser et farm safe ?"
        )
    return (
        f"Minute 22 — tempo mid et objectif en jeu. {p_jgl} peut forcer une "
        f"skirmish pendant que {o_jgl} cherche une ouverture. "
        f"Forcer le fight ou reset et jouer la vision ?"
    )


def _phase_explanation_text(
    phase: PhaseName,
    *,
    phase_advantage: float,
    choice: Choice,
    phase_won: bool,
    prediction: dict[str, Any],
    player_side: Side,
) -> str:
    ours = _our_team_detail(prediction, player_side=player_side)
    theirs = _their_team_detail(prediction, player_side=player_side)
    adv_pts = phase_advantage * 100.0
    direction = "en ta faveur" if phase_advantage > 0.02 else "contre toi" if phase_advantage < -0.02 else "serré"

    if phase == "early":
        bot = prediction.get("bot_lane_matchup") or {}
        blue_champs = bot.get("blue_champions") or []
        red_champs = bot.get("red_champions") or []
        if player_side == "blue":
            duo = " / ".join(blue_champs) if blue_champs else "ton duo bot"
        else:
            duo = " / ".join(red_champs) if red_champs else "ton duo bot"
        signal = f"Le duo bot ({duo}) partait avec un avantage estimé de {adv_pts:+.0f} pts ({direction})."
    elif phase == "mid":
        js = prediction.get("jungle_support_matchup") or {}
        syn_delta = (
            float(ours.get("score_synergie", 0.5)) - float(theirs.get("score_synergie", 0.5))
        ) * 100.0
        signal = (
            f"Jungle/support et cohérence mid game : avantage phase {adv_pts:+.0f} pts "
            f"(Δ synergie {syn_delta:+.1f} pts)."
        )
    else:
        final_delta = float(ours.get("score_final", 0.0)) - float(theirs.get("score_final", 0.0))
        signal = f"Scaling late : Δ score final {final_delta:+.1f} pts ({direction})."

    outcome = "Phase remportée" if phase_won else "Phase perdue"
    choice_hint = (
        "Engager capitalisait sur l'avantage."
        if choice == "engage" and phase_advantage > 0
        else "Temporiser limitait le risque."
        if choice == "temporize"
        else "Engager était agressif compte tenu du contexte."
        if choice == "engage"
        else "Temporiser visait un tempo neutre."
    )
    return f"{signal} {outcome}. {choice_hint}"


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
        ("early", f"{w_jgl} pathing vers bot — prio wave pour {winner_name}."),
        ("early", f"First blood : {w_mid} puni {l_mid} level 2, avantage mid pour {winner_name}."),
        ("early", f"{w_top} trade favorable top vs {l_top}, {winner_name} contrôle la side."),
        ("early", f"{l_jgl} tente un gank bot mais {w_sup} ward clean — rien pour {loser_name}."),
    ]
    mid_pool = [
        ("mid", f"Herald pour {winner_name} : {w_jgl} + {w_top} convertissent la plate."),
        ("mid", f"Teamfight mid : {w_mid} trouve l'angle, {winner_name} remporte l'échange 3 pour 1."),
        ("mid", f"Drake pour {winner_name} — {w_adc} sécurise l'objectif sous pression de {l_sup}."),
        ("mid", f"{l_adc} outplay en 2v2 bot mais {w_sup} roam mid sauve {w_mid}."),
        ("mid", f"Pick off {l_jgl} dans la jungle, {winner_name} ouvre la map."),
    ]
    late_pool = [
        ("late", f"{winner_name} pose la vision Baron — {l_jgl} ne peut pas contest."),
        ("late", f"Baron rush {winner_name} : {w_adc} DPS insane, {l_sup} peel parfait."),
        ("late", f"Teamfight décisive : {w_mid} flash engage, {winner_name} ace."),
        ("late", f"{l_top} split push stoppé par {w_jgl}, {winner_name} force le Nashor."),
        ("late", f"Siege mid : {w_adc} destroy les inhibs, {loser_name} crack."),
    ]
    loser_early = [
        ("early", f"{l_jgl} gank top réussi — first blood sur {w_top}, {loser_name} ouvre la game."),
        ("early", f"{l_mid} solo kill sur {w_mid}, tempo mid pour {loser_name}."),
    ]
    loser_mid = [
        ("mid", f"Drake volé par {l_jgl} — {loser_name} reprend le tempo objectifs."),
        ("mid", f"Teamfight mid : {l_adc} carry le fight pour {loser_name}."),
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
                "type": "flavor",
                "minute": minute,
                "phase": phase,
                "side": side,
                "text": text,
            }
        )

    timeline.append(
        {
            "type": "flavor",
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


def _decision_minute(phase: PhaseName) -> int:
    return 13 if phase == "early" else 26


def _inject_decision_nodes(
    timeline: list[dict[str, Any]],
    *,
    phase_meta: dict[PhaseName, dict[str, Any]],
) -> list[dict[str, Any]]:
    decision_minutes = {_decision_minute(phase) for phase in DECISION_PHASES}
    late_minute = 31
    merged: list[dict[str, Any]] = []

    for event in timeline:
        minute = int(event["minute"])
        if minute == late_minute and "late" in phase_meta:
            late = phase_meta["late"]
            merged.append(
                {
                    "type": "phase_result",
                    "phase": "late",
                    "minute": late_minute,
                    "phase_won": late["phase_won"],
                    "explanation_text": late["explanation_text"],
                    "phase_probability": late["phase_probability"],
                    "auto_resolved": True,
                }
            )
        if minute in decision_minutes:
            phase = "early" if minute == 13 else "mid"
            meta = phase_meta[phase]
            merged.append(
                {
                    "type": "decision",
                    "phase": phase,
                    "minute": minute,
                    "choices": ["engage", "temporize"],
                    "context_text": meta["context_text"],
                    "resolved": meta.get("resolved", False),
                    "player_choice": meta.get("player_choice"),
                    "phase_won": meta.get("phase_won"),
                    "explanation_text": meta.get("explanation_text"),
                    "phase_probability": meta.get("phase_probability"),
                }
            )
        merged.append(event)

    return merged


def _purge_expired_states() -> None:
    now = time.time()
    expired = [
        sim_id
        for sim_id, state in _store.items()
        if now - state.created_at > SIMULATION_TTL_SECONDS
    ]
    for sim_id in expired:
        _store.pop(sim_id, None)


@dataclass
class SimulationState:
    player_side: Side
    player_team_name: str
    opponent_team_name: str
    draft_blue_win_prob: float
    player_roster: Roster
    opponent_roster: Roster
    player_roster_power: float
    opponent_roster_power: float
    prediction: dict[str, Any]
    base: float
    phase_advantages: dict[PhaseName, float]
    rng: random.Random
    phase_results: dict[PhaseName, dict[str, Any]] = field(default_factory=dict)
    pending_phase: PhaseName | None = "early"
    completed: bool = False
    created_at: float = field(default_factory=time.time)


def _serialize_rng(rng: random.Random) -> list[Any]:
    version, internal, gauss = rng.getstate()
    return [version, list(internal), gauss]


def _deserialize_rng(payload: list[Any]) -> random.Random:
    rng = random.Random()
    rng.setstate((payload[0], tuple(payload[1]), payload[2]))
    return rng


def _state_to_payload(state: SimulationState) -> dict[str, Any]:
    return {
        "player_side": state.player_side,
        "player_team_name": state.player_team_name,
        "opponent_team_name": state.opponent_team_name,
        "draft_blue_win_prob": state.draft_blue_win_prob,
        "player_roster": state.player_roster,
        "opponent_roster": state.opponent_roster,
        "player_roster_power": state.player_roster_power,
        "opponent_roster_power": state.opponent_roster_power,
        "prediction": state.prediction,
        "base": state.base,
        "phase_advantages": state.phase_advantages,
        "rng_state": _serialize_rng(state.rng),
        "phase_results": state.phase_results,
        "pending_phase": state.pending_phase,
        "completed": state.completed,
    }


def _state_from_payload(payload: dict[str, Any]) -> SimulationState:
    return SimulationState(
        player_side=payload["player_side"],
        player_team_name=payload["player_team_name"],
        opponent_team_name=payload["opponent_team_name"],
        draft_blue_win_prob=float(payload["draft_blue_win_prob"]),
        player_roster=dict(payload["player_roster"]),
        opponent_roster=dict(payload["opponent_roster"]),
        player_roster_power=float(payload["player_roster_power"]),
        opponent_roster_power=float(payload["opponent_roster_power"]),
        prediction=dict(payload["prediction"]),
        base=float(payload["base"]),
        phase_advantages=dict(payload["phase_advantages"]),
        rng=_deserialize_rng(payload["rng_state"]),
        phase_results=dict(payload.get("phase_results") or {}),
        pending_phase=payload.get("pending_phase"),
        completed=bool(payload.get("completed")),
    )


def encode_simulation_token(state: SimulationState) -> str:
    raw = json.dumps(_state_to_payload(state), separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_simulation_token(token: str) -> SimulationState:
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("Simulation introuvable ou expirée.") from exc
    return _state_from_payload(payload)


def _load_simulation_state(
    *,
    simulation_id: str | None,
    simulation_token: str | None,
) -> SimulationState:
    if simulation_token:
        return decode_simulation_token(simulation_token)
    if simulation_id:
        _purge_expired_states()
        state = _store.get(simulation_id)
        if state is not None:
            return state
    raise ValueError("Simulation introuvable ou expirée.")


def start_simulation(
    *,
    player_side: Side,
    player_team_name: str,
    opponent_team_name: str,
    draft_blue_win_prob: float,
    prediction: dict[str, Any],
    player_roster: Roster | None = None,
    opponent_roster: Roster | None = None,
    player_roster_power: float = 0.5,
    opponent_roster_power: float = 0.55,
    seed: int | None = None,
) -> dict[str, Any]:
    _purge_expired_states()
    rng = random.Random(seed)
    base = compute_final_win_probability(
        player_side=player_side,
        draft_blue_win_prob=draft_blue_win_prob,
        player_roster_power=player_roster_power,
        opponent_roster_power=opponent_roster_power,
        noise=0.5,
    )
    default_roster = {role: role.title() for role in ROLE_ORDER}
    player_roster = player_roster or default_roster
    opponent_roster = opponent_roster or default_roster
    phase_advantages = compute_phase_advantages(prediction, player_side=player_side)

    simulation_id = uuid.uuid4().hex
    state = SimulationState(
        player_side=player_side,
        player_team_name=player_team_name,
        opponent_team_name=opponent_team_name,
        draft_blue_win_prob=draft_blue_win_prob,
        player_roster=player_roster,
        opponent_roster=opponent_roster,
        player_roster_power=player_roster_power,
        opponent_roster_power=opponent_roster_power,
        prediction=prediction,
        base=base,
        phase_advantages=phase_advantages,
        rng=rng,
    )
    _store[simulation_id] = state

    return {
        "simulation_id": simulation_id,
        "simulation_token": encode_simulation_token(state),
        "status": "awaiting_decision",
        "pending_phase": "early",
        "early_context": _phase_context_text(
            "early",
            player_roster=player_roster,
            opponent_roster=opponent_roster,
        ),
        "player_win_probability": round(base, 4),
        "draft_blue_win_probability": round(draft_blue_win_prob, 4),
        "phase_advantages": {k: round(v, 4) for k, v in phase_advantages.items()},
    }


def _build_final_result(state: SimulationState) -> dict[str, Any]:
    player_wins = determine_match_winner(
        phase_results={phase: data["phase_won"] for phase, data in state.phase_results.items()},
        base=state.base,
        rng=state.rng,
    )

    if player_wins:
        winner_side: Side = state.player_side
        winner_name = state.player_team_name
        loser_side: Side = "red" if state.player_side == "blue" else "blue"
        loser_name = state.opponent_team_name
        winner_roster = state.player_roster
        loser_roster = state.opponent_roster
    else:
        winner_side = "red" if state.player_side == "blue" else "blue"
        winner_name = state.opponent_team_name
        loser_side = state.player_side
        loser_name = state.player_team_name
        winner_roster = state.opponent_roster
        loser_roster = state.player_roster

    phase_meta: dict[PhaseName, dict[str, Any]] = {}
    for phase_name in ("early", "mid", "late"):
        data = state.phase_results[phase_name]
        phase_meta[phase_name] = {
            **data,
            "context_text": data.get("context_text")
            or _phase_context_text(
                phase_name,
                player_roster=state.player_roster,
                opponent_roster=state.opponent_roster,
            ),
            "resolved": phase_name in DECISION_PHASES,
        }

    flavor = _build_timeline(
        winner_side=winner_side,
        loser_side=loser_side,
        winner_name=winner_name,
        loser_name=loser_name,
        winner_roster=winner_roster,
        loser_roster=loser_roster,
        rng=state.rng,
    )
    events = _inject_decision_nodes(flavor, phase_meta=phase_meta)
    blue_win_prob = state.base if state.player_side == "blue" else 1.0 - state.base

    return {
        "status": "complete",
        "player_wins": player_wins,
        "player_win_probability": round(state.base, 4),
        "draft_blue_win_probability": round(state.draft_blue_win_prob, 4),
        "winner_side": winner_side,
        "winner_team_name": winner_name,
        "loser_team_name": loser_name,
        "blue_win_probability": round(blue_win_prob, 4),
        "events": events,
        "game_length_minutes": events[-1]["minute"] if events else 30,
        "phases_won": sum(1 for data in state.phase_results.values() if data["phase_won"]),
    }


def resolve_simulation_phase(
    *,
    simulation_id: str | None = None,
    simulation_token: str | None = None,
    phase: PhaseName,
    choice: Choice,
) -> dict[str, Any]:
    state = _load_simulation_state(
        simulation_id=simulation_id,
        simulation_token=simulation_token,
    )
    if state.completed:
        raise ValueError("Simulation déjà terminée.")
    if state.pending_phase != phase:
        raise ValueError(f"Phase attendue : {state.pending_phase}, reçue : {phase}.")

    active_simulation_id = simulation_id or uuid.uuid4().hex

    phase_advantage = state.phase_advantages[phase]
    phase_won, phase_prob = resolve_phase_outcome(
        base=state.base,
        phase_advantage=phase_advantage,
        choice=choice,
        rng=state.rng,
    )
    explanation = _phase_explanation_text(
        phase,
        phase_advantage=phase_advantage,
        choice=choice,
        phase_won=phase_won,
        prediction=state.prediction,
        player_side=state.player_side,
    )
    state.phase_results[phase] = {
        "phase_won": phase_won,
        "phase_probability": round(phase_prob, 4),
        "player_choice": choice,
        "explanation_text": explanation,
        "context_text": _phase_context_text(
            phase,
            player_roster=state.player_roster,
            opponent_roster=state.opponent_roster,
        ),
        "resolved": True,
    }

    if phase == "early":
        state.pending_phase = "mid"
        if simulation_id:
            _store[simulation_id] = state
        return {
            "simulation_id": active_simulation_id,
            "simulation_token": encode_simulation_token(state),
            "status": "awaiting_decision",
            "pending_phase": "mid",
            "resolved_phase": phase,
            "phase_won": phase_won,
            "phase_probability": round(phase_prob, 4),
            "explanation_text": explanation,
            "mid_context": _phase_context_text(
                "mid",
                player_roster=state.player_roster,
                opponent_roster=state.opponent_roster,
            ),
        }

    if phase == "mid":
        late_won, late_prob = resolve_phase_outcome(
            base=state.base,
            phase_advantage=state.phase_advantages["late"],
            choice="engage",
            rng=state.rng,
        )
        state.phase_results["late"] = {
            "phase_won": late_won,
            "phase_probability": round(late_prob, 4),
            "player_choice": None,
            "explanation_text": _phase_explanation_text(
                "late",
                phase_advantage=state.phase_advantages["late"],
                choice="engage",
                phase_won=late_won,
                prediction=state.prediction,
                player_side=state.player_side,
            ),
            "context_text": "",
            "resolved": True,
        }
        state.pending_phase = None
        state.completed = True
        result = _build_final_result(state)
        result["simulation_id"] = active_simulation_id
        result["resolved_phase"] = phase
        result["phase_won"] = phase_won
        result["phase_probability"] = round(phase_prob, 4)
        result["explanation_text"] = explanation
        if simulation_id:
            _store.pop(simulation_id, None)
        return result

    raise ValueError(f"Phase interactive invalide : {phase}")


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
    prediction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compatibilité : résout automatiquement engage/engage puis retourne le résultat final."""
    default_prediction = {
        "blue_win_probability": draft_blue_win_prob,
        "bot_lane_matchup": None,
        "jungle_support_matchup": None,
        "blue": {"score_final": 0.0, "score_synergie": 0.5},
        "red": {"score_final": 0.0, "score_synergie": 0.5},
    }
    started = start_simulation(
        player_side=player_side,
        player_team_name=player_team_name,
        opponent_team_name=opponent_team_name,
        draft_blue_win_prob=draft_blue_win_prob,
        prediction=prediction or default_prediction,
        player_roster=player_roster,
        opponent_roster=opponent_roster,
        player_roster_power=player_roster_power,
        opponent_roster_power=opponent_roster_power,
        seed=seed,
    )
    simulation_id = started["simulation_id"]
    resolve_simulation_phase(simulation_id=simulation_id, phase="early", choice="engage")
    final = resolve_simulation_phase(simulation_id=simulation_id, phase="mid", choice="engage")
    return final
