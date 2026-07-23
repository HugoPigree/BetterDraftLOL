"""Reformulation parlée des justifications techniques du bot Rival."""

from __future__ import annotations

import random
from typing import Any, Literal

from composition_archetype import compute_composition_archetype
from justification_builder import (
    ROLE_LABELS_FR,
    _build_composition_sentence,
    _build_duo_sentence,
    _build_meta_sentence,
    _build_stats_sentence,
    _champion_for_role,
    _describe_archetype_shift,
    _team_champions_excluding_role,
    generate_pick_justification,
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
CoherenceKind = Literal["strong", "weak", "ok"]
ShiftKind = Literal["peel", "engage", "early", "scaling", "damage_balance"]


def _pick(templates: list[str], **kwargs: Any) -> str:
    return random.choice(templates).format(**kwargs)


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

    meta_sentence = _build_meta_sentence(champion, role, mode=mode)
    composition_sentence = _build_composition_sentence(
        champion,
        role,
        pick_team,
        archetype_score=None,
        decomposition=None,
        changed_side="team",
    )
    duo_sentence = _build_duo_sentence(champion, role, pick_team, mode=mode)
    stats_sentence = _build_stats_sentence(
        champion,
        role,
        decomposition=None,
        changed_side="team",
    )

    row = lookup_meta_tierlist_row(champion, role)
    meta_kind: MetaKind = "credible"
    trend: str | None = None
    if row is not None:
        if row.ban_rate >= 0.15:
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
    coherence: CoherenceKind | None = None
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
        if not shifts:
            coherence = "ok"

    duo_partner: str | None = None
    if role == "BOTTOM":
        duo_partner = _champion_for_role(pick_team, "UTILITY")
    elif role == "JUNGLE":
        duo_partner = _champion_for_role(pick_team, "UTILITY")
    elif role == "UTILITY":
        duo_partner = _champion_for_role(pick_team, "BOTTOM") or _champion_for_role(
            pick_team, "JUNGLE"
        )

    lane_opponent = _champion_for_role(opponents, role)

    return {
        "meta": meta_sentence,
        "composition": composition_sentence,
        "duo": duo_sentence,
        "stats": stats_sentence,
        "meta_kind": meta_kind,
        "trend": trend,
        "composition_shifts": shifts,
        "coherence": coherence,
        "duo_partner": duo_partner,
        "lane_opponent": lane_opponent,
        "technical_full": generate_pick_justification(
            champion,
            role,
            pick_team,
            opponents,
            source_data={"mode": mode, "pick_side": "team", "changed_side": "team"},
        ),
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

    if meta_kind == "often_banned":
        parts.append(
            _pick(
                [
                    "J'ai pris {champion} parce que c'est une vraie menace en {role} — les pros le bannissent souvent pour une raison.",
                    "{champion} en {role}, c'est le genre de pick qui fait peur : trop dangereux pour le laisser passer.",
                    "Sur {role}, {champion} s'imposait — c'est un choix que beaucoup préfèrent voir de l'autre côté de la draft.",
                ],
                champion=champion,
                role=role_fr,
            )
        )
    elif meta_kind == "established":
        base = _pick(
            [
                "J'ai pris {champion} parce que c'est un choix solide et éprouvé en ce moment sur ce poste.",
                "{champion} en {role}, c'est safe et fiable — exactement ce que je voulais ici.",
                "Sur {role}, j'ai verrouillé {champion} : un pick qui a fait ses preuves.",
            ],
            champion=champion,
            role=role_fr,
        )
        if trend == "hausse":
            base += " Et en plus, ça monte en ce moment."
        elif trend == "baisse":
            base += " Même s'il est un peu moins à la mode, ça reste un bon outil."
        parts.append(base)
    elif meta_kind == "niche":
        parts.append(
            _pick(
                [
                    "J'ai sorti {champion} en {role} pour sortir un peu des sentiers battus, sans être n'importe quoi.",
                    "{champion} n'est pas le pick le plus joué en {role}, mais ça me va très bien dans cette draft.",
                ],
                champion=champion,
                role=role_fr,
            )
        )
    else:
        parts.append(
            _pick(
                [
                    "J'ai pris {champion} en {role} — un choix crédible pour ce qu'il me fallait.",
                    "Sur {role}, {champion} rentrait pile dans ce que je cherchais.",
                ],
                champion=champion,
                role=role_fr,
            )
        )

    shifts: list[str] = list(justification_technique.get("composition_shifts") or [])
    shift_lines = {
        "peel": [
            "En plus, ça apporte de la protection à mon équipe, ce qui nous manquait.",
            "Et ça me donne enfin de quoi protéger mon équipe quand ça chauffe.",
        ],
        "engage": [
            "En plus, ça me donne un vrai moyen d'engager et de forcer les fights.",
            "Et avec ça, on peut enfin ouvrir les combats nous-mêmes.",
        ],
        "early": [
            "En plus, ça accélère notre début de partie — on ne veut pas attendre.",
            "Et ça nous pousse vers un plan plus agressif dès le early.",
        ],
        "scaling": [
            "En plus, ça renforce notre late game : on scale tranquillement.",
            "Et ça nous aide à être encore plus dangereux plus tard dans la partie.",
        ],
        "damage_balance": [
            "En plus, ça équilibre mieux nos dégâts — moins facile à itemizer contre nous.",
            "Et ça diversifie nos sources de dégâts, ce qui embête l'adversaire.",
        ],
    }
    for shift in shifts[:2]:
        options = shift_lines.get(shift)
        if options:
            parts.append(random.choice(options))

    duo_partner = justification_technique.get("duo_partner")
    if duo_partner:
        parts.append(
            _pick(
                [
                    "Avec {partner}, ces deux-là fonctionnent bien ensemble.",
                    "Et avec {partner} à mes côtés, le duo est vraiment confortable.",
                    "Je compte aussi sur la synergie avec {partner} — ça matche bien.",
                ],
                partner=duo_partner,
            )
        )

    lane_opponent = justification_technique.get("lane_opponent")
    if lane_opponent:
        parts.append(
            _pick(
                [
                    "Et honnêtement, face à ton {opponent}, je pense que j'ai l'avantage dans ce duel direct.",
                    "Contre ton {opponent}, je suis plutôt confiant sur le matchup de lane.",
                    "Face à {opponent}, ce pick me plaît — j'aime bien ce duel.",
                ],
                opponent=lane_opponent,
            )
        )

    text = " ".join(parts)
    for banned in TECHNICAL_BLACKLIST:
        if banned in text:
            text = text.replace(banned, "")
    return " ".join(text.split())


def build_plain_team_synergy_summary(
    team_champions: list[str],
    archetype_data: dict[str, Any] | None = None,
) -> str:
    """Synthèse parlée du profil d'équipe (sans jargon technique)."""
    names = [c.strip() for c in team_champions if c and c.strip()]
    data = archetype_data or compute_composition_archetype(names)

    power = float(data.get("power_curve", 0.0))
    engage = float(data.get("engage_score", 0.0))
    peel = float(data.get("peel_score", 0.0))
    damage = data.get("damage_profile") or {}
    magic_ratio = float(damage.get("magic_ratio", 0.5))
    balance = float(damage.get("damage_balance", 1.0))

    if power <= -0.25:
        tempo = _pick(
            [
                "Au final, mon équipe est plutôt taillée pour imposer un rythme agressif en début de partie",
                "Globalement, on est une compo qui veut dicter le tempo dès le early",
            ]
        )
    elif power >= 0.25:
        tempo = _pick(
            [
                "On a une équipe plus patiente, on scale bien vers le late game",
                "Au final, on est plus forts en s'installant et en grandissant vers le late",
            ]
        )
    else:
        tempo = _pick(
            [
                "Au final, mon équipe reste flexible sur le timing des fights",
                "Globalement, on n'est ni full early ni full late — on s'adapte",
            ]
        )

    extras: list[str] = []
    if engage >= 0.55:
        extras.append(
            _pick(
                [
                    "avec assez de contrôle pour enchaîner nos combos",
                    "et on a de quoi forcer les engagements quand on le décide",
                ]
            )
        )
    if peel >= 0.55:
        extras.append(
            _pick(
                [
                    "et on a de quoi protéger nos carries",
                    "avec une vraie capacité à protéger nos menaces",
                ]
            )
        )
    if balance < 0.55:
        if magic_ratio >= 0.6:
            extras.append("même si on penche clairement vers la magie")
        elif magic_ratio <= 0.4:
            extras.append("même si on penche clairement vers les dégâts physiques")

    if not extras:
        extras.append("et la synergie d'ensemble me convient")

    summary = f"{tempo}, {extras[0]}."
    if len(extras) > 1:
        summary = f"{tempo}, {extras[0]}, {extras[1]}."

    for banned in TECHNICAL_BLACKLIST:
        if banned in summary:
            summary = summary.replace(banned, "")
    return " ".join(summary.split())


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
