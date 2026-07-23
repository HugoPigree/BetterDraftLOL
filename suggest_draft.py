#!/usr/bin/env python3
"""Draft pick and ban suggestion engine based on predict_draft()."""

from __future__ import annotations

import logging
import math
import random
from typing import Any, Literal

import build_training_dataset as btd
from predict_draft import (
    PredictionMode,
    WEIGHT_FORCE,
    WEIGHT_SIDE,
    WEIGHT_SYNERGY,
    build_soloq_lookup,
    get_meraki_context,
    get_side_bonuses,
    predict_draft,
    resolve_soloq_champion_name,
    score_diff_to_probabilities,
    warmup_predict_caches,
    load_soloq_scores,
)
from pro_force import (
    MIN_GAMES_EXCLUSION,
    MIN_GAMES_PRO_FORCE,
    compute_pro_winrate_by_champion,
    get_meta_pool_for_role,
    pro_meta_score,
)
from build_duo_dataset import get_duo_score
from composition_archetype import score_archetype_coherence
from justification_builder import generate_pick_justification

logger = logging.getLogger(__name__)

TeamSide = Literal["blue", "red"]
ChangedSide = Literal["team", "opponent"]
TOP_N = 5
RETROSPECTIVE_PICKS_PER_ROLE = 3
MIN_RETROSPECTIVE_BAN_GAIN = 0.35
DUO_ROLES = frozenset({"JUNGLE", "BOTTOM", "UTILITY"})

ATTRIBUTE_LABELS_FR = {
    "damage_mean": "dégâts",
    "toughness_mean": "robustesse",
    "control_mean": "contrôle",
    "mobility_mean": "mobilité",
    "utility_mean": "utilité",
}

ROLE_LABELS_FR = {
    "TOP": "top",
    "JUNGLE": "jungle",
    "MIDDLE": "mid",
    "BOTTOM": "adc",
    "UTILITY": "support",
}

POSITION_MAP = {
    "SUPPORT": "UTILITY",
}

VALID_ROLES = {"TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"}
ROLES_ORDER = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]


def normalize_role(role: str) -> str:
    role_upper = role.strip().upper()
    return POSITION_MAP.get(role_upper, role_upper)


def slots_to_team(slots: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {"champion": slot["champion"].strip(), "role": normalize_role(slot["role"])}
        for slot in slots
        if slot.get("champion", "").strip() and slot.get("role")
    ]


def soft_assign_roles(
    partial_picks: list[dict[str, Any]],
    catalog: dict[str, list[str]] | None = None,
) -> list[dict[str, str]]:
    """Déduit des rôles provisoires à partir des positions Meraki.

    En draft réelle les postes ne sont pas connus : on ignore tout rôle client
    et on assigne au mieux pour le scoring uniquement.
    """
    catalog = catalog or get_champion_role_catalog()
    champions = [
        str(slot.get("champion", "")).strip()
        for slot in partial_picks
        if str(slot.get("champion", "")).strip()
    ]
    if not champions:
        return []

    assigned: dict[str, str] = {}
    remaining = set(range(len(champions)))

    # Pass 1: champions with a single open fitting role
    for idx in list(remaining):
        name = champions[idx]
        positions = [r for r in catalog.get(name, []) if r in ROLES_ORDER]
        open_roles = [r for r in ROLES_ORDER if r not in assigned.values()]
        fitting = [r for r in open_roles if r in positions]
        if len(fitting) == 1:
            assigned[name] = fitting[0]
            remaining.discard(idx)

    # Pass 2: best score among remaining open roles
    for role in ROLES_ORDER:
        if role in assigned.values():
            continue
        best_idx: int | None = None
        best_score = -2
        for idx in remaining:
            name = champions[idx]
            positions = catalog.get(name, [])
            if role not in positions:
                score = -1
            elif len(positions) == 1:
                score = 3
            elif positions and positions[0] == role:
                score = 2
            else:
                score = 1
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_idx is not None and best_score >= 0:
            assigned[champions[best_idx]] = role
            remaining.discard(best_idx)

    # Pass 3: leftover champions get leftover roles
    leftover_roles = [r for r in ROLES_ORDER if r not in assigned.values()]
    for idx in sorted(remaining):
        if not leftover_roles:
            break
        assigned[champions[idx]] = leftover_roles.pop(0)

    return [
        {"champion": name, "role": assigned[name]}
        for name in champions
        if name in assigned
    ]


def get_champion_role_catalog() -> dict[str, list[str]]:
    champions = btd.load_meraki_champions(btd.MERAKI_URL, btd.DEFAULT_MERAKI_CACHE)
    catalog: dict[str, list[str]] = {}

    for key, payload in champions.items():
        name = str(payload.get("name", key)).strip()
        if not name:
            continue

        positions: list[str] = []
        for position in payload.get("positions", []):
            mapped = normalize_role(str(position))
            if mapped in VALID_ROLES and mapped not in positions:
                positions.append(mapped)

        catalog[name] = positions

    return catalog


def champions_playable_on_role(
    champions: list[str],
    role: str,
    catalog: dict[str, list[str]],
) -> list[str]:
    role = normalize_role(role)
    playable: list[str] = []
    for champion in champions:
        name = champion.strip()
        if not name:
            continue
        if role in catalog.get(name, []):
            playable.append(name)
    return sorted(set(playable), key=str.casefold)


def filter_meta_pool_candidates_for_role(
    pool: list[str],
    role: str,
    catalog: dict[str, list[str]],
    patch: str,
    *,
    top_n: int | None = None,
) -> list[str]:
    """Candidats filtrés par get_meta_pool_for_role (>= MIN_GAMES_EXCLUSION games pro)."""
    role = normalize_role(role)
    playable = champions_playable_on_role(pool, role, catalog)
    if not playable:
        return []

    champion_features, _, lookup_by_norm = get_meraki_context()
    limit = top_n if top_n is not None else len(playable)
    return get_meta_pool_for_role(
        role,
        patch,
        top_n=max(limit, 1),
        candidates=playable,
        champion_features=champion_features,
        lookup_by_norm=lookup_by_norm,
    )


def is_champion_in_meta_pool_for_role(
    champion: str,
    role: str,
    catalog: dict[str, list[str]],
    patch: str,
) -> bool:
    """True si le champion atteint MIN_GAMES_EXCLUSION à ce rôle."""
    eligible = filter_meta_pool_candidates_for_role(
        [champion.strip()],
        role,
        catalog,
        patch,
    )
    key = champion.strip().casefold()
    return any(name.casefold() == key for name in eligible)


def replace_role_pick(
    team: list[dict[str, str]],
    role: str,
    champion: str,
) -> list[dict[str, str]]:
    role = normalize_role(role)
    replaced = False
    updated: list[dict[str, str]] = []

    for slot in team:
        if normalize_role(slot["role"]) == role:
            updated.append({"champion": champion, "role": role})
            replaced = True
        else:
            updated.append({"champion": slot["champion"], "role": normalize_role(slot["role"])})

    if not replaced:
        raise ValueError(f"Aucun pick trouvé pour le rôle {role} dans l'équipe")

    return updated


