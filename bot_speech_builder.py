"""Reformulation parlée des justifications techniques du bot Rival."""

from __future__ import annotations

import random
from typing import Any, Literal

from build_duo_dataset import DuoType, get_duo_score
from champion_profile_stats import lookup_champion_profile_stats
from composition_archetype import (
    ENGAGE_ROLE_WEIGHTS,
    PEEL_ROLE_WEIGHTS,
    compute_composition_archetype,
    _resolve_team_champions,
    _roles_for,
)
from justification_builder import (
    ROLE_LABELS_FR,
    SIGNIFICANT_BAN_RATE,
    _champion_for_role,
    _describe_archetype_shift,
    _team_champions_excluding_role,
    lookup_meta_tierlist_row,
    normalize_role,
)
from predict_draft import PredictionMode, get_meraki_context
from pro_force import pro_meta_score

ROLE_ORDER = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")

TECHNICAL_BLACKLIST = (
    "Wilson",
    "wilson",
    "meta_score",
    "archétype Meraki",
    "archetype Meraki",
    "presence_score",
    "damage_profile",
    "engage_score",
    "peel_score",
    "power_curve",
    "delta_force",
    "delta_synergie",
)

MetaKind = Literal["established", "often_banned", "niche", "credible"]
ShiftKind = Literal["peel", "engage", "early", "scaling", "damage_balance"]


def _pick(templates: list[str], **kwargs: Any) -> str:
    return random.choice(templates).format(**kwargs)


def _scrub(text: str) -> str:
    cleaned = text
    for banned in TECHNICAL_BLACKLIST:
        cleaned = cleaned.replace(banned, "")
    return " ".join(cleaned.split())


def _duo_type_and_label(role: str) -> tuple[DuoType | None, str]:
    role = normalize_role(role)
    if role == "BOTTOM":
        return "bot_lane", "bot lane"
    if role == "JUNGLE":
        return "jungle_support", "jungle-support"
    if role == "UTILITY":
        return None, "duo"
    return None, "duo"


def _resolve_duo_details(
    champion: str,
    role: str,
    pick_team: list[dict[str, str]],
    *,
    mode: PredictionMode,
) -> dict[str, Any] | None:
    role = normalize_role(role)
    partners: list[tuple[str, DuoType, str]] = []
    if role == "BOTTOM":
        support = _champion_for_role(pick_team, "UTILITY")
        if support:
            partners.append((support, "bot_lane", "bot lane"))
    elif role == "JUNGLE":
        support = _champion_for_role(pick_team, "UTILITY")
        if support:
            partners.append((support, "jungle_support", "jungle-support"))
    elif role == "UTILITY":
        adc = _champion_for_role(pick_team, "BOTTOM")
        jungle = _champion_for_role(pick_team, "JUNGLE")
        if adc:
            partners.append((adc, "bot_lane", "bot lane"))
        if jungle:
            partners.append((jungle, "jungle_support", "jungle-support"))

    best: dict[str, Any] | None = None
    for partner, duo_type, lane_label in partners:
        duo = get_duo_score(champion, partner, duo_type, mode=mode)
        if duo.score is None or duo.insufficient_data or duo.games < 5:
            continue
        if best is None or float(duo.score) > float(best["winrate"]):
            best = {
                "partner": partner,
                "lane_label": lane_label,
                "winrate": float(duo.score),
                "games": int(duo.games),
            }
    return best


def _lane_gold_at_15(champion: str, role: str) -> float | None:
    stats = lookup_champion_profile_stats(champion, role)
    if stats is None or stats.golddiffat15 is None:
        return None
    if abs(stats.golddiffat15) < 50:
        return None
    return float(stats.golddiffat15)


def _lane_cs_at_15(champion: str, role: str) -> float | None:
    stats = lookup_champion_profile_stats(champion, role)
    if stats is None or stats.csdiffat15 is None:
        return None
    if abs(stats.csdiffat15) < 3:
        return None
    return float(stats.csdiffat15)


def _display_name(key_or_name: str, original_names: list[str]) -> str:
    folded = key_or_name.casefold()
    for name in original_names:
        if name.casefold() == folded or name.casefold().replace(" ", "") == folded:
            return name
    return key_or_name


