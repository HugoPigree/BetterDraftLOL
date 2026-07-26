"""Types de dilemmes, signaux et variantes textuelles pour la simulation Worlds."""

from __future__ import annotations

import random
from typing import Any, Literal

from build_duo_dataset import SEUIL_MIN_GAMES, lookup_solo_lane_matchup
from composition_archetype import compute_composition_archetype

Side = Literal["blue", "red"]
DilemmaType = Literal[
    "bot_lane",
    "jungle_support",
    "objective_control",
    "split_push",
    "vision_control",
]
PhaseKey = Literal["early", "mid"]

OBJECTIVE_ENGAGE_W = 0.55
OBJECTIVE_SYN_W = 0.45
VISION_CONTROL_W = 0.50
VISION_PEEL_W = 0.50
RELEVANCE_BOOST = 0.15

DILEMMA_BASE_WEIGHTS: dict[DilemmaType, float] = {
    "bot_lane": 1.0,
    "jungle_support": 1.0,
    "objective_control": 0.9,
    "split_push": 0.85,
    "vision_control": 0.85,
}

DECISION_MINUTE_RANGES: dict[PhaseKey, tuple[int, int]] = {
    "early": (10, 15),
    "mid": (23, 28),
}

LATE_DECISION_MINUTE = 31

ALL_DILEMMA_TYPES: tuple[DilemmaType, ...] = (
    "bot_lane",
    "jungle_support",
    "objective_control",
    "split_push",
    "vision_control",
)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def pts_to_phase_advantage(pts: float) -> float:
    return clamp(pts / 100.0, -0.35, 0.35)


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


