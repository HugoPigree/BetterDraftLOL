#!/usr/bin/env python3
"""Draft pick and ban suggestion engine based on predict_draft()."""

from __future__ import annotations

import logging
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
    MIN_GAMES_PRO_FORCE,
    compute_pro_winrate_by_champion,
    is_pro_viable_on_role,
    pro_meta_score,
    rank_pro_champions_for_role,
)
from champion_profile_stats import DescriptiveContext, format_descriptive_stats_clause

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


def _describe_synergy_shift(
    baseline: dict[str, Any],
    updated: dict[str, Any],
    team_side: TeamSide,
    changed_side: ChangedSide,
) -> str:
    side = _changed_team_side(team_side, changed_side)
    prof_b = _detail_for_side(baseline, side)["attribute_profile"]
    prof_n = _detail_for_side(updated, side)["attribute_profile"]
    shifts: list[str] = []
    for key, label in ATTRIBUTE_LABELS_FR.items():
        delta = float(prof_n[key]) - float(prof_b[key])
        if abs(delta) >= 0.12:
            shifts.append(label)
    if not shifts:
        return "meilleure cohérence globale de la composition"
    return f"plus de {', '.join(shifts[:2])}, cohérent avec le reste de la comp"


def build_decomposed_reason(
    *,
    headline: str,
    decomposition: dict[str, float],
    role: str,
    candidate: str,
    current: str | None,
    opponent: list[dict[str, str]],
    team: list[dict[str, str]],
    baseline: dict[str, Any],
    updated: dict[str, Any],
    team_side: TeamSide,
    changed_side: ChangedSide,
    patch: str,
    mode: PredictionMode,
) -> str:
    role = normalize_role(role)
    role_fr = ROLE_LABELS_FR.get(role, role.lower())
    wr_label = "pro" if mode == "pro" else "soloQ"
    delta = decomposition
    parts: list[str] = [headline]

    force_clause: str | None = None
    opp_same = _champion_for_role(opponent, role)
    cand_wr = _champion_winrate_for(candidate, role, patch, mode)
    curr_wr = _champion_winrate_for(current, role, patch, mode) if current else None
    opp_wr = _champion_winrate_for(opp_same, role, patch, mode) if opp_same else None

    if abs(delta["delta_force"]) >= 0.05:
        if changed_side == "team" and opp_same and cand_wr is not None and opp_wr is not None:
            force_clause = (
                f"{delta['delta_force']:+.1f} pt car {candidate} est un profil plus favorable "
                f"face à {opp_same} en {role_fr} ({wr_label})"
            )
        elif changed_side == "opponent" and opp_same and cand_wr is not None:
            force_clause = (
                f"{delta['delta_force']:+.1f} pt car {candidate} renforcerait l'{role_fr} adverse "
                f"face à {_champion_for_role(team, role) or 'votre pick'} ({wr_label})"
            )
        else:
            force_clause = f"{delta['delta_force']:+.1f} pt via la force individuelle ({wr_label})"

    duo_clause: str | None = None
    if role in DUO_ROLES and abs(delta["delta_duo"]) >= 0.05:
        team_ref = team if changed_side == "team" else opponent
        if role == "BOTTOM":
            partner = _champion_for_role(team_ref, "UTILITY")
            duo_clause = (
                f"{delta['delta_duo']:+.1f} pt via le duo bot avec {partner or 'le support'}"
            )
        elif role == "JUNGLE":
            partner = _champion_for_role(team_ref, "UTILITY")
            duo_clause = (
                f"{delta['delta_duo']:+.1f} pt via le duo jungle-support "
                f"avec {partner or 'le support'}"
            )
        else:
            adc = _champion_for_role(team_ref, "BOTTOM")
            jng = _champion_for_role(team_ref, "JUNGLE")
            duo_clause = (
                f"{delta['delta_duo']:+.1f} pt via les duos bot/jungle "
                f"({adc or 'adc'}/{jng or 'jungle'})"
            )

    synergy_shift = _describe_synergy_shift(baseline, updated, team_side, changed_side)
    clauses: list[str] = []
    if force_clause:
        clauses.append(force_clause)
    if abs(delta["delta_synergie"]) >= 0.05:
        if delta["delta_synergie"] > 0:
            clauses.append(
                f"{delta['delta_synergie']:+.1f} pt car elle renforce la synergie globale "
                f"({synergy_shift})"
            )
        else:
            clauses.append(
                f"{delta['delta_synergie']:+.1f} pt sur la synergie globale de la composition"
            )
    if duo_clause:
        clauses.append(duo_clause)

    if clauses:
        parts.append(
            f"{delta['delta_total']:+.1f} pt au total — dont " + ", et ".join(clauses[:3]) + "."
        )
    else:
        parts.append(f"{delta['delta_total']:+.1f} pt au total.")

    if changed_side == "team" and delta["delta_force"] > 0.05 and delta["delta_synergie"] < -0.05:
        parts.append(
            f"Attention : ce pick gagne sa lane mais affaiblit légèrement la synergie globale "
            f"de l'équipe ({delta['delta_synergie']:+.1f} pt), le gain net reste "
            f"{'positif' if delta['delta_total'] > 0 else 'négatif'} mais plus modeste qu'il n'y paraît."
        )

    stats_context: DescriptiveContext = "neutral"
    if changed_side == "team" and force_clause and delta["delta_force"] > 0.05:
        stats_context = "counter"
    elif changed_side == "opponent" and delta["delta_force"] < -0.05:
        stats_context = "threat"

    descriptive = format_descriptive_stats_clause(
        candidate,
        role,
        caller="suggest_draft",
        role_fr=role_fr,
        context=stats_context,
    )
    if descriptive:
        parts.append(descriptive)

    return " ".join(parts)


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
    candidates = champions_playable_on_role(pool, role, catalog)
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
        role_fr = ROLE_LABELS_FR.get(role, role.lower())
        headline = (
            f"{candidate} à la place de {current_champion} ({role_fr})"
            if current_champion
            else f"{candidate} en {role_fr}"
        )
        reason = build_decomposed_reason(
            headline=headline,
            decomposition=decomposition,
            role=role,
            candidate=candidate,
            current=current_champion,
            opponent=opponent,
            team=modified_team,
            baseline=baseline,
            updated=result,
            team_side=team_side,
            changed_side="team",
            patch=patch,
            mode=mode,
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
PRO_BOT_SYNERGY_WEIGHT = 0.38
PRO_BOT_DUO_WEIGHT = 0.22
PRO_BOT_META_WEIGHT = 0.18
PRO_BOT_SYNERGY_PENALTY_SCALE = 90.0
PRO_MIN_SYNERGY_AFTER_TWO_PICKS = 0.44


def _pro_winrate_entry(champion: str, role: str) -> tuple[float, int] | None:
    return _pro_winrate_for(champion, normalize_role(role))


def _pro_meta_score_for(champion: str, role: str) -> tuple[float, int, float, float, str] | None:
    champion_features, _, lookup_by_norm = get_meraki_context()
    return pro_meta_score(champion, role, champion_features, lookup_by_norm)


def _rank_pro_for_role(champions: list[str], role: str) -> list[tuple[float, int, float, float, str]]:
    champion_features, _, lookup_by_norm = get_meraki_context()
    return rank_pro_champions_for_role(
        champions, role, champion_features, lookup_by_norm
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
        ranked = _rank_pro_for_role(playable, role)
        if ranked:
            return ranked[0][4]
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
        ranked = _rank_pro_for_role(playable, role)
        return [name for _, _, _, _, name in ranked[: max(1, limit)]]

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
) -> float:
    """Score de sélection : winrate + synergie ML + duos pro + meta Oracle."""
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

        min_synergy = PRO_MIN_SYNERGY_AFTER_TWO_PICKS if locked_picks >= 2 else 0.40
        if locked_picks >= 1 and synergy < min_synergy:
            score -= (min_synergy - synergy) * PRO_BOT_SYNERGY_PENALTY_SCALE

    return score


def suggest_bot_pick(
    bot_partial_picks: list[dict[str, str]],
    opponent_partial_picks: list[dict[str, str]],
    patch: str,
    available_champions: list[str],
    team_side: TeamSide = "blue",
    mode: PredictionMode = "pro",
    candidates_per_role: int = BOT_CANDIDATES_PER_ROLE,
) -> dict[str, Any]:
    """Choisit le prochain pick du bot en simulant une compo meta + synergie ML."""
    patch = patch.strip()
    warmup_predict_caches(patch)
    catalog = get_champion_role_catalog()

    bot_partial = slots_to_team(bot_partial_picks)
    opponent_partial = slots_to_team(opponent_partial_picks)

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
    champion_features, _, lookup_by_norm = get_meraki_context()

    best: dict[str, Any] | None = None
    fallback: dict[str, Any] | None = None

    for role in bot_remaining:
        candidates = _top_candidates_for_role(
            pool, role, catalog, patch, mode, per_role
        )
        if mode == "pro":
            candidates = [
                name
                for name in candidates
                if is_pro_viable_on_role(
                    name, role, champion_features, lookup_by_norm
                )
            ] or candidates[:3]

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
            selection_score = _bot_pick_selection_score(
                result,
                team_side,
                mode,
                locked_picks,
                candidate_meta=candidate_meta,
                locked_duo_bonus=locked_duo_bonus,
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
            }

            if fallback is None or selection_score > fallback["selection_score"]:
                fallback = entry

            min_synergy = PRO_MIN_SYNERGY_AFTER_TWO_PICKS if locked_picks >= 2 else 0.40
            if mode == "pro" and locked_picks >= 1 and synergy < min_synergy:
                continue

            if best is None or selection_score > best["selection_score"]:
                best = entry

    chosen = best or fallback
    if chosen is None:
        return {"champion": None, "role": None, "win_probability": None}

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

    suggestions: list[dict[str, Any]] = []
    for candidate in sorted(set(pool), key=str.casefold):
        reserved = used | {candidate.casefold()}
        best_opponent_prob = -1.0
        best_role: str | None = None
        best_result: dict[str, Any] | None = None
        best_opponent_full: list[dict[str, str]] | None = None

        for role in remaining:
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
        role_fr = ROLE_LABELS_FR.get(best_role, best_role.lower())
        reason = build_decomposed_reason(
            headline=(
                f"Si l'adversaire pick {candidate} ({role_fr}), "
                f"votre winrate"
            ),
            decomposition=decomposition,
            role=best_role,
            candidate=candidate,
            current=None,
            opponent=best_opponent_full,
            team=team,
            baseline=baseline,
            updated=best_result,
            team_side=team_side,
            changed_side="opponent",
            patch=patch,
            mode=mode,
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
        role_fr = ROLE_LABELS_FR.get(role, role.lower())
        reason = build_decomposed_reason(
            headline=f"Ban manqué : {banned_champ} ({role_fr})",
            decomposition=decomposition,
            role=role,
            candidate=banned_champ,
            current=filler,
            opponent=opponent,
            team=team,
            baseline=baseline,
            updated=result,
            team_side=team_side,
            changed_side="opponent",
            patch=patch,
            mode=mode,
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
            top_n=max(picks_per_role * 5, 20),
            mode=mode,
        )
        if not role_result["suggestions"]:
            continue

        added_for_role = 0
        for candidate in role_result["suggestions"]:
            if candidate["champion"].casefold() == current_champion.casefold():
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