def _team_role_contributors(
    team_champions: list[str],
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Retourne (engageurs, peelers, early, late) avec noms d'affichage."""
    keys = _resolve_team_champions(team_champions)
    engageurs: list[str] = []
    peelers: list[str] = []
    early: list[str] = []
    late: list[str] = []

    from composition_archetype import _champion_power_curve, _ratings_for

    for key, original in zip(keys, team_champions):
        roles = _roles_for(key)
        name = _display_name(key, [original])
        if _role_weight_sum_local(roles, ENGAGE_ROLE_WEIGHTS) >= 0.7:
            engageurs.append(name)
        if _role_weight_sum_local(roles, PEEL_ROLE_WEIGHTS) >= 0.7:
            peelers.append(name)
        curve = _champion_power_curve(_ratings_for(key))
        if curve <= -0.25:
            early.append(name)
        elif curve >= 0.25:
            late.append(name)
    return engageurs, peelers, early, late


def _role_weight_sum_local(roles: list[str], weights: dict[str, float]) -> float:
    return sum(weights.get(role, 0.0) for role in roles)


def _pro_winrate_line(champion: str, role: str) -> tuple[float, int] | None:
    try:
        champion_features, _, lookup_by_norm = get_meraki_context()
        scored = pro_meta_score(champion, role, champion_features, lookup_by_norm)
    except (FileNotFoundError, ValueError):
        return None
    if scored is None:
        return None
    _meta, games, winrate, _fitness, _name = scored
    return float(winrate), int(games)


def _format_teammates(so_far: list[str], limit: int = 3) -> str:
    names = [name.strip() for name in so_far if name.strip()]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} et {names[1]}"
    visible = names[:limit]
    return ", ".join(visible[:-1]) + f" et {visible[-1]}"


def _comp_plan_label(before: dict[str, Any]) -> str | None:
    engage = float(before.get("engage_score", 0.0))
    peel = float(before.get("peel_score", 0.0))
    curve = float(before.get("power_curve", 0.0))
    balance = float((before.get("damage_profile") or {}).get("damage_balance", 1.0))

    if engage >= 0.4 and peel < 0.22:
        return "dive"
    if curve >= 0.08:
        return "scaling"
    if curve <= -0.12:
        return "early"
    if balance < 0.45:
        return "damage_mix"
    return None