def _team_champion_names(team_detail: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for entry in team_detail.get("champions") or []:
        if isinstance(entry, dict):
            name = str(entry.get("champion", "")).strip()
            if name:
                names.append(name)
        elif isinstance(entry, str) and entry.strip():
            names.append(entry.strip())
    return names


def _champion_for_role_from_prediction(team_detail: dict[str, Any], role: str) -> str | None:
    role = role.upper()
    for entry in team_detail.get("champions") or []:
        if isinstance(entry, dict) and str(entry.get("role", "")).upper() == role:
            name = str(entry.get("champion", "")).strip()
            return name or None
    return None


def _attribute_profile(team_detail: dict[str, Any]) -> dict[str, float]:
    profile = team_detail.get("attribute_profile") or {}
    return {
        "control_mean": float(profile.get("control_mean", 1.5)),
        "utility_mean": float(profile.get("utility_mean", 1.5)),
    }


def _team_archetype(team_detail: dict[str, Any]) -> dict[str, Any]:
    return compute_composition_archetype(_team_champion_names(team_detail))


def compute_late_advantage(prediction: dict[str, Any], *, player_side: Side) -> float:
    ours = _our_team_detail(prediction, player_side=player_side)
    theirs = _their_team_detail(prediction, player_side=player_side)
    late = _score_delta_advantage(
        float(ours.get("score_final", 0.0)),
        float(theirs.get("score_final", 0.0)),
    )
    if abs(late) >= 1e-6:
        return late
    player_draft = _player_side_prob(
        prediction.get("blue_win_probability", 0.5),
        player_side=player_side,
    )
    return pts_to_phase_advantage(((player_draft or 0.5) - 0.5) * 100.0)


def compute_dilemma_advantage(
    dilemma_type: DilemmaType,
    prediction: dict[str, Any],
    *,
    player_side: Side,
) -> tuple[float, bool]:
    ours = _our_team_detail(prediction, player_side=player_side)
    theirs = _their_team_detail(prediction, player_side=player_side)

    if dilemma_type == "bot_lane":
        bot = prediction.get("bot_lane_matchup")
        adv = _matchup_player_advantage(bot, player_side=player_side)
        if abs(adv) < 1e-6:
            adv = _matchup_player_advantage(
                prediction.get("jungle_support_matchup"), player_side=player_side
            )
        return adv, True

    if dilemma_type == "jungle_support":
        adv_js = _matchup_player_advantage(
            prediction.get("jungle_support_matchup"), player_side=player_side
        )
        adv_syn = _score_delta_advantage(
            float(ours.get("score_synergie", 0.5)),
            float(theirs.get("score_synergie", 0.5)),
        )
        return (adv_js if abs(adv_js) >= abs(adv_syn) else adv_syn), True

    if dilemma_type == "objective_control":
        our_arch = _team_archetype(ours)
        their_arch = _team_archetype(theirs)
        engage_delta = float(our_arch["engage_score"]) - float(their_arch["engage_score"])
        syn_delta = float(ours.get("score_synergie", 0.5)) - float(theirs.get("score_synergie", 0.5))
        pts = OBJECTIVE_ENGAGE_W * (engage_delta * 100.0) + OBJECTIVE_SYN_W * (syn_delta * 100.0)
        return pts_to_phase_advantage(pts), True

    if dilemma_type == "split_push":
        our_top = _champion_for_role_from_prediction(ours, "TOP")
        opp_top = _champion_for_role_from_prediction(theirs, "TOP")
        if not our_top or not opp_top:
            return 0.0, False
        games, wr_blue = lookup_solo_lane_matchup(our_top, opp_top, "TOP")
        if games < SEUIL_MIN_GAMES or wr_blue is None:
            return 0.0, False
        player_prob = wr_blue if player_side == "blue" else 1.0 - wr_blue
        return pts_to_phase_advantage((player_prob - 0.5) * 100.0), True

    if dilemma_type == "vision_control":
        our_arch = _team_archetype(ours)
        their_arch = _team_archetype(theirs)
        our_attr = _attribute_profile(ours)
        their_attr = _attribute_profile(theirs)
        control_delta = our_attr["control_mean"] - their_attr["control_mean"]
        peel_delta = float(our_arch["peel_score"]) - float(their_arch["peel_score"])
        pts = VISION_CONTROL_W * (control_delta * 30.0) + VISION_PEEL_W * (peel_delta * 100.0)
        return pts_to_phase_advantage(pts), True

    return 0.0, False


def _weighted_sample_without_replacement(
    rng: random.Random,
    items: list[tuple[DilemmaType, float]],
    weights: list[float],
    count: int,
) -> list[tuple[DilemmaType, float]]:
    pool = list(items)
    pool_weights = list(weights)
    selected: list[tuple[DilemmaType, float]] = []
    for _ in range(min(count, len(pool))):
        total = sum(pool_weights)
        if total <= 0:
            break
        pick = rng.random() * total
        acc = 0.0
        for index, weight in enumerate(pool_weights):
            acc += weight
            if pick <= acc:
                selected.append(pool[index])
                pool.pop(index)
                pool_weights.pop(index)
                break
    return selected


def _fallback_pair(
    prediction: dict[str, Any],
    *,
    player_side: Side,
) -> list[tuple[DilemmaType, float]]:
    return [
        ("bot_lane", compute_dilemma_advantage("bot_lane", prediction, player_side=player_side)[0]),
        (
            "jungle_support",
            compute_dilemma_advantage("jungle_support", prediction, player_side=player_side)[0],
        ),
    ]


def build_decision_plan(
    prediction: dict[str, Any],
    *,
    player_side: Side,
    rng: random.Random,
) -> list[dict[str, Any]]:
    eligible: list[tuple[DilemmaType, float]] = []
    weights: list[float] = []

    for dilemma_type in ALL_DILEMMA_TYPES:
        advantage, ok = compute_dilemma_advantage(
            dilemma_type, prediction, player_side=player_side
        )
        if not ok:
            continue
        relevance = 1.0 + RELEVANCE_BOOST * min(abs(advantage), 0.35) / 0.35
        eligible.append((dilemma_type, advantage))
        weights.append(DILEMMA_BASE_WEIGHTS[dilemma_type] * relevance)

    picked = _weighted_sample_without_replacement(rng, eligible, weights, 2)
    if len(picked) < 2:
        picked = _fallback_pair(prediction, player_side=player_side)
    rng.shuffle(picked)

    phase_keys: tuple[PhaseKey, PhaseKey] = ("early", "mid")
    plan: list[dict[str, Any]] = []
    for phase_key, (dilemma_type, advantage) in zip(phase_keys, picked, strict=True):
        low, high = DECISION_MINUTE_RANGES[phase_key]
        plan.append(
            {
                "phase_key": phase_key,
                "dilemma_type": dilemma_type,
                "phase_advantage": round(advantage, 4),
                "decision_minute": rng.randint(low, high),
                "context_variant": rng.randrange(_context_variant_count(dilemma_type)),
                "explanation_variant": rng.randrange(_explanation_variant_count(dilemma_type)),
            }
        )
    return plan


def _roster_ctx(player_roster: dict[str, str], opponent_roster: dict[str, str]) -> dict[str, str]:
    return {
        "p_top": player_roster.get("TOP") or "Top",
        "p_jgl": player_roster.get("JUNGLE") or "Jungle",
        "p_mid": player_roster.get("MIDDLE") or "Mid",
        "p_adc": player_roster.get("BOTTOM") or "ADC",
        "p_sup": player_roster.get("UTILITY") or "Support",
        "o_top": opponent_roster.get("TOP") or "Top adverse",
        "o_jgl": opponent_roster.get("JUNGLE") or "Jungle adverse",
        "o_adc": opponent_roster.get("BOTTOM") or "ADC adverse",
    }


CONTEXT_VARIANTS: dict[DilemmaType, list[str]] = {
    "bot_lane": [
        "La wave bot se stack sous votre tour. {p_jgl} est en position de gank pendant que {p_adc}/{p_sup} jouent la 2v2 contre {o_adc}. Engager ou temporiser ?",
        "Le jungler adverse path bot — {p_adc} et {p_sup} doivent décider s'ils all-in ou slow push. Quel tempo ?",
        "Bot lane sous prio : {p_jgl} peut counter-gank pendant que {p_adc}/{p_sup} défendent. Forcer le fight ou reset ?",
        "Drake spawn soon — {p_adc}/{p_sup} veulent stack la wave, {o_adc} cherche l'all-in. Engager maintenant ?",
    ],
    "jungle_support": [
        "Tempo mid et objectif en jeu. {p_jgl} peut forcer une skirmish pendant que {o_jgl} cherche une ouverture. Fight ou reset ?",
        "Le support vient de roam — {p_jgl} et {p_sup} peuvent punir ou laisser l'objectif. Quelle décision ?",
        "Herald contestable : {p_jgl} propose un invade pendant que {o_jgl} setup la vision. Engager ?",
        "Mid prio serrée — {p_jgl} voit une fenêtre jungle/support. Forcer le 2v2 ou jouer safe ?",
    ],
    "objective_control": [
        "Un drake est up dans 30 secondes. Votre comp peut force malgré un setup adverse. Contest ou céder l'objectif ?",
        "Void grubs disponibles — l'équipe peut engage sous tour adverse. Forcer le take ou reset ?",
        "Herald spawn : votre draft peut dive la plate. Engager l'objectif ou farm safe ?",
        "L'objectif est contestable mais le setup n'est pas parfait. Force malgré tout ou temporise ?",
    ],
    "split_push": [
        "{p_top} a prio top et peut split pendant que le reste setup un fight mid. Split ou regroup ?",
        "Side lane ouverte — {p_top} peut push pendant que {p_jgl} cherche une ouverture ailleurs. Split push ?",
        "La top lane est isolée : {p_top} propose de split pendant que l'équipe prépare un objectif. Valider ?",
    ],
    "vision_control": [
        "Baron spawn dans 1 minute — investir dans la vision avant le setup ou jouer reactif ?",
        "L'équipe peut deep ward avant le prochain fight. Poser la vision ou skip et force ?",
        "Objectif majeur imminent : contrôle de vision complet ou tempo agressif sans setup ?",
        "Le fog est favorable — investir dans le sweep avant d'engage ou y aller à l'aveugle ?",
    ],
}


EXPLANATION_VARIANTS: dict[DilemmaType, list[str]] = {
    "bot_lane": [
        "Le duo bot ({duo}) partait avec {adv_pts:+.0f} pts ({direction}). {outcome}. {choice_hint}",
        "Signal bot lane : avantage estimé {adv_pts:+.0f} pts pour {duo} ({direction}). {outcome}. {choice_hint}",
        "La 2v2 ({duo}) était {direction} ({adv_pts:+.0f} pts). {outcome}. {choice_hint}",
        "Contexte bot : {adv_pts:+.0f} pts pour votre duo ({direction}). {outcome}. {choice_hint}",
    ],
    "jungle_support": [
        "Jungle/support + cohérence mid : {adv_pts:+.0f} pts (Δ synergie {syn_delta:+.1f} pts). {outcome}. {choice_hint}",
        "Tempo JG/sup : avantage phase {adv_pts:+.0f} pts, Δ synergie {syn_delta:+.1f}. {outcome}. {choice_hint}",
        "Skirmish mid estimée {direction} ({adv_pts:+.0f} pts). {outcome}. {choice_hint}",
        "Signal jungle/support {adv_pts:+.0f} pts ({direction}). {outcome}. {choice_hint}",
    ],
    "objective_control": [
        "Force d'engage relative {engage_delta:+.0f} pts + cohésion {syn_delta:+.1f} pts → avantage objectif {adv_pts:+.0f} pts. {outcome}. {choice_hint}",
        "Votre comp {force_label} force les objectifs ({adv_pts:+.0f} pts, engage Δ {engage_delta:+.0f}). {outcome}. {choice_hint}",
        "Contexte drake/herald : {adv_pts:+.0f} pts ({direction}). {outcome}. {choice_hint}",
        "Setup objectif {direction} ({adv_pts:+.0f} pts). {outcome}. {choice_hint}",
    ],
    "split_push": [
        "Matchup top {our_top} vs {opp_top} : {adv_pts:+.0f} pts ({direction}). {outcome}. {choice_hint}",
        "Split push : avantage lane {adv_pts:+.0f} pts pour {our_top} ({direction}). {outcome}. {choice_hint}",
        "Top side {direction} ({adv_pts:+.0f} pts) — {our_top} vs {opp_top}. {outcome}. {choice_hint}",
    ],
    "vision_control": [
        "Contrôle + peel : Δ control {control_delta:+.1f}, Δ peel {peel_delta:+.0f} pts → {adv_pts:+.0f} pts phase. {outcome}. {choice_hint}",
        "Setup vision {direction} ({adv_pts:+.0f} pts). {outcome}. {choice_hint}",
        "Investissement vision {vision_label} ({adv_pts:+.0f} pts). {outcome}. {choice_hint}",
        "Signal contrôle {adv_pts:+.0f} pts ({direction}). {outcome}. {choice_hint}",
    ],
}


def _context_variant_count(dilemma_type: DilemmaType) -> int:
    return len(CONTEXT_VARIANTS[dilemma_type])


def _explanation_variant_count(dilemma_type: DilemmaType) -> int:
    return len(EXPLANATION_VARIANTS[dilemma_type])


def pick_context_text(
    dilemma_type: DilemmaType,
    *,
    player_roster: dict[str, str],
    opponent_roster: dict[str, str],
    variant_index: int,
) -> str:
    variants = CONTEXT_VARIANTS[dilemma_type]
    template = variants[variant_index % len(variants)]
    return template.format(**_roster_ctx(player_roster, opponent_roster))


def build_explanation_text(
    dilemma_type: DilemmaType,
    *,
    phase_advantage: float,
    choice: str,
    phase_won: bool,
    prediction: dict[str, Any],
    player_side: Side,
    player_roster: dict[str, str],
    opponent_roster: dict[str, str],
    variant_index: int,
) -> str:
    adv_pts = phase_advantage * 100.0
    direction = (
        "en ta faveur" if phase_advantage > 0.02 else "contre toi" if phase_advantage < -0.02 else "serré"
    )
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

    ours = _our_team_detail(prediction, player_side=player_side)
    theirs = _their_team_detail(prediction, player_side=player_side)
    our_arch = _team_archetype(ours)
    their_arch = _team_archetype(theirs)
    our_attr = _attribute_profile(ours)
    their_attr = _attribute_profile(theirs)

    bot = prediction.get("bot_lane_matchup") or {}
    blue_champs = bot.get("blue_champions") or []
    red_champs = bot.get("red_champions") or []
    duo = (
        " / ".join(blue_champs if player_side == "blue" else red_champs)
        or f"{_roster_ctx(player_roster, opponent_roster)['p_adc']} / {_roster_ctx(player_roster, opponent_roster)['p_sup']}"
    )

    ctx = {
        "adv_pts": adv_pts,
        "direction": direction,
        "outcome": outcome,
        "choice_hint": choice_hint,
        "duo": duo,
        "syn_delta": (float(ours.get("score_synergie", 0.5)) - float(theirs.get("score_synergie", 0.5))) * 100.0,
        "engage_delta": (float(our_arch["engage_score"]) - float(their_arch["engage_score"])) * 100.0,
        "control_delta": our_attr["control_mean"] - their_attr["control_mean"],
        "peel_delta": (float(our_arch["peel_score"]) - float(their_arch["peel_score"])) * 100.0,
        "our_top": player_roster.get("TOP") or "Top",
        "opp_top": opponent_roster.get("TOP") or "Top adverse",
        "force_label": "peut" if adv_pts > 0 else "doit",
        "vision_label": "justifié" if adv_pts > 0 else "risqué",
    }
    variants = EXPLANATION_VARIANTS[dilemma_type]
    return variants[variant_index % len(variants)].format(**ctx)