def team_side_win_probability(result: dict[str, Any], team_side: TeamSide) -> float:
    if team_side == "blue":
        return float(result["blue_win_probability"])
    return float(result["red_win_probability"])


def opponent_side_win_probability(result: dict[str, Any], team_side: TeamSide) -> float:
    if team_side == "blue":
        return float(result["red_win_probability"])
    return float(result["blue_win_probability"])


def build_matchup_teams(
    team_picks: list[dict[str, str]],
    opponent_picks: list[dict[str, str]],
    team_side: TeamSide,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if team_side == "blue":
        return team_picks, opponent_picks
    return opponent_picks, team_picks


def gain_percentage_points(current: float, updated: float) -> float:
    return round((updated - current) * 100, 2)


def _default_force(force: float | None) -> float:
    return float(force) if force is not None else 0.5


def _detail_for_side(result: dict[str, Any], side: TeamSide) -> dict[str, Any]:
    return result["blue"] if side == "blue" else result["red"]


def _side_index(side: TeamSide) -> int:
    return 0 if side == "blue" else 1


def _changed_team_side(team_side: TeamSide, changed_side: ChangedSide) -> TeamSide:
    if changed_side == "team":
        return team_side
    return "red" if team_side == "blue" else "blue"


def _team_score_from_components(force: float, synergy: float, side: TeamSide) -> float:
    side_bonus = get_side_bonuses()[_side_index(side)]
    return WEIGHT_FORCE * force + WEIGHT_SYNERGY * synergy + WEIGHT_SIDE * side_bonus


def _win_prob_from_scores(our_score: float, opp_score: float, team_side: TeamSide) -> float:
    if team_side == "blue":
        return score_diff_to_probabilities(our_score, opp_score)[0]
    return score_diff_to_probabilities(opp_score, our_score)[1]


def _our_matchup_win_prob(matchup: dict[str, Any], team_side: TeamSide) -> float | None:
    prob = matchup.get("blue_win_probability")
    if prob is None or matchup.get("insufficient_data"):
        return None
    return float(prob) if team_side == "blue" else 1.0 - float(prob)


def _duo_score_delta_points(old: dict[str, Any], new: dict[str, Any]) -> float:
    old_score, new_score = old.get("score"), new.get("score")
    if old_score is None or new_score is None:
        return 0.0
    return (float(new_score) - float(old_score)) * 100.0


def _estimate_duo_delta_points(
    baseline: dict[str, Any],
    updated: dict[str, Any],
    team_side: TeamSide,
    role: str,
    changed_side: ChangedSide,
) -> float:
    """Estimation explicative du delta duo/matchup (pts de winrate)."""
    role = normalize_role(role)
    if role not in DUO_ROLES:
        return 0.0

    duo_side = _changed_team_side(team_side, changed_side)
    duos_b = baseline["duo_synergies"][duo_side]
    duos_n = updated["duo_synergies"][duo_side]

    pts = 0.0
    sign = -1.0 if changed_side == "opponent" else 1.0

    bl_match_b = _our_matchup_win_prob(baseline["bot_lane_matchup"], team_side)
    bl_match_n = _our_matchup_win_prob(updated["bot_lane_matchup"], team_side)
    js_match_b = _our_matchup_win_prob(baseline["jungle_support_matchup"], team_side)
    js_match_n = _our_matchup_win_prob(updated["jungle_support_matchup"], team_side)

    if role == "BOTTOM":
        pts += _duo_score_delta_points(duos_b["duo_bot_lane"], duos_n["duo_bot_lane"]) * 0.45
        if bl_match_b is not None and bl_match_n is not None:
            pts += (bl_match_n - bl_match_b) * 100.0 * 0.55
    elif role == "JUNGLE":
        pts += _duo_score_delta_points(duos_b["duo_jungle_support"], duos_n["duo_jungle_support"]) * 0.45
        if js_match_b is not None and js_match_n is not None:
            pts += (js_match_n - js_match_b) * 100.0 * 0.55
    elif role == "UTILITY":
        pts += _duo_score_delta_points(duos_b["duo_bot_lane"], duos_n["duo_bot_lane"]) * 0.25
        pts += _duo_score_delta_points(duos_b["duo_jungle_support"], duos_n["duo_jungle_support"]) * 0.25
        if bl_match_b is not None and bl_match_n is not None:
            pts += (bl_match_n - bl_match_b) * 100.0 * 0.25
        if js_match_b is not None and js_match_n is not None:
            pts += (js_match_n - js_match_b) * 100.0 * 0.25

    return round(sign * pts, 2)


def decompose_winrate_delta(
    baseline: dict[str, Any],
    updated: dict[str, Any],
    team_side: TeamSide,
    role: str,
    changed_side: ChangedSide,
    mode: PredictionMode = "mixed",
) -> dict[str, float]:
    """Décompose la variation de winrate en force, synergie et duo (pts)."""
    del mode  # réservé pour affinements futurs pro/mixed
    role = normalize_role(role)
    p_old = team_side_win_probability(baseline, team_side)
    p_new = team_side_win_probability(updated, team_side)
    delta_total = round((p_new - p_old) * 100, 2)

    if changed_side == "team":
        our_b = _detail_for_side(baseline, team_side)
        our_n = _detail_for_side(updated, team_side)
        opp_score = _detail_for_side(baseline, "red" if team_side == "blue" else "blue")["score_final"]
        force_b = _default_force(our_b["score_force"])
        force_n = _default_force(our_n["score_force"])
        syn_b = float(our_b["score_synergie"])
        syn_n = float(our_n["score_synergie"])
        p_base = _win_prob_from_scores(
            _team_score_from_components(force_b, syn_b, team_side),
            opp_score,
            team_side,
        )
        p_after_force = _win_prob_from_scores(
            _team_score_from_components(force_n, syn_b, team_side),
            opp_score,
            team_side,
        )
        p_after_synergy = _win_prob_from_scores(
            _team_score_from_components(force_n, syn_n, team_side),
            opp_score,
            team_side,
        )
    else:
        opp_b = _detail_for_side(baseline, "red" if team_side == "blue" else "blue")
        opp_n = _detail_for_side(updated, "red" if team_side == "blue" else "blue")
        our_score = _detail_for_side(baseline, team_side)["score_final"]
        force_b = _default_force(opp_b["score_force"])
        force_n = _default_force(opp_n["score_force"])
        syn_b = float(opp_b["score_synergie"])
        syn_n = float(opp_n["score_synergie"])
        p_base = _win_prob_from_scores(our_score, _team_score_from_components(force_b, syn_b, _changed_team_side(team_side, "opponent")), team_side)
        p_after_force = _win_prob_from_scores(our_score, _team_score_from_components(force_n, syn_b, _changed_team_side(team_side, "opponent")), team_side)
        p_after_synergy = _win_prob_from_scores(our_score, _team_score_from_components(force_n, syn_n, _changed_team_side(team_side, "opponent")), team_side)

    delta_force = round((p_after_force - p_base) * 100, 2)

    delta_duo = 0.0
    if role in DUO_ROLES:
        delta_duo = _estimate_duo_delta_points(baseline, updated, team_side, role, changed_side)
        delta_synergie = round(delta_total - delta_force - delta_duo, 2)
    else:
        delta_synergie = round(delta_total - delta_force, 2)

    # Ajustement d'arrondi : la somme doit coller au gain affiché
    delta_synergie = round(delta_total - delta_force - delta_duo, 2)

    return {
        "delta_force": delta_force,
        "delta_synergie": delta_synergie,
        "delta_duo": delta_duo,
        "delta_total": delta_total,
    }


def _champion_for_role(team: list[dict[str, str]], role: str) -> str | None:
    role = normalize_role(role)
    for slot in team:
        if normalize_role(slot["role"]) == role:
            return slot["champion"].strip()
    return None


def _soloq_winrate_for(champion: str, role: str, patch: str) -> float | None:
    try:
        champion_features, _, lookup_by_norm = get_meraki_context()
        soloq_lookup = build_soloq_lookup(load_soloq_scores(patch))
        resolved = resolve_soloq_champion_name(champion, champion_features, lookup_by_norm)
        if resolved is None:
            return None
        return soloq_lookup.get((resolved, normalize_role(role)))
    except (FileNotFoundError, ValueError):
        return None


def _pro_winrate_for(champion: str, role: str) -> tuple[float, int] | None:
    try:
        champion_features, _, lookup_by_norm = get_meraki_context()
        return compute_pro_winrate_by_champion(
            champion, normalize_role(role), champion_features, lookup_by_norm
        )
    except (FileNotFoundError, ValueError):
        return None


def _champion_winrate_for(
    champion: str,
    role: str,
    patch: str,
    mode: PredictionMode,
) -> float | None:
    if mode == "pro":
        entry = _pro_winrate_for(champion, role)
        return entry[0] if entry is not None else None
    return _soloq_winrate_for(champion, role, patch)


def suggest_improvements(
    team_picks: list[dict[str, str]],
    opponent_picks: list[dict[str, str]],
    role_to_improve: str,
    patch: str,
    available_champions: list[str],
    team_side: TeamSide = "blue",
    top_n: int = TOP_N,
    mode: PredictionMode = "mixed",
) -> dict[str, Any]:
    """Suggère les remplacements de pick les plus profitables pour un rôle donné."""
    if len(team_picks) != 5 or len(opponent_picks) != 5:
        raise ValueError("team_picks et opponent_picks doivent contenir exactement 5 champions")

    role = normalize_role(role_to_improve)
    if role not in VALID_ROLES:
        raise ValueError(f"Rôle invalide: {role_to_improve}")

    team = slots_to_team(team_picks)
    opponent = slots_to_team(opponent_picks)
    patch = patch.strip()

    warmup_predict_caches(patch)
    catalog = get_champion_role_catalog()

    used = {slot["champion"].casefold() for slot in team + opponent}
    pool = [
        champion.strip()
        for champion in available_champions
        if champion.strip() and champion.strip().casefold() not in used
    ]
    candidates = filter_meta_pool_candidates_for_role(pool, role, catalog, patch)
    if not candidates:
        return {
            "team_side": team_side,
            "role": role,
            "current_win_probability": None,
            "suggestions": [],
        }

    blue_team, red_team = build_matchup_teams(team, opponent, team_side)
    baseline = predict_draft(blue_team, red_team, patch=patch, mode=mode)
    current_prob = team_side_win_probability(baseline, team_side)

    current_champion = _champion_for_role(team, role)
    suggestions: list[dict[str, Any]] = []
    for candidate in candidates:
        modified_team = replace_role_pick(team, role, candidate)
        mod_blue, mod_red = build_matchup_teams(modified_team, opponent, team_side)
        result = predict_draft(mod_blue, mod_red, patch=patch, mode=mode)
        new_prob = team_side_win_probability(result, team_side)
        decomposition = decompose_winrate_delta(
            baseline, result, team_side, role, "team", mode
        )
        team_so_far = [
            slot["champion"]
            for slot in team
            if normalize_role(slot["role"]) != role
        ]
        reason = generate_pick_justification(
            candidate,
            role,
            team_context=modified_team,
            opponent_context=opponent,
            source_data={
                "patch": patch,
                "mode": mode,
                "pick_side": "team",
                "changed_side": "team",
                "decomposition": decomposition,
                "archetype_score": score_archetype_coherence(team_so_far, candidate),
            },
        )
        suggestions.append(
            {
                "champion": candidate,
                "win_probability": round(new_prob, 4),
                "gain_percentage_points": decomposition["delta_total"],
                "delta_force": decomposition["delta_force"],
                "delta_synergie": decomposition["delta_synergie"],
                "delta_duo": decomposition["delta_duo"],
                "delta_total": decomposition["delta_total"],
                "reason": reason,
            }
        )

    suggestions.sort(
        key=lambda item: (item["gain_percentage_points"], item["win_probability"]),
        reverse=True,
    )

    logger.info(
        "Suggest pick role=%s side=%s: %d candidats évalués, baseline=%.2f%%",
        role,
        team_side,
        len(candidates),
        current_prob * 100,
    )

    return {
        "team_side": team_side,
        "role": role,
        "current_win_probability": round(current_prob, 4),
        "suggestions": suggestions[:top_n],
    }


def _pick_filler_for_role(
    role: str,
    catalog: dict[str, list[str]],
    available: list[str],
    reserved: set[str],
) -> str | None:
    for champion in sorted(available, key=str.casefold):
        key = champion.casefold()
        if key in reserved:
            continue
        if role in catalog.get(champion, []):
            return champion
    return None


def build_opponent_team_with_fillers(
    opponent_partial: list[dict[str, str]],
    remaining_roles: list[str],
    catalog: dict[str, list[str]],
    available_champions: list[str],
    reserved: set[str],
    patch: str = "",
    mode: PredictionMode = "mixed",
) -> list[dict[str, str]] | None:
    team = slots_to_team(opponent_partial)
    picked = {normalize_role(slot["role"]): slot["champion"] for slot in team}
    roles_to_fill = [normalize_role(role) for role in remaining_roles]
    used = set(reserved)
    used.update(name.casefold() for name in picked.values())

    for role in roles_to_fill:
        if role in picked:
            continue
        filler = _pick_filler_for_role_smart(
            role, catalog, available_champions, used, patch, mode
        )
        if filler is None:
            return None
        picked[role] = filler
        used.add(filler.casefold())

    if len(picked) != 5:
        return None

    return [{"champion": picked[role], "role": role} for role in picked]


def build_opponent_team_with_pick(
    opponent_partial: list[dict[str, str]],
    candidate: str,
    candidate_role: str,
    remaining_roles: list[str],
    catalog: dict[str, list[str]],
    available_champions: list[str],
    reserved: set[str],
    patch: str = "",
    mode: PredictionMode = "mixed",
) -> list[dict[str, str]] | None:
    candidate_role = normalize_role(candidate_role)
    roles_to_fill = [normalize_role(role) for role in remaining_roles]
    if candidate_role not in roles_to_fill:
        return None

    team = slots_to_team(opponent_partial)
    picked = {normalize_role(slot["role"]): slot["champion"] for slot in team}
    picked[candidate_role] = candidate
    used = set(reserved)
    used.add(candidate.casefold())
    used.update(name.casefold() for name in picked.values())

    for role in roles_to_fill:
        if role in picked:
            continue
        filler = _pick_filler_for_role_smart(
            role, catalog, available_champions, used, patch, mode
        )
        if filler is None:
            return None
        picked[role] = filler
        used.add(filler.casefold())

    if len(picked) != 5:
        return None

    return [{"champion": picked[role], "role": role} for role in picked]


BOT_CANDIDATES_PER_ROLE = 12
# Softmax pick diversity : plus bas = proche du deterministe, plus haut = plus de variety.
# 0.3 laissait Ashe ~75% / Nocturne ~91% (scores serrés ~90-100 => exp(score/T) trop peaked).
# 1.0 retenu apres 90 sims (3 seeds) : Ashe ~40%, Bard ~47%, Nocturne ~70%, 4-10 champs/rôle.
TEMPERATURE_BOT_PICK = 1.0
PRO_BOT_SYNERGY_WEIGHT = 0.38
PRO_BOT_DUO_WEIGHT = 0.22
PRO_BOT_META_WEIGHT = 0.18
# Cohérence d'archétype (early/late, engage/peel, AD/AP). Testé empiriquement : 0.18
# pénalise ~18 pts un carry fragile dans une comp dive sans changer le softmax global.
WEIGHT_ARCHETYPE = 0.18
PRO_BOT_SYNERGY_PENALTY_SCALE = 90.0
PRO_MIN_SYNERGY_AFTER_TWO_PICKS = 0.44


def _pro_winrate_entry(champion: str, role: str) -> tuple[float, int] | None:
    return _pro_winrate_for(champion, normalize_role(role))


def _pro_meta_score_for(champion: str, role: str) -> tuple[float, int, float, float, str] | None:
    champion_features, _, lookup_by_norm = get_meraki_context()
    return pro_meta_score(champion, role, champion_features, lookup_by_norm)


def _bot_meta_pool_for_role(
    pool: list[str],
    role: str,
    catalog: dict[str, list[str]],
    patch: str,
    limit: int,
) -> list[str]:
    """Pool candidats bot pro : get_meta_pool_for_role sur champions jouables disponibles."""
    return filter_meta_pool_candidates_for_role(
        pool, role, catalog, patch, top_n=limit
    )


def _meta_strength_for(
    champion: str,
    role: str,
    patch: str,
    mode: PredictionMode,
) -> float:
    if mode == "pro":
        scored = _pro_meta_score_for(champion, role)
        if scored is None:
            return -1.0
        return scored[0]

    winrate = _champion_winrate_for(champion, role, patch, mode)
    return float(winrate) if winrate is not None else 0.48


def pick_meta_filler_for_role(
    role: str,
    catalog: dict[str, list[str]],
    available: list[str],
    reserved: set[str],
    patch: str,
    mode: PredictionMode,
) -> str | None:
    """Champion de remplissage crédible (meta pro ou soloQ selon le mode)."""
    role = normalize_role(role)
    playable = champions_playable_on_role(available, role, catalog)
    playable = [name for name in playable if name.casefold() not in reserved]

    if mode == "pro":
        pool_names = _bot_meta_pool_for_role(
            available, role, catalog, patch, limit=1
        )
        if pool_names:
            return pool_names[0]
        return _pick_filler_for_role(role, catalog, available, reserved)

    ranked_mixed: list[tuple[float, int, float, str]] = []
    for champion in playable:
        ranked_mixed.append(
            (_meta_strength_for(champion, role, patch, mode), 0, 0.0, champion)
        )
    ranked_mixed.sort(key=lambda item: (-item[0], item[3].casefold()))
    if not ranked_mixed:
        return _pick_filler_for_role(role, catalog, available, reserved)
    return ranked_mixed[0][3]


def _pick_filler_for_role_smart(
    role: str,
    catalog: dict[str, list[str]],
    available: list[str],
    reserved: set[str],
    patch: str,
    mode: PredictionMode,
) -> str | None:
    if mode == "pro":
        return pick_meta_filler_for_role(role, catalog, available, reserved, patch, mode)
    return _pick_filler_for_role(role, catalog, available, reserved)


def build_team_with_meta_fillers(
    partial_picks: list[dict[str, str]],
    remaining_roles: list[str],
    catalog: dict[str, list[str]],
    available_champions: list[str],
    reserved: set[str],
    patch: str,
    mode: PredictionMode,
) -> list[dict[str, str]] | None:
    """Complète une draft partielle avec des champions meta plutôt qu'alphabétiques."""
    team = slots_to_team(partial_picks)
    picked = {normalize_role(slot["role"]): slot["champion"] for slot in team}
    roles_to_fill = [normalize_role(role) for role in remaining_roles]
    used = set(reserved)
    used.update(name.casefold() for name in picked.values())

    for role in roles_to_fill:
        if role in picked:
            continue
        filler = _pick_filler_for_role_smart(
            role, catalog, available_champions, used, patch, mode
        )
        if filler is None:
            return None
        picked[role] = filler
        used.add(filler.casefold())

    if len(picked) != 5:
        return None

    return [{"champion": picked[role], "role": role} for role in picked]


def build_simulated_team_with_pick(
    partial_picks: list[dict[str, str]],
    candidate: str,
    candidate_role: str,
    remaining_roles: list[str],
    catalog: dict[str, list[str]],
    available_champions: list[str],
    reserved: set[str],
    patch: str,
    mode: PredictionMode,
) -> list[dict[str, str]] | None:
    """Simule une compo complète en posant un candidat puis des fillers meta."""
    candidate_role = normalize_role(candidate_role)
    roles_to_fill = [normalize_role(role) for role in remaining_roles]
    if candidate_role not in roles_to_fill and candidate_role not in {
        normalize_role(slot["role"]) for slot in partial_picks
    }:
        return None

    team = slots_to_team(partial_picks)
    picked = {normalize_role(slot["role"]): slot["champion"] for slot in team}
    picked[candidate_role] = candidate
    used = set(reserved)
    used.add(candidate.casefold())
    used.update(name.casefold() for name in picked.values())

    for role in roles_to_fill:
        if role in picked:
            continue
        filler = _pick_filler_for_role_smart(
            role, catalog, available_champions, used, patch, mode
        )
        if filler is None:
            return None
        picked[role] = filler
        used.add(filler.casefold())

    if len(picked) != 5:
        return None

    return [{"champion": picked[role], "role": role} for role in picked]


def _top_candidates_for_role(
    pool: list[str],
    role: str,
    catalog: dict[str, list[str]],
    patch: str,
    mode: PredictionMode,
    limit: int,
) -> list[str]:
    playable = champions_playable_on_role(pool, role, catalog)
    if mode == "pro":
        return _bot_meta_pool_for_role(pool, role, catalog, patch, limit)

    ranked_mixed = [
        (_meta_strength_for(champion, role, patch, mode), champion)
        for champion in playable
    ]
    ranked_mixed.sort(key=lambda item: (-item[0], item[1].casefold()))
    return [name for _, name in ranked_mixed[: max(1, limit)]]


def _locked_pro_duo_bonus(
    bot_partial: list[dict[str, str]],
    candidate: str,
    candidate_role: str,
) -> float:
    """Bonus si le candidat forme un duo pro mesuré avec un pick déjà posé."""
    role = normalize_role(candidate_role)
    bonus = 0.0

    support = _champion_for_role(bot_partial, "UTILITY")
    adc = _champion_for_role(bot_partial, "BOTTOM")
    jungle = _champion_for_role(bot_partial, "JUNGLE")

    if role == "BOTTOM" and support:
        duo = get_duo_score(candidate, support, "bot_lane", mode="pro")
        if not duo.insufficient_data and duo.score is not None:
            bonus += float(duo.score) * 12.0
    elif role == "UTILITY":
        if adc:
            duo = get_duo_score(adc, candidate, "bot_lane", mode="pro")
            if not duo.insufficient_data and duo.score is not None:
                bonus += float(duo.score) * 12.0
        if jungle:
            duo = get_duo_score(jungle, candidate, "jungle_support", mode="pro")
            if not duo.insufficient_data and duo.score is not None:
                bonus += float(duo.score) * 8.0
    elif role == "JUNGLE" and support:
        duo = get_duo_score(candidate, support, "jungle_support", mode="pro")
        if not duo.insufficient_data and duo.score is not None:
            bonus += float(duo.score) * 8.0

    return bonus


def _average_measured_duo_score(result: dict[str, Any], team_side: TeamSide) -> float | None:
    duos = result["duo_synergies"][team_side]
    scores: list[float] = []
    for key in ("duo_jungle_support", "duo_bot_lane"):
        payload = duos[key]
        if payload.get("insufficient_data") or payload.get("score") is None:
            continue
        scores.append(float(payload["score"]))
    if not scores:
        return None
    return sum(scores) / len(scores)


def _bot_pick_selection_score(
    result: dict[str, Any],
    team_side: TeamSide,
    mode: PredictionMode,
    locked_picks: int,
    candidate_meta: float | None = None,
    locked_duo_bonus: float = 0.0,
    archetype_score: float | None = None,
) -> float:
    """Score de sélection : winrate + synergie ML + duos pro + meta + archétype."""
    win_prob = team_side_win_probability(result, team_side)
    detail = _detail_for_side(result, team_side)
    synergy = float(detail["score_synergie"])

    score = win_prob * 100.0

    if mode == "pro":
        score += synergy * 100.0 * PRO_BOT_SYNERGY_WEIGHT
        duo_avg = _average_measured_duo_score(result, team_side)
        if duo_avg is not None:
            score += duo_avg * 100.0 * PRO_BOT_DUO_WEIGHT
        if candidate_meta is not None:
            score += candidate_meta * 100.0 * PRO_BOT_META_WEIGHT
        score += locked_duo_bonus
        if archetype_score is not None:
            score += archetype_score * 100.0 * WEIGHT_ARCHETYPE

        min_synergy = PRO_MIN_SYNERGY_AFTER_TWO_PICKS if locked_picks >= 2 else 0.40
        if locked_picks >= 1 and synergy < min_synergy:
            score -= (min_synergy - synergy) * PRO_BOT_SYNERGY_PENALTY_SCALE

    return score


def decompose_bot_candidate_score(
    bot_partial_picks: list[dict[str, str]],
    opponent_partial_picks: list[dict[str, str]],
    candidate: str,
    candidate_role: str,
    patch: str,
    available_champions: list[str],
    team_side: TeamSide = "blue",
    mode: PredictionMode = "pro",
    *,
    weight_archetype: float = WEIGHT_ARCHETYPE,
) -> dict[str, Any] | None:
    """Décompose le score de sélection d'un candidat bot (composantes brutes + pondérées)."""
    patch = patch.strip()
    warmup_predict_caches(patch)
    catalog = get_champion_role_catalog()

    bot_partial = soft_assign_roles(bot_partial_picks, catalog)
    opponent_partial = soft_assign_roles(opponent_partial_picks, catalog)
    candidate_role = normalize_role(candidate_role)

    reserved = {
        slot["champion"].casefold()
        for slot in bot_partial + opponent_partial
    }
    pool = [
        champion.strip()
        for champion in available_champions
        if champion.strip() and champion.strip().casefold() not in reserved
    ]
    if candidate.casefold() in reserved:
        return None

    bot_remaining = [
        role
        for role in ROLES_ORDER
        if role not in {normalize_role(slot["role"]) for slot in bot_partial}
    ]
    if candidate_role not in bot_remaining:
        return None

    opponent_remaining = [
        role
        for role in ROLES_ORDER
        if role not in {normalize_role(slot["role"]) for slot in opponent_partial}
    ] or ROLES_ORDER.copy()

    locked_picks = len(bot_partial)
    meta_scored = _pro_meta_score_for(candidate, candidate_role) if mode == "pro" else None
    candidate_meta = meta_scored[0] if meta_scored else None
    locked_duo_bonus = (
        _locked_pro_duo_bonus(bot_partial, candidate, candidate_role) if mode == "pro" else 0.0
    )

    trial_reserved = reserved | {candidate.casefold()}
    bot_full = build_simulated_team_with_pick(
        partial_picks=bot_partial,
        candidate=candidate,
        candidate_role=candidate_role,
        remaining_roles=bot_remaining,
        catalog=catalog,
        available_champions=pool,
        reserved=trial_reserved,
        patch=patch,
        mode=mode,
    )
    if bot_full is None:
        return None

    used_for_opp = trial_reserved | {
        slot["champion"].casefold() for slot in bot_full
    }
    opponent_full = build_team_with_meta_fillers(
        partial_picks=opponent_partial,
        remaining_roles=opponent_remaining,
        catalog=catalog,
        available_champions=pool,
        reserved=used_for_opp,
        patch=patch,
        mode=mode,
    )
    if opponent_full is None:
        return None

    mod_blue, mod_red = build_matchup_teams(bot_full, opponent_full, team_side)
    result = predict_draft(mod_blue, mod_red, patch=patch, mode=mode)
    win_prob = team_side_win_probability(result, team_side)
    detail = _detail_for_side(result, team_side)
    synergy = float(detail["score_synergie"])
    duo_avg = _average_measured_duo_score(result, team_side)
    team_so_far = [slot["champion"] for slot in bot_partial]
    archetype_score = score_archetype_coherence(team_so_far, candidate)

    score_winrate = win_prob * 100.0
    score_synergy_ml = synergy * 100.0 * PRO_BOT_SYNERGY_WEIGHT
    score_duo = duo_avg * 100.0 * PRO_BOT_DUO_WEIGHT if duo_avg is not None else 0.0
    score_meta = (
        candidate_meta * 100.0 * PRO_BOT_META_WEIGHT if candidate_meta is not None else 0.0
    )
    score_archetype = archetype_score * 100.0 * weight_archetype

    synergy_penalty = 0.0
    if mode == "pro":
        min_synergy = PRO_MIN_SYNERGY_AFTER_TWO_PICKS if locked_picks >= 2 else 0.40
        if locked_picks >= 1 and synergy < min_synergy:
            synergy_penalty = (min_synergy - synergy) * PRO_BOT_SYNERGY_PENALTY_SCALE

    selection_score = (
        score_winrate
        + score_synergy_ml
        + score_duo
        + score_meta
        + locked_duo_bonus
        + score_archetype
        - synergy_penalty
    )

    return {
        "champion": candidate,
        "role": candidate_role,
        "win_probability": round(win_prob, 4),
        "synergy_raw": round(synergy, 4),
        "meta_raw": round(candidate_meta, 4) if candidate_meta is not None else None,
        "duo_raw": round(duo_avg, 4) if duo_avg is not None else None,
        "archetype_raw": archetype_score,
        "duo_bonus": round(locked_duo_bonus, 2),
        "score_winrate": round(score_winrate, 2),
        "score_synergy_ml": round(score_synergy_ml, 2),
        "score_duo": round(score_duo, 2),
        "score_meta": round(score_meta, 2),
        "score_archetype": round(score_archetype, 2),
        "score_duo_bonus": round(locked_duo_bonus, 2),
        "score_synergy_penalty": round(synergy_penalty, 2),
        "selection_score": round(selection_score, 2),
        "weight_archetype": weight_archetype,
    }


def _weighted_bot_pick(
    candidates: list[dict[str, Any]],
    temperature: float,
    rng: random.Random,
) -> dict[str, Any]:
    """Tirage softmax parmi les candidats evalues (scores de selection)."""
    if not candidates:
        raise ValueError("Aucun candidat pour le tirage bot")
    if len(candidates) == 1:
        return candidates[0]

    temp = max(temperature, 1e-6)
    max_score = max(float(item["selection_score"]) for item in candidates)
    weights = [
        math.exp((float(item["selection_score"]) - max_score) / temp)
        for item in candidates
    ]
    total = sum(weights)
    roll = rng.random() * total
    cumulative = 0.0
    for item, weight in zip(candidates, weights, strict=True):
        cumulative += weight
        if roll <= cumulative:
            item = dict(item)
            item["selection_probability"] = round(weight / total, 4)
            return item

    chosen = dict(candidates[-1])
    chosen["selection_probability"] = round(weights[-1] / total, 4)
    return chosen


def suggest_bot_pick(
    bot_partial_picks: list[dict[str, str]],
    opponent_partial_picks: list[dict[str, str]],
    patch: str,
    available_champions: list[str],
    team_side: TeamSide = "blue",
    mode: PredictionMode = "pro",
    candidates_per_role: int = BOT_CANDIDATES_PER_ROLE,
    rng: random.Random | None = None,
    rng_seed: int | None = None,
) -> dict[str, Any]:
    """Choisit le prochain pick du bot en simulant une compo meta + synergie ML."""
    if rng_seed is not None:
        pick_rng = random.Random(rng_seed)
    elif rng is not None:
        pick_rng = rng
    else:
        pick_rng = random.Random()
    patch = patch.strip()
    warmup_predict_caches(patch)
    catalog = get_champion_role_catalog()

    bot_partial = soft_assign_roles(bot_partial_picks, catalog)
    opponent_partial = soft_assign_roles(opponent_partial_picks, catalog)

    reserved = {
        slot["champion"].casefold()
        for slot in bot_partial + opponent_partial
    }
    pool = [
        champion.strip()
        for champion in available_champions
        if champion.strip() and champion.strip().casefold() not in reserved
    ]
    if not pool:
        return {"champion": None, "role": None, "win_probability": None}

    bot_remaining = [
        role
        for role in ROLES_ORDER
        if role not in {normalize_role(slot["role"]) for slot in bot_partial}
    ]
    if not bot_remaining:
        raise ValueError("La compo du bot est déjà complète")

    opponent_remaining = [
        role
        for role in ROLES_ORDER
        if role not in {normalize_role(slot["role"]) for slot in opponent_partial}
    ] or ROLES_ORDER.copy()

    locked_picks = len(bot_partial)
    per_role = max(4, min(candidates_per_role, 20))

    eligible: list[dict[str, Any]] = []
    fallback_eligible: list[dict[str, Any]] = []
    role_pools: dict[str, list[str]] = {}
    candidate_eval_logs: list[dict[str, Any]] = []
    allowed_pool: set[str] = set()
    min_synergy = PRO_MIN_SYNERGY_AFTER_TWO_PICKS if locked_picks >= 2 else 0.40

    for role in bot_remaining:
        candidates = _top_candidates_for_role(
            pool, role, catalog, patch, mode, per_role
        )
        if mode == "pro":
            role_pools[role] = list(candidates)
            allowed_pool.update(name.casefold() for name in candidates)

        for candidate in candidates:
            meta_scored = _pro_meta_score_for(candidate, role) if mode == "pro" else None
            candidate_meta = meta_scored[0] if meta_scored else None
            locked_duo_bonus = (
                _locked_pro_duo_bonus(bot_partial, candidate, role) if mode == "pro" else 0.0
            )

            trial_reserved = reserved | {candidate.casefold()}
            bot_full = build_simulated_team_with_pick(
                partial_picks=bot_partial,
                candidate=candidate,
                candidate_role=role,
                remaining_roles=bot_remaining,
                catalog=catalog,
                available_champions=pool,
                reserved=trial_reserved,
                patch=patch,
                mode=mode,
            )
            if bot_full is None:
                continue

            used_for_opp = trial_reserved | {
                slot["champion"].casefold() for slot in bot_full
            }
            opponent_full = build_team_with_meta_fillers(
                partial_picks=opponent_partial,
                remaining_roles=opponent_remaining,
                catalog=catalog,
                available_champions=pool,
                reserved=used_for_opp,
                patch=patch,
                mode=mode,
            )
            if opponent_full is None:
                continue

            mod_blue, mod_red = build_matchup_teams(bot_full, opponent_full, team_side)
            result = predict_draft(mod_blue, mod_red, patch=patch, mode=mode)
            win_prob = team_side_win_probability(result, team_side)
            team_so_far = [slot["champion"] for slot in bot_partial]
            archetype_score = score_archetype_coherence(team_so_far, candidate)
            selection_score = _bot_pick_selection_score(
                result,
                team_side,
                mode,
                locked_picks,
                candidate_meta=candidate_meta,
                locked_duo_bonus=locked_duo_bonus,
                archetype_score=archetype_score,
            )
            synergy = float(_detail_for_side(result, team_side)["score_synergie"])

            pro_entry = _pro_winrate_entry(candidate, role)
            entry = {
                "champion": candidate,
                "role": role,
                "win_probability": round(win_prob, 4),
                "selection_score": selection_score,
                "synergy": synergy,
                "pro_games": pro_entry[1] if pro_entry else None,
                "meta_score": round(candidate_meta, 4) if candidate_meta is not None else None,
                "role_fitness": round(meta_scored[3], 4) if meta_scored else None,
                "archetype_score": archetype_score,
            }

            if mode == "pro":
                candidate_eval_logs.append(
                    {
                        "role": role,
                        "champion": candidate,
                        "pro_games": entry["pro_games"],
                        "meta_score": entry["meta_score"],
                        "win_prob": entry["win_probability"],
                        "synergy": entry["synergy"],
                        "duo_bonus": round(locked_duo_bonus, 2),
                        "archetype_score": archetype_score,
                        "selection_score": round(selection_score, 2),
                    }
                )

            fallback_eligible.append(entry)
            if mode == "pro" and locked_picks >= 1 and synergy < min_synergy:
                continue
            eligible.append(entry)

    pick_pool = eligible if eligible else fallback_eligible
    if not pick_pool:
        return {"champion": None, "role": None, "win_probability": None}

    if mode == "pro":
        chosen = _weighted_bot_pick(pick_pool, TEMPERATURE_BOT_PICK, pick_rng)
    else:
        chosen = max(pick_pool, key=lambda item: item["selection_score"])

    if mode == "pro":
        logger.info(
            "Bot meta pools (>= %d games) by role: %s",
            MIN_GAMES_EXCLUSION,
            role_pools,
        )
        for row in sorted(
            candidate_eval_logs,
            key=lambda item: (-item["selection_score"], item["champion"].casefold()),
        ):
            logger.info(
                "Bot candidate [%s] %s: games=%s meta=%s win=%.1f%% syn=%.3f "
                "duo=%.1f score=%.2f",
                row["role"],
                row["champion"],
                row["pro_games"],
                row["meta_score"],
                row["win_prob"] * 100,
                row["synergy"],
                row["duo_bonus"],
                row["selection_score"],
            )
        logger.info(
            "Bot softmax pick T=%.2f prob=%.2f%% pool_size=%d used_synergy_filter=%s",
            TEMPERATURE_BOT_PICK,
            chosen.get("selection_probability", 1.0) * 100,
            len(pick_pool),
            bool(eligible),
        )
        chosen_key = chosen["champion"].casefold()
        if allowed_pool and chosen_key not in allowed_pool:
            logger.error(
                "Bot pick hors pool meta: %s (%s) not in %s",
                chosen["champion"],
                chosen["role"],
                role_pools,
            )
            raise ValueError(
                f"Pick bot hors pool meta restreint: {chosen['champion']} ({chosen['role']})"
            )

    logger.info(
        "Bot pick side=%s: %s (%s) score=%.2f win=%.2f%% synergy=%.2f pro_games=%s",
        team_side,
        chosen["champion"],
        chosen["role"],
        chosen["selection_score"],
        chosen["win_probability"] * 100,
        chosen["synergy"],
        chosen.get("pro_games"),
    )

    bot_team_with_pick = bot_partial + [
        {"champion": chosen["champion"], "role": chosen["role"]}
    ]
    chosen["reason"] = generate_pick_justification(
        chosen["champion"],
        chosen["role"],
        team_context=bot_team_with_pick,
        opponent_context=opponent_partial,
        source_data={
            "patch": patch,
            "mode": mode,
            "pick_side": "team",
            "archetype_score": chosen.get("archetype_score"),
        },
    )

    return chosen


def suggest_ban(
    available_champions: list[str],
    opponent_partial_picks: list[dict[str, str]],
    opponent_remaining_roles: list[str],
    patch: str,
    team_picks: list[dict[str, str]],
    team_side: TeamSide = "blue",
    top_n: int = TOP_N,
    mode: PredictionMode = "mixed",
) -> dict[str, Any]:
    """Suggère des bans préventifs contre les picks adverses les plus dangereux."""
    if len(team_picks) != 5:
        raise ValueError("team_picks doit contenir exactement 5 champions")

    opponent = slots_to_team(opponent_partial_picks)
    team = slots_to_team(team_picks)
    patch = patch.strip()

    remaining = [normalize_role(role) for role in opponent_remaining_roles]
    if not remaining:
        raise ValueError("opponent_remaining_roles ne peut pas être vide")

    warmup_predict_caches(patch)
    catalog = get_champion_role_catalog()

    used = {slot["champion"].casefold() for slot in team + opponent}
    pool = [
        champion.strip()
        for champion in available_champions
        if champion.strip() and champion.strip().casefold() not in used
    ]
    if not pool:
        return {"team_side": team_side, "baseline_opponent_win_probability": None, "suggestions": []}

    blue_team, red_team = build_matchup_teams(team, opponent, team_side)
    if len(opponent) == 5:
        baseline_opponent = opponent
    else:
        baseline_opponent = build_opponent_team_with_fillers(
            opponent_partial=opponent,
            remaining_roles=remaining,
            catalog=catalog,
            available_champions=pool,
            reserved=used,
            patch=patch,
            mode=mode,
        )
        if baseline_opponent is None:
            baseline_opponent = opponent

    mod_blue, mod_red = build_matchup_teams(team, baseline_opponent, team_side)
    baseline = predict_draft(mod_blue, mod_red, patch=patch, mode=mode)
    baseline_opp_prob = opponent_side_win_probability(baseline, team_side)

    meta_pools_by_role: dict[str, set[str]] = {}
    canonical_by_key: dict[str, str] = {}
    for slot_role in remaining:
        for name in filter_meta_pool_candidates_for_role(
            pool, slot_role, catalog, patch
        ):
            meta_pools_by_role.setdefault(slot_role, set()).add(name.casefold())
            canonical_by_key[name.casefold()] = name

    ban_candidate_keys: set[str] = set()
    for slot_role in remaining:
        ban_candidate_keys |= meta_pools_by_role.get(slot_role, set())

    suggestions: list[dict[str, Any]] = []
    for key in sorted(ban_candidate_keys, key=str.casefold):
        candidate = canonical_by_key[key]
        reserved = used | {key}
        best_opponent_prob = -1.0
        best_role: str | None = None
        best_result: dict[str, Any] | None = None
        best_opponent_full: list[dict[str, str]] | None = None

        for role in remaining:
            if key not in meta_pools_by_role.get(role, set()):
                continue
            if role not in catalog.get(candidate, []):
                continue

            opponent_full = build_opponent_team_with_pick(
                opponent_partial=opponent,
                candidate=candidate,
                candidate_role=role,
                remaining_roles=remaining,
                catalog=catalog,
                available_champions=pool,
                reserved=reserved,
                patch=patch,
                mode=mode,
            )
            if opponent_full is None:
                continue

            mod_blue, mod_red = build_matchup_teams(team, opponent_full, team_side)
            result = predict_draft(mod_blue, mod_red, patch=patch, mode=mode)
            opponent_prob = opponent_side_win_probability(result, team_side)

            if opponent_prob > best_opponent_prob:
                best_opponent_prob = opponent_prob
                best_role = role
                best_result = result
                best_opponent_full = opponent_full

        if best_role is None or best_result is None or best_opponent_full is None:
            continue

        decomposition = decompose_winrate_delta(
            baseline, best_result, team_side, best_role, "opponent", mode
        )
        reason = generate_pick_justification(
            candidate,
            best_role,
            team_context=team,
            opponent_context=best_opponent_full,
            source_data={
                "patch": patch,
                "mode": mode,
                "pick_side": "opponent",
                "changed_side": "opponent",
                "decomposition": decomposition,
            },
        )

        threat_points = (
            gain_percentage_points(baseline_opp_prob, best_opponent_prob)
            if baseline_opp_prob is not None
            else round(best_opponent_prob * 100, 2)
        )
        suggestions.append(
            {
                "champion": candidate,
                "best_opponent_role": best_role,
                "opponent_win_probability": round(best_opponent_prob, 4),
                "threat_percentage_points": threat_points,
                "delta_force": decomposition["delta_force"],
                "delta_synergie": decomposition["delta_synergie"],
                "delta_duo": decomposition["delta_duo"],
                "delta_total": decomposition["delta_total"],
                "reason": reason,
            }
        )

    suggestions.sort(
        key=lambda item: (item["opponent_win_probability"], item["threat_percentage_points"]),
        reverse=True,
    )

    logger.info(
        "Suggest ban side=%s: %d candidats évalués, rôles restants=%s",
        team_side,
        len(suggestions),
        remaining,
    )

    return {
        "team_side": team_side,
        "baseline_opponent_win_probability": (
            round(baseline_opp_prob, 4) if baseline_opp_prob is not None else None
        ),
        "suggestions": suggestions[:top_n],
    }


def suggest_retrospective_bans(
    team_picks: list[dict[str, str]],
    opponent_picks: list[dict[str, str]],
    patch: str,
    available_champions: list[str],
    team_side: TeamSide = "blue",
    top_n: int = TOP_N,
    mode: PredictionMode = "mixed",
) -> dict[str, Any]:
    """Analyse a posteriori : quels picks adverses auraient mérité un ban."""
    if len(team_picks) != 5 or len(opponent_picks) != 5:
        raise ValueError("team_picks et opponent_picks doivent contenir exactement 5 champions")

    team = slots_to_team(team_picks)
    opponent = slots_to_team(opponent_picks)
    patch = patch.strip()

    warmup_predict_caches(patch)
    catalog = get_champion_role_catalog()

    blue_team, red_team = build_matchup_teams(team, opponent, team_side)
    baseline = predict_draft(blue_team, red_team, patch=patch, mode=mode)
    baseline_prob = team_side_win_probability(baseline, team_side)

    suggestions: list[dict[str, Any]] = []
    for slot in opponent:
        role = normalize_role(slot["role"])
        banned_champ = slot["champion"]

        if not is_champion_in_meta_pool_for_role(banned_champ, role, catalog, patch):
            continue

        reserved = {pick["champion"].casefold() for pick in team + opponent}
        reserved.discard(banned_champ.casefold())

        pool = [
            champion.strip()
            for champion in available_champions
            if champion.strip() and champion.strip().casefold() not in reserved
        ]
        filler = _pick_filler_for_role(role, catalog, pool, reserved)
        if filler is None:
            continue

        modified_opponent = replace_role_pick(opponent, role, filler)
        mod_blue, mod_red = build_matchup_teams(team, modified_opponent, team_side)
        result = predict_draft(mod_blue, mod_red, patch=patch, mode=mode)
        new_prob = team_side_win_probability(result, team_side)
        decomposition = decompose_winrate_delta(
            baseline, result, team_side, role, "opponent", mode
        )
        gain = decomposition["delta_total"]
        reason = generate_pick_justification(
            banned_champ,
            role,
            team_context=team,
            opponent_context=opponent,
            source_data={
                "patch": patch,
                "mode": mode,
                "pick_side": "opponent",
                "changed_side": "opponent",
                "decomposition": decomposition,
                "prefix": f"Ban manqué sur {banned_champ} ({ROLE_LABELS_FR.get(role, role.lower())})",
            },
        )

        if gain < MIN_RETROSPECTIVE_BAN_GAIN:
            continue

        suggestions.append(
            {
                "champion": banned_champ,
                "role": role,
                "replacement_champion": filler,
                "win_probability": round(new_prob, 4),
                "gain_percentage_points": gain,
                "delta_force": decomposition["delta_force"],
                "delta_synergie": decomposition["delta_synergie"],
                "delta_duo": decomposition["delta_duo"],
                "delta_total": decomposition["delta_total"],
                "reason": reason,
            }
        )

    suggestions.sort(
        key=lambda item: (item["gain_percentage_points"], item["win_probability"]),
        reverse=True,
    )

    logger.info(
        "Retrospective ban side=%s: %d picks adverses impactants",
        team_side,
        len(suggestions),
    )

    return {
        "team_side": team_side,
        "current_win_probability": round(baseline_prob, 4),
        "suggestions": suggestions[:top_n],
    }


def suggest_retrospective_picks(
    team_picks: list[dict[str, str]],
    opponent_picks: list[dict[str, str]],
    patch: str,
    available_champions: list[str],
    team_side: TeamSide = "blue",
    picks_per_role: int = RETROSPECTIVE_PICKS_PER_ROLE,
    top_n: int | None = None,
    mode: PredictionMode = "mixed",
) -> dict[str, Any]:
    """Analyse a posteriori : meilleurs picks alternatifs face à la comp adverse."""
    if len(team_picks) != 5 or len(opponent_picks) != 5:
        raise ValueError("team_picks et opponent_picks doivent contenir exactement 5 champions")

    picks_per_role = max(1, min(picks_per_role, RETROSPECTIVE_PICKS_PER_ROLE))

    team = slots_to_team(team_picks)
    opponent = slots_to_team(opponent_picks)
    patch = patch.strip()
    current_by_role = {normalize_role(slot["role"]): slot["champion"] for slot in team}

    warmup_predict_caches(patch)
    blue_team, red_team = build_matchup_teams(team, opponent, team_side)
    baseline = predict_draft(blue_team, red_team, patch=patch, mode=mode)
    current_prob = team_side_win_probability(baseline, team_side)

    suggestions: list[dict[str, Any]] = []
    for role in ROLES_ORDER:
        current_champion = current_by_role.get(role)
        if not current_champion:
            continue

        role_result = suggest_improvements(
            team_picks=team,
            opponent_picks=opponent,
            role_to_improve=role,
            patch=patch,
            available_champions=available_champions,
            team_side=team_side,
            top_n=max(picks_per_role * 15, 50),
            mode=mode,
        )
        if not role_result["suggestions"]:
            continue

        added_for_role = 0
        for candidate in role_result["suggestions"]:
            if candidate["champion"].casefold() == current_champion.casefold():
                continue
            if candidate["gain_percentage_points"] <= 0:
                continue

            suggestions.append(
                {
                    "role": role,
                    "current_champion": current_champion,
                    "champion": candidate["champion"],
                    "win_probability": candidate["win_probability"],
                    "gain_percentage_points": candidate["gain_percentage_points"],
                    "delta_force": candidate.get("delta_force", 0.0),
                    "delta_synergie": candidate.get("delta_synergie", 0.0),
                    "delta_duo": candidate.get("delta_duo", 0.0),
                    "delta_total": candidate.get("delta_total", candidate["gain_percentage_points"]),
                    "reason": candidate.get("reason", ""),
                }
            )
            added_for_role += 1
            if added_for_role >= picks_per_role:
                break

    suggestions.sort(
        key=lambda item: (item["role"], -item["gain_percentage_points"], -item["win_probability"]),
    )

    if top_n is not None:
        suggestions = suggestions[:top_n]

    logger.info(
        "Retrospective pick side=%s: %d alternatives (%d/rôle max), baseline=%.2f%%",
        team_side,
        len(suggestions),
        picks_per_role,
        current_prob * 100,
    )

    return {
        "team_side": team_side,
        "current_win_probability": round(current_prob, 4),
        "suggestions": suggestions,
    }