def build_pick_justification_dict(
    champion: str,
    role: str,
    team_context: list[dict[str, str]] | None,
    opponent_context: list[dict[str, str]] | None,
    *,
    mode: PredictionMode = "pro",
    scoring: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construit un dict structuré (meta / composition / duo / stats) pour un pick."""
    role = normalize_role(role)
    pick_team = list(team_context or [])
    opponents = list(opponent_context or [])

    row = lookup_meta_tierlist_row(champion, role)
    meta_kind: MetaKind = "credible"
    trend: str | None = None
    ban_rate: float | None = None
    games: int | None = None
    if row is not None:
        ban_rate = float(row.ban_rate)
        games = int(row.games)
        if row.ban_rate >= SIGNIFICANT_BAN_RATE:
            meta_kind = "often_banned"
        elif row.games >= 30:
            meta_kind = "established"
        elif row.games > 0:
            meta_kind = "niche"
        raw = str(row.trend_raw or "")
        for label in ("hausse", "baisse", "stable"):
            if raw.lower().startswith(label):
                trend = label
                break

    so_far = _team_champions_excluding_role(pick_team, role)
    shifts: list[ShiftKind] = []
    comp_plan: str | None = None
    if so_far:
        before = compute_composition_archetype(so_far)
        after = compute_composition_archetype(so_far + [champion])
        comp_plan = _comp_plan_label(before)
        raw_shifts = _describe_archetype_shift(before, after)
        mapping = {
            "comble un manque de peel": "peel",
            "renforce l'engage": "engage",
            "accélère le tempo early": "early",
            "renforce un profil scaling déjà engagé": "scaling",
            "équilibre le profil de dégâts AD/AP": "damage_balance",
        }
        for label, key in mapping.items():
            if label in raw_shifts:
                shifts.append(key)  # type: ignore[arg-type]

    duo_details = _resolve_duo_details(champion, role, pick_team, mode=mode)
    lane_opponent = _champion_for_role(opponents, role)
    my_gold = _lane_gold_at_15(champion, role)
    my_cs = _lane_cs_at_15(champion, role)
    opp_gold = _lane_gold_at_15(lane_opponent, role) if lane_opponent else None

    my_pro = _pro_winrate_line(champion, role) if mode == "pro" else None
    opp_pro = (
        _pro_winrate_line(lane_opponent, role)
        if lane_opponent and mode == "pro"
        else None
    )

    damage_before = compute_composition_archetype(so_far) if so_far else None
    damage_after = (
        compute_composition_archetype(so_far + [champion]) if so_far else None
    )

    score_payload = scoring or {}

    return {
        "meta_kind": meta_kind,
        "trend": trend,
        "ban_rate": ban_rate,
        "games": games,
        "composition_shifts": shifts,
        "comp_plan": comp_plan,
        "teammates": so_far,
        "duo": duo_details,
        "lane_opponent": lane_opponent,
        "my_gold_at_15": my_gold,
        "my_cs_at_15": my_cs,
        "opp_gold_at_15": opp_gold,
        "my_pro_winrate": my_pro[0] if my_pro else None,
        "my_pro_games": my_pro[1] if my_pro else None,
        "opp_pro_winrate": opp_pro[0] if opp_pro else None,
        "opp_pro_games": opp_pro[1] if opp_pro else None,
        "win_probability": score_payload.get("win_probability"),
        "pair_planning_bonus": score_payload.get("pair_planning_bonus"),
        "lookahead_duo_bonus": score_payload.get("lookahead_duo_bonus"),
        "comp_direction_bonus": score_payload.get("comp_direction_bonus"),
        "opponent_counter_bonus": score_payload.get("opponent_counter_bonus"),
        "archetype_score": score_payload.get("archetype_score"),
        "damage_before": damage_before,
        "damage_after": damage_after,
    }


def build_plain_pick_explanation(
    champion: str,
    role: str,
    justification_technique: dict[str, Any],
) -> str:
    """Retraduit une justification technique en argument convaincant à la 1re personne."""
    role = normalize_role(role)
    role_fr = ROLE_LABELS_FR.get(role, role.lower())
    teammates = list(justification_technique.get("teammates") or [])
    team_label = _format_teammates(teammates)
    comp_plan = justification_technique.get("comp_plan")
    win_prob = justification_technique.get("win_probability")
    pair_bonus = float(justification_technique.get("pair_planning_bonus") or 0.0)

    lead: str | None = None
    support: list[str] = []

    duo = justification_technique.get("duo")
    if isinstance(duo, dict) and duo.get("partner") and float(duo.get("winrate", 0)) >= 0.51:
        wr = float(duo["winrate"]) * 100
        partner = duo["partner"]
        lane = duo.get("lane_label", "duo")
        duo_games = int(duo.get("games", 0))
        lead = (
            f"Je lock {champion} parce qu'avec {partner}, notre {lane} affiche "
            f"{wr:.1f}% de winrate pro sur {duo_games} games — c'est le duo le plus fiable "
            f"disponible pour moi sur ce slot."
        )
    elif pair_bonus >= 1.0 and teammates:
        lead = (
            f"Je prends {champion} en {role_fr} parce que c'est le meilleur chaînon "
            f"pour compléter {team_label} : en simulant la suite de la draft, "
            "c'est le pick qui maximise notre winrate d'équipe."
        )

    shifts: list[str] = list(justification_technique.get("composition_shifts") or [])
    if not lead and shifts and teammates:
        shift = shifts[0]
        if shift == "peel":
            lead = (
                f"Avec {team_label} déjà lockés, on partait en comp agressive sans filet : "
                f"{champion} apporte enfin du peel pour sécuriser nos carries en fight."
            )
        elif shift == "engage":
            lead = (
                f"{team_label} posent une base solide, mais il nous manquait un vrai bouton "
                f"d'engage — {champion} me permet de forcer l'ouverture quand je le décide."
            )
        elif shift == "early":
            lead = (
                f"Notre draft avec {team_label} cherche le tempo early : "
                f"{champion} accélère le plan au lieu de nous laisser scaler passivement."
            )
        elif shift == "scaling":
            lead = (
                f"On a {team_label} pour tenir le mid game ; "
                f"{champion} renforce notre scaling et allonge la fenêtre où on devient dangereux."
            )
        elif shift == "damage_balance":
            before = justification_technique.get("damage_before") or {}
            after = justification_technique.get("damage_after") or {}
            before_phys = int((before.get("damage_profile") or {}).get("physical_count", 0))
            before_mag = int((before.get("damage_profile") or {}).get("magic_count", 0))
            after_phys = int((after.get("damage_profile") or {}).get("physical_count", 0))
            after_mag = int((after.get("damage_profile") or {}).get("magic_count", 0))
            lead = (
                f"On était trop prévisibles en dégâts ({before_phys} AD / {before_mag} AP) "
                f"avec {team_label} — {champion} nous passe à {after_phys} AD / {after_mag} AP, "
                "donc plus dur à itemiser pour l'adversaire."
            )

    lane_opponent = justification_technique.get("lane_opponent")
    my_pro_wr = justification_technique.get("my_pro_winrate")
    opp_pro_wr = justification_technique.get("opp_pro_winrate")
    my_pro_games = justification_technique.get("my_pro_games")
    if not lead and lane_opponent and my_pro_wr is not None and opp_pro_wr is not None:
        margin = (float(my_pro_wr) - float(opp_pro_wr)) * 100
        if margin >= 1.5:
            games_bit = f" sur {my_pro_games} games" if my_pro_games else ""
            lead = (
                f"Tu as déjà {lane_opponent} en face : je prends {champion} parce qu'en pro "
                f"il sort à {float(my_pro_wr)*100:.1f}%{games_bit} contre "
                f"{float(opp_pro_wr)*100:.1f}% pour {lane_opponent} sur le même rôle — "
                "c'est mon meilleur counter crédible."
            )
        elif margin <= -1.5:
            lead = (
                f"Je sais que {lane_opponent} est favori en winrate pro "
                f"({float(opp_pro_wr)*100:.1f}% vs {float(my_pro_wr)*100:.1f}%), "
                f"mais {champion} limite le snowball adverse et garde notre plan d'équipe intact."
            )

    my_gold = justification_technique.get("my_gold_at_15")
    opp_gold = justification_technique.get("opp_gold_at_15")
    if not lead and lane_opponent and my_gold is not None and opp_gold is not None:
        if float(my_gold) > float(opp_gold) + 30:
            lead = (
                f"Face à ton {lane_opponent}, {champion} sort en moyenne "
                f"{int(round(my_gold)):+d} gold à 15 min contre "
                f"{int(round(opp_gold)):+d} pour lui — je veux gagner la lane, pas juste survive."
            )

    meta_kind = justification_technique.get("meta_kind") or "credible"
    ban_rate = justification_technique.get("ban_rate")
    games = justification_technique.get("games")
    trend = justification_technique.get("trend")

    if not lead:
        if meta_kind == "often_banned" and ban_rate is not None:
            ban_pct = int(round(float(ban_rate) * 100))
            lead = (
                f"{champion} en {role_fr}, je ne peux pas le laisser rotater : "
                f"les pros le bannissent {ban_pct}% du temps, signe qu'il domine le meta actuel."
            )
        elif my_pro_wr is not None and my_pro_games and int(my_pro_games) >= 20:
            lead = (
                f"Je prends {champion} en {role_fr} : "
                f"{float(my_pro_wr)*100:.1f}% de winrate pro sur {my_pro_games} games sur ce poste."
            )
        elif meta_kind == "established" and games is not None:
            lead = (
                f"{champion} est mon pick {role_fr} le plus sûr : "
                f"{games} games pro sur le patch, pick établi que je peux blind."
            )
        elif comp_plan == "dive" and role in {"UTILITY", "JUNGLE"}:
            lead = (
                f"Notre draft part en dive — {champion} en {role_fr} "
                "est le chaînon qui manquait pour convertir les engages."
            )
        elif comp_plan == "scaling" and role in {"BOTTOM", "MIDDLE"}:
            lead = (
                f"On scale avec {team_label or 'la compo en cours'} : "
                f"{champion} en {role_fr} porte notre win condition late."
            )
        else:
            lead = (
                f"Je lock {champion} en {role_fr} parce que c'est le candidat "
                "qui maximise notre winrate estimé sur le pool restant."
            )

    if shifts and teammates and lead:
        shift = shifts[0]
        if shift == "peel" and "peel" not in lead.lower():
            support.append(
                f"Avec {team_label} déjà lockés, {champion} apporte le peel "
                "qui manquait pour protéger nos carries en fight."
            )
        elif shift == "engage" and "engage" not in lead.lower():
            support.append(
                f"Sur {team_label}, on avait besoin d'un bouton d'engage — "
                f"{champion} le fournit sans casser le plan."
            )
        elif shift == "damage_balance" and "dégâts" not in lead.lower():
            before = justification_technique.get("damage_before") or {}
            after = justification_technique.get("damage_after") or {}
            before_phys = int((before.get("damage_profile") or {}).get("physical_count", 0))
            before_mag = int((before.get("damage_profile") or {}).get("magic_count", 0))
            after_phys = int((after.get("damage_profile") or {}).get("physical_count", 0))
            after_mag = int((after.get("damage_profile") or {}).get("magic_count", 0))
            support.append(
                f"On passe de {before_phys} AD / {before_mag} AP à {after_phys} AD / {after_mag} AP "
                f"avec {team_label} — l'adversaire ne peut plus stack une seule résistance."
            )
        elif shift == "early" and "early" not in lead.lower():
            support.append(
                f"Ça accélère notre tempo avec {team_label} au lieu de nous laisser scaler passivement."
            )
        elif shift == "scaling" and "scaling" not in lead.lower():
            support.append(
                f"Ça renforce notre scaling autour de {team_label} pour gagner le late game."
            )

    if comp_plan and teammates and lead and comp_plan not in lead.lower():
        if comp_plan == "dive":
            support.append(
                f"Notre draft part en dive avec {team_label} — {champion} "
                "est le chaînon qui convertit les engages."
            )
        elif comp_plan == "scaling":
            support.append(
                f"On scale autour de {team_label} ; {champion} porte la win condition late."
            )
        elif comp_plan == "early":
            support.append(
                f"Le plan early avec {team_label} demande ce type de pick pour punir avant le scaling adverse."
            )

    if lane_opponent and lead and lane_opponent not in lead:
        if my_pro_wr is not None and opp_pro_wr is not None:
            margin = (float(my_pro_wr) - float(opp_pro_wr)) * 100
            if margin >= 1.5:
                games_bit = f" sur {my_pro_games} games" if my_pro_games else ""
                support.append(
                    f"Face à {lane_opponent}, {champion} sort à {float(my_pro_wr)*100:.1f}%{games_bit} "
                    f"contre {float(opp_pro_wr)*100:.1f}% pour lui — je joue le counter crédible."
                )
            elif margin <= -1.5:
                support.append(
                    f"{lane_opponent} domine en winrate pro ({float(opp_pro_wr)*100:.1f}% vs "
                    f"{float(my_pro_wr)*100:.1f}%), mais {champion} limite son snowball lane."
                )
        elif my_gold is not None and "gold" not in lead.lower():
            opp_bit = (
                f" contre {int(round(opp_gold)):+d} pour {lane_opponent}"
                if opp_gold is not None
                else f" face à {lane_opponent}"
            )
            support.append(
                f"Historiquement, {champion} sort {int(round(my_gold)):+d} gold à 15 min{opp_bit} "
                "— je veux gagner la lane, pas juste survive."
            )

    if win_prob is not None and float(win_prob) > 0:
        support.append(
            f"Après ce pick, j'estime notre winrate draft à {float(win_prob)*100:.1f}%."
        )

    if trend == "hausse" and meta_kind == "established" and len(support) < 2:
        support.append("Sa présence en pro monte en ce moment.")
    elif (
        my_gold is not None
        and lane_opponent
        and "gold" not in lead.lower()
        and not any("gold" in s.lower() for s in support)
    ):
        support.append(
            f"Historiquement, {champion} sort {int(round(my_gold)):+d} gold à 15 min en {role_fr}."
        )
    elif (
        justification_technique.get("my_cs_at_15") is not None
        and lane_opponent
        and len(support) < 2
    ):
        cs = int(round(float(justification_technique["my_cs_at_15"])))
        support.append(
            f"Son profil de farm ({cs:+d} CS à 15 min) me permet de stabiliser la lane."
        )

    parts = [lead, *support[:3]]
    return _scrub(" ".join(part for part in parts if part))


def generate_bot_pick_reason(
    champion: str,
    role: str,
    team_context: list[dict[str, str]] | None,
    opponent_context: list[dict[str, str]] | None,
    *,
    mode: PredictionMode = "pro",
    scoring: dict[str, Any] | None = None,
) -> str:
    """Justification convaincante pour un pick bot (visual novel + reason API)."""
    technical = build_pick_justification_dict(
        champion,
        role,
        team_context,
        opponent_context,
        mode=mode,
        scoring=scoring,
    )
    return build_plain_pick_explanation(champion, role, technical)


def generate_bot_ban_reason(
    champion: str,
    role: str,
    opponent_partial: list[dict[str, str]] | None,
    team_context: list[dict[str, str]] | None,
    *,
    threat_points: float,
    duo_denial_boost: float,
    flex_roles: int,
    opponent_win_probability: float,
    mode: PredictionMode = "pro",
) -> str:
    """Justification convaincante pour un ban bot à la 1re personne."""
    role_fr = ROLE_LABELS_FR.get(normalize_role(role), role.lower())
    teammates = _format_teammates(
        _team_champions_excluding_role(list(opponent_partial or []), role)
    )
    row = lookup_meta_tierlist_row(champion, role)
    ban_rate_pct = int(round(float(row.ban_rate) * 100)) if row else None
    games = int(row.games) if row else None

    lead: str
    if duo_denial_boost >= 2.0 and teammates:
        lead = (
            f"Je ban {champion} parce qu'avec {teammates} déjà visible, "
            f"il complète un duo pro trop dangereux — je coupe leur win condition "
            f"avant qu'ils le lockent en {role_fr}."
        )
    elif flex_roles >= 2:
        lead = (
            f"Je ban {champion} : il flex sur {flex_roles} rôles restants chez toi, "
            f"donc je lui retire plusieurs options de draft d'un coup."
        )
    elif ban_rate_pct is not None and ban_rate_pct >= 15:
        lead = (
            f"Je ban {champion} en priorité — {ban_rate_pct}% de ban rate pro "
            f"sur le patch, je ne veux pas le affronter en {role_fr}."
        )
    elif threat_points >= 1.5:
        lead = (
            f"Je ban {champion} parce que s'il tombe en {role_fr}, "
            f"ton winrate draft monte de {threat_points:.1f} pts "
            f"(j'estime ton équipe à {opponent_win_probability * 100:.1f}% si tu le récupères)."
        )
    elif games is not None and games >= 30:
        lead = (
            f"Je ban {champion} : c'est le power pick {role_fr} le plus menaçant "
            f"disponible ({games} games pro sur le patch)."
        )
    else:
        lead = (
            f"Je ban {champion} parce que c'est la menace la plus crédible "
            f"que je peux retirer de ton pool en {role_fr}."
        )

    support: list[str] = []
    if threat_points >= 0.5 and "winrate draft" not in lead:
        support.append(
            f"Simulation : ce ban te coûte environ {threat_points:.1f} pts de winrate adverse."
        )
    if row and row.presence_score >= 0.08:
        support.append(
            f"Sa présence pro est élevée — je préfère le retirer maintenant plutôt qu'en affrontement direct."
        )

    return _scrub(" ".join(part for part in [lead, *support[:1]] if part))


def build_plain_team_synergy_summary(
    team_champions: list[str],
    archetype_data: dict[str, Any] | None = None,
) -> str:
    """Synthèse parlée précise du profil d'équipe (sans jargon technique)."""
    names = [c.strip() for c in team_champions if c and c.strip()]
    data = archetype_data or compute_composition_archetype(names)

    power = float(data.get("power_curve", 0.0))
    engage = float(data.get("engage_score", 0.0))
    peel = float(data.get("peel_score", 0.0))
    damage = data.get("damage_profile") or {}
    physical = int(damage.get("physical_count", 0))
    magic = int(damage.get("magic_count", 0))
    magic_ratio = float(damage.get("magic_ratio", 0.5))
    balance = float(damage.get("damage_balance", 1.0))

    engageurs, peelers, early, late = _team_role_contributors(names)

    if power <= -0.25:
        tempo = (
            "Mon plan : imposer le tempo en early"
            + (f" avec {', '.join(early[:2])} en tête de pont" if early else "")
            + ", punir les erreurs avant le scaling adverse."
        )
    elif power >= 0.25:
        tempo = (
            "Mon plan : survivre au mid game puis gagner le late"
            + (f" autour de {', '.join(late[:2])}" if late else "")
            + " quand nos items tournent."
        )
    else:
        tempo = (
            "Mon plan : rester flexible sur le timing — "
            "je peux forcer une fight ou slow push selon ce que tu me laisses."
        )

    bits: list[str] = [tempo]

    if engage >= 0.55 and engageurs:
        bits.append(
            f"on engage avec {', '.join(engageurs[:2])} "
            "pour ouvrir les combats quand on le décide"
        )
    elif engage >= 0.55:
        bits.append("on a assez d'outils pour forcer les engagements")

    if peel >= 0.55 and peelers:
        bits.append(
            f"et {', '.join(peelers[:2])} protègent nos carries en late fight"
        )
    elif peel >= 0.55:
        bits.append("et on a de quoi protéger nos carries")

    if physical or magic:
        if balance >= 0.7:
            bits.append(
                f"côté dégâts on est mixtes ({physical} physiques / {magic} magiques), "
                "donc plus durs à itemizer"
            )
        elif magic_ratio >= 0.6:
            bits.append(
                f"attention : on penche magie ({magic} AP / {physical} AD) — "
                "il faudra bien jouer les angles"
            )
        elif magic_ratio <= 0.4:
            bits.append(
                f"attention : on penche physique ({physical} AD / {magic} AP) — "
                "l'adversaire pourra stacker l'armure"
            )

    if len(bits) == 1:
        bits.append("et la synergie d'ensemble me convient pour exécuter le plan")

    if len(bits) == 2:
        summary = f"{bits[0]}, {bits[1]}."
    else:
        summary = f"{bits[0]}, {bits[1]}, {bits[2]}."

    return _scrub(summary)


def build_bot_explanation_steps(
    bot_picks: list[dict[str, str]],
    opponent_picks: list[dict[str, str]],
    *,
    mode: PredictionMode = "pro",
) -> list[dict[str, Any]]:
    """5 explications de pick (ordre des rôles) + synthèse de synergie."""
    by_role: dict[str, dict[str, str]] = {}
    for slot in bot_picks:
        role = normalize_role(slot["role"])
        champion = slot["champion"].strip()
        if champion:
            by_role[role] = {"champion": champion, "role": role}

    steps: list[dict[str, Any]] = []
    ordered_names: list[str] = []

    for role in ROLE_ORDER:
        slot = by_role.get(role)
        if slot is None:
            continue
        champion = slot["champion"]
        ordered_names.append(champion)
        technical = build_pick_justification_dict(
            champion,
            role,
            bot_picks,
            opponent_picks,
            mode=mode,
        )
        steps.append(
            {
                "champion": champion,
                "role": role,
                "text": build_plain_pick_explanation(champion, role, technical),
            }
        )

    archetype = compute_composition_archetype(ordered_names)
    steps.append(
        {
            "champion": None,
            "role": None,
            "text": build_plain_team_synergy_summary(ordered_names, archetype),
        }
    )
    return steps
