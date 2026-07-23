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
from predict_draft import PredictionMode

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


def build_pick_justification_dict(
    champion: str,
    role: str,
    team_context: list[dict[str, str]] | None,
    opponent_context: list[dict[str, str]] | None,
    *,
    mode: PredictionMode = "pro",
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
    if so_far:
        before = compute_composition_archetype(so_far)
        after = compute_composition_archetype(so_far + [champion])
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

    damage_before = compute_composition_archetype(so_far) if so_far else None
    damage_after = (
        compute_composition_archetype(so_far + [champion]) if so_far else None
    )

    return {
        "meta_kind": meta_kind,
        "trend": trend,
        "ban_rate": ban_rate,
        "games": games,
        "composition_shifts": shifts,
        "duo": duo_details,
        "lane_opponent": lane_opponent,
        "my_gold_at_15": my_gold,
        "my_cs_at_15": my_cs,
        "opp_gold_at_15": opp_gold,
        "damage_before": damage_before,
        "damage_after": damage_after,
    }


def build_plain_pick_explanation(
    champion: str,
    role: str,
    justification_technique: dict[str, Any],
) -> str:
    """Retraduit une justification technique en phrase parlée à la 1re personne."""
    role = normalize_role(role)
    role_fr = ROLE_LABELS_FR.get(role, role.lower())
    parts: list[str] = []

    meta_kind = justification_technique.get("meta_kind") or "credible"
    trend = justification_technique.get("trend")
    ban_rate = justification_technique.get("ban_rate")
    games = justification_technique.get("games")

    if meta_kind == "often_banned" and ban_rate is not None:
        ban_pct = int(round(float(ban_rate) * 100))
        games_bit = f", sur {games} games pickées" if games else ""
        parts.append(
            _pick(
                [
                    "J'ai pris {champion} parce que c'est une vraie menace en {role} — les pros le bannissent dans {ban_pct}% des games{games_bit}.",
                    "{champion} en {role}, trop dangereux à laisser passer : {ban_pct}% de ban rate en pro{games_bit}.",
                ],
                champion=champion,
                role=role_fr,
                ban_pct=ban_pct,
                games_bit=games_bit,
            )
        )
    elif meta_kind == "established" and games is not None:
        base = (
            f"J'ai pris {champion} en {role_fr} parce que c'est un pick établi "
            f"en pro ({games} games sur ce poste)."
        )
        if trend == "hausse":
            base += " Et la tendance monte en ce moment."
        elif trend == "baisse":
            base += " Même s'il est un peu moins joué qu'avant, le volume reste solide."
        parts.append(base)
    elif meta_kind == "niche" and games is not None:
        parts.append(
            f"J'ai sorti {champion} en {role_fr} — peu joué en pro ({games} games), "
            "mais ça me donne un angle moins préparé."
        )
    else:
        parts.append(
            f"J'ai pris {champion} en {role_fr} — un choix crédible pour ce que je voulais ici."
        )

    shifts: list[str] = list(justification_technique.get("composition_shifts") or [])
    damage_before = justification_technique.get("damage_before") or {}
    damage_after = justification_technique.get("damage_after") or {}
    for shift in shifts[:2]:
        if shift == "peel":
            parts.append(
                "En plus, ça apporte enfin de la protection (peel) : "
                "on manquait de filets de sécu pour nos carries."
            )
        elif shift == "engage":
            parts.append(
                "En plus, ça me donne un vrai outil d'engage pour ouvrir les fights "
                "au lieu d'attendre que l'adversaire décide."
            )
        elif shift == "early":
            parts.append(
                "En plus, ça accélère notre début de partie — "
                "on veut forcer le tempo avant que l'adversaire scale."
            )
        elif shift == "scaling":
            parts.append(
                "En plus, ça renforce notre late game : "
                "plus on avance, plus notre compo devient dangereuse."
            )
        elif shift == "damage_balance":
            before_phys = int((damage_before.get("damage_profile") or {}).get("physical_count", 0))
            before_mag = int((damage_before.get("damage_profile") or {}).get("magic_count", 0))
            after_phys = int((damage_after.get("damage_profile") or {}).get("physical_count", 0))
            after_mag = int((damage_after.get("damage_profile") or {}).get("magic_count", 0))
            parts.append(
                f"En plus, ça rééquilibre nos dégâts "
                f"(on passe de {before_phys} AD / {before_mag} AP "
                f"à {after_phys} AD / {after_mag} AP) — plus dur à itemizer contre nous."
            )

    duo = justification_technique.get("duo")
    if isinstance(duo, dict) and duo.get("partner"):
        wr = float(duo["winrate"]) * 100
        partner = duo["partner"]
        lane = duo.get("lane_label", "duo")
        duo_games = int(duo.get("games", 0))
        parts.append(
            f"Avec {partner}, le duo {lane} tient la route en pro : "
            f"environ {wr:.1f}% de winrate sur {duo_games} games ensemble."
        )
    elif justification_technique.get("duo_partner"):
        # Compat anciens appels de test
        partner = justification_technique["duo_partner"]
        parts.append(
            f"Avec {partner}, ces deux-là ont une synergie de duo mesurée en pro."
        )

    lane_opponent = justification_technique.get("lane_opponent")
    my_gold = justification_technique.get("my_gold_at_15")
    my_cs = justification_technique.get("my_cs_at_15")
    opp_gold = justification_technique.get("opp_gold_at_15")

    if lane_opponent:
        if my_gold is not None and opp_gold is not None:
            if my_gold > opp_gold + 30:
                parts.append(
                    f"Face à ton {lane_opponent}, le matchup me plaît sur les chiffres : "
                    f"{champion} sort en moyenne {int(round(my_gold)):+d} gold à 15 min en {role_fr}, "
                    f"contre {int(round(opp_gold)):+d} pour {lane_opponent}."
                )
            elif my_gold < opp_gold - 30:
                parts.append(
                    f"Face à ton {lane_opponent}, je ne nie pas que sa lane est forte "
                    f"({int(round(opp_gold)):+d} gold à 15 min en moyenne), "
                    f"mais {champion} reste mon meilleur outil pour limiter les dégâts."
                )
            else:
                parts.append(
                    f"Contre ton {lane_opponent}, les lanes sont proches en gold à 15 "
                    f"({champion} {int(round(my_gold)):+d}, "
                    f"{lane_opponent} {int(round(opp_gold)):+d}) — "
                    "je joue sur l'exécution et le reste de la compo."
                )
        elif my_gold is not None:
            parts.append(
                f"Contre ton {lane_opponent}, je m'appuie sur le profil de lane de {champion} : "
                f"en moyenne {int(round(my_gold)):+d} gold à 15 minutes en {role_fr}."
            )
        elif my_cs is not None:
            parts.append(
                f"Contre ton {lane_opponent}, {champion} a un profil de farm solide "
                f"({int(round(my_cs)):+d} CS à 15 min en moyenne en {role_fr})."
            )
        else:
            parts.append(
                f"Contre ton {lane_opponent}, je prends {champion} pour le plan d'équipe "
                "plus que pour un counter parfait 1v1."
            )
    elif my_gold is not None:
        parts.append(
            f"Sur ce poste, {champion} affiche en moyenne "
            f"{int(round(my_gold)):+d} gold à 15 minutes — un profil de lane concret."
        )

    return _scrub(" ".join(parts))


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
            "Au final, mon équipe veut imposer le rythme en early"
            + (f" grâce à {', '.join(early[:2])}" if early else "")
        )
    elif power >= 0.25:
        tempo = (
            "Au final, mon équipe scale vers le late"
            + (f" avec {', '.join(late[:2])} comme menaces principales" if late else "")
        )
    else:
        tempo = "Au final, mon équipe reste flexible sur le timing des fights"

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
