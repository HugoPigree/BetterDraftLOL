"""Justifications hiérarchisées pour picks/bans (meta → archétype → duo → stats)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from build_duo_dataset import DuoType, get_duo_score
from champion_profile_stats import DescriptiveContext, format_descriptive_stats_clause
from composition_archetype import compute_composition_archetype, score_archetype_coherence
from pro_force import DEFAULT_META_TIERLIST_CSV, pro_meta_score
from predict_draft import PredictionMode, get_meraki_context

DUO_ROLES = frozenset({"JUNGLE", "BOTTOM", "UTILITY"})
SIGNIFICANT_BAN_RATE = 0.15
ARCHETYPE_PENALTY_THRESHOLD = 0.55
ARCHETYPE_BONUS_THRESHOLD = 0.85

ROLE_LABELS_FR = {
    "TOP": "top",
    "JUNGLE": "jungle",
    "MIDDLE": "mid",
    "BOTTOM": "adc",
    "UTILITY": "support",
}

PickSide = Literal["team", "opponent"]
ChangedSide = Literal["team", "opponent"]


def normalize_role(role: str) -> str:
    role_upper = role.strip().upper()
    return {"SUPPORT": "UTILITY"}.get(role_upper, role_upper)


def _champion_for_role(team: list[dict[str, str]], role: str) -> str | None:
    role = normalize_role(role)
    for slot in team:
        if normalize_role(slot["role"]) == role:
            champion = slot["champion"].strip()
            return champion or None
    return None


def _team_champions_excluding_role(
    team: list[dict[str, str]],
    role: str,
) -> list[str]:
    role = normalize_role(role)
    return [
        slot["champion"].strip()
        for slot in team
        if slot["champion"].strip() and normalize_role(slot["role"]) != role
    ]


@dataclass(frozen=True)
class MetaTierlistRow:
    champion: str
    role: str
    games: int
    wilson_lower_bound: float
    pick_rate: float
    ban_rate: float
    presence_score: float
    trend_raw: str


@lru_cache(maxsize=1)
def _load_meta_tierlist_rows(
    tierlist_csv: str = str(DEFAULT_META_TIERLIST_CSV),
) -> dict[tuple[str, str], MetaTierlistRow]:
    path = Path(tierlist_csv)
    if not path.exists():
        return {}

    df = pd.read_csv(path)
    lookup: dict[tuple[str, str], MetaTierlistRow] = {}
    for _, row in df.iterrows():
        champion = str(row["champion"]).strip()
        role = normalize_role(str(row["role"]))
        entry = MetaTierlistRow(
            champion=champion,
            role=role,
            games=int(row["games"]),
            wilson_lower_bound=float(row["wilson_lower_bound"]),
            pick_rate=float(row["pick_rate"]),
            ban_rate=float(row["ban_rate"]),
            presence_score=float(row["presence_score"]),
            trend_raw=str(row.get("trend", "stable")),
        )
        lookup[(champion, role)] = entry
        lookup[(champion.casefold(), role)] = entry
    return lookup


def lookup_meta_tierlist_row(
    champion: str,
    role: str,
    tierlist_csv: Path = DEFAULT_META_TIERLIST_CSV,
) -> MetaTierlistRow | None:
    table = _load_meta_tierlist_rows(str(tierlist_csv))
    role = normalize_role(role)
    champion = champion.strip()
    direct = table.get((champion, role))
    if direct is not None:
        return direct
    return table.get((champion.casefold(), role))


def _parse_trend_label(trend_raw: str) -> str | None:
    if not trend_raw or trend_raw.lower() == "nan":
        return None
    match = re.match(r"^(hausse|stable|baisse)", trend_raw.strip(), re.IGNORECASE)
    if not match:
        return None
    label = match.group(1).lower()
    if label == "hausse":
        return "en hausse ce mois-ci"
    if label == "baisse":
        return "en baisse ce mois-ci"
    return "stable ce mois-ci"


def _format_percent(rate: float) -> str:
    return f"{rate * 100:.0f}%"


def _build_meta_sentence(
    champion: str,
    role: str,
    *,
    mode: PredictionMode,
) -> str:
    role_fr = ROLE_LABELS_FR.get(normalize_role(role), role.lower())
    row = lookup_meta_tierlist_row(champion, role)

    if row is not None:
        trend_clause = _parse_trend_label(row.trend_raw)
        trend_suffix = f", tendance {trend_clause}" if trend_clause else ""
        if row.ban_rate >= SIGNIFICANT_BAN_RATE:
            return (
                f"{champion} est souvent banni en pro ({_format_percent(row.ban_rate)} des games), "
                f"signe de la menace qu'il représente en {role_fr} "
                f"({row.games} games pickées{trend_suffix})."
            )
        if row.games >= 30:
            return (
                f"{champion} est un pick établi en {role_fr} pro "
                f"({row.games} games, Wilson LB {_format_percent(row.wilson_lower_bound)}"
                f"{trend_suffix})."
            )
        if row.games > 0:
            return (
                f"{champion} reste peu joué en {role_fr} pro ({row.games} games"
                f"{trend_suffix})."
            )

    if mode == "pro":
        try:
            champion_features, _, lookup_by_norm = get_meraki_context()
            scored = pro_meta_score(champion, role, champion_features, lookup_by_norm)
        except (FileNotFoundError, ValueError):
            scored = None
        if scored is not None:
            meta_score, games, winrate, _fitness, _name = scored
            return (
                f"{champion} affiche {winrate * 100:.1f}% de winrate pro "
                f"en {role_fr} ({games} games, score meta {meta_score:.2f})."
            )

    return f"{champion} est une option crédible en {role_fr} dans le pool actuel."


def _format_teammates_list(names: list[str]) -> str:
    cleaned = [name.strip() for name in names if name.strip()]
    if not cleaned:
        return "la compo"
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} et {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f" et {cleaned[-1]}"


def _describe_archetype_shift(
    before: dict[str, Any],
    after: dict[str, Any],
) -> list[str]:
    shifts: list[str] = []
    peel_delta = float(after["peel_score"]) - float(before["peel_score"])
    engage_delta = float(after["engage_score"]) - float(before["engage_score"])
    curve_delta = float(after["power_curve"]) - float(before["power_curve"])
    balance_delta = (
        float(after["damage_profile"]["damage_balance"])
        - float(before["damage_profile"]["damage_balance"])
    )

    if peel_delta >= 0.08:
        shifts.append("comble un manque de peel")
    if engage_delta >= 0.08:
        shifts.append("renforce l'engage")
    if curve_delta >= 0.10:
        shifts.append("renforce un profil scaling déjà engagé")
    elif curve_delta <= -0.10:
        shifts.append("accélère le tempo early")
    if balance_delta >= 0.08:
        shifts.append("équilibre le profil de dégâts AD/AP")
    return shifts


def _build_composition_sentence(
    champion: str,
    role: str,
    pick_team: list[dict[str, str]],
    *,
    archetype_score: float | None,
    decomposition: dict[str, float] | None,
    changed_side: ChangedSide | None,
) -> str | None:
    so_far = _team_champions_excluding_role(pick_team, role)
    if not so_far:
        return None

    role = normalize_role(role)
    score = (
        archetype_score
        if archetype_score is not None
        else score_archetype_coherence(so_far, champion)
    )
    before = compute_composition_archetype(so_far)
    after = compute_composition_archetype(so_far + [champion])
    shifts = _describe_archetype_shift(before, after)

    subject = "Ce pick" if len(so_far) >= 2 else f"{champion}"
    parts: list[str] = []

    if shifts:
        parts.append(f"{subject} {' et '.join(shifts[:2])} dans la composition")
    elif score >= ARCHETYPE_BONUS_THRESHOLD:
        parts.append(f"{subject} renforce la cohérence d'archétype de l'équipe")
    elif score <= ARCHETYPE_PENALTY_THRESHOLD:
        parts.append(
            f"{subject} casse la cohérence du plan "
            f"(profil peu aligné, score interne {score:.2f})"
        )
    else:
        if len(so_far) >= 2:
            ally = _format_teammates_list(so_far)
            parts.append(
                f"{subject} complète {ally} sans dénaturer le plan de composition"
            )
        else:
            parts.append(f"{subject} pose une base cohérente pour la suite de la draft")

    if (
        decomposition is not None
        and changed_side == "team"
        and decomposition.get("delta_force", 0.0) > 0.05
        and decomposition.get("delta_synergie", 0.0) < -0.05
    ):
        parts.append(
            "mais gagne surtout sa lane au détriment de la synergie globale "
            f"({decomposition['delta_synergie']:+.1f} pt)"
        )
    elif score <= ARCHETYPE_PENALTY_THRESHOLD and not shifts:
        parts.append("un profil peu aligné avec le plan de jeu actuel")

    return f"{', '.join(parts)}."


def _duo_type_for_role(role: str) -> DuoType | None:
    role = normalize_role(role)
    if role == "BOTTOM":
        return "bot_lane"
    if role == "JUNGLE":
        return "jungle_support"
    return None


def _build_duo_sentence(
    champion: str,
    role: str,
    pick_team: list[dict[str, str]],
    *,
    mode: PredictionMode,
) -> str | None:
    role = normalize_role(role)
    if role not in DUO_ROLES:
        return None

    role_fr = ROLE_LABELS_FR.get(role, role.lower())
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

    best: tuple[str, str, float, int] | None = None
    for partner, duo_type, lane_label in partners:
        duo = get_duo_score(champion, partner, duo_type, mode=mode)
        if duo.score is None or duo.insufficient_data:
            continue
        if duo.games < 5:
            continue
        if best is None or duo.score > best[2]:
            best = (partner, lane_label, float(duo.score), int(duo.games))

    if best is None:
        return None

    partner, lane_label, winrate, games = best
    quality = "solide" if winrate >= 0.52 else "correct"
    return (
        f"En {role_fr}, le duo {lane_label} avec {partner} est {quality} en pro "
        f"({winrate * 100:.1f} % WR sur {games} games)."
    )


def _descriptive_context(
    decomposition: dict[str, float] | None,
    changed_side: ChangedSide | None,
) -> DescriptiveContext:
    if decomposition is None or changed_side is None:
        return "neutral"
    if changed_side == "team" and decomposition.get("delta_force", 0.0) > 0.05:
        return "counter"
    if changed_side == "opponent" and decomposition.get("delta_force", 0.0) < -0.05:
        return "threat"
    return "neutral"


def _build_stats_sentence(
    champion: str,
    role: str,
    *,
    decomposition: dict[str, float] | None,
    changed_side: ChangedSide | None,
) -> str | None:
    role_fr = ROLE_LABELS_FR.get(normalize_role(role), role.lower())
    clause = format_descriptive_stats_clause(
        champion,
        role,
        caller="justification_builder",
        role_fr=role_fr,
        context=_descriptive_context(decomposition, changed_side),
    )
    if not clause:
        return None
    marker = " affiche historiquement "
    if marker in clause:
        tail = clause.split(marker, 1)[1]
        return f"C'est cohérent avec un profil de lane où il affiche historiquement {tail}"
    return f"C'est cohérent avec {clause}"


def _resolve_pick_team(
    team_context: list[dict[str, str]] | None,
    opponent_context: list[dict[str, str]] | None,
    pick_side: PickSide,
) -> list[dict[str, str]]:
    if pick_side == "opponent":
        return list(opponent_context or [])
    return list(team_context or [])


def generate_pick_justification(
    champion: str,
    role: str,
    team_context: list[dict[str, str]] | None,
    opponent_context: list[dict[str, str]] | None,
    source_data: dict[str, Any] | None = None,
) -> str:
    """Génère 2–3 phrases : meta → archétype → duo → stats (sections omises si absentes)."""
    source = source_data or {}
    mode: PredictionMode = source.get("mode", "mixed")
    pick_side: PickSide = source.get("pick_side", "team")
    changed_side: ChangedSide | None = source.get("changed_side")
    decomposition: dict[str, float] | None = source.get("decomposition")
    archetype_score: float | None = source.get("archetype_score")
    prefix: str | None = source.get("prefix")

    sentences: list[str] = []

    if prefix:
        sentences.append(prefix.rstrip(".") + ".")

    sentences.append(_build_meta_sentence(champion, role, mode=mode))

    pick_team = _resolve_pick_team(team_context, opponent_context, pick_side)
    composition = _build_composition_sentence(
        champion,
        role,
        pick_team,
        archetype_score=archetype_score,
        decomposition=decomposition,
        changed_side=changed_side,
    )
    if composition:
        sentences.append(composition)

    duo = _build_duo_sentence(champion, role, pick_team, mode=mode)
    stats = _build_stats_sentence(
        champion,
        role,
        decomposition=decomposition,
        changed_side=changed_side,
    )

    if duo and stats:
        stats_body = stats[0].lower() + stats[1:] if stats else stats
        sentences.append(f"{duo.rstrip('.')}; {stats_body}")
    elif duo:
        sentences.append(duo)
    elif stats:
        sentences.append(stats)

    if prefix:
        sentences = [sentences[0]] + sentences[1 : 1 + 3]
    else:
        sentences = sentences[:3]

    return " ".join(sentences)


def section_positions(text: str) -> dict[str, int]:
    """Repère les sections pour les tests d'ordre narratif."""
    positions: dict[str, int] = {}
    meta_markers = (
        "pick établi",
        "souvent banni",
        "meta_score pro",
        "peu joué en",
        "option crédible",
    )
    for marker in meta_markers:
        idx = text.find(marker)
        if idx >= 0:
            positions["meta"] = idx
            break

    comp_markers = (
        "composition",
        "archétype",
        "peel",
        "scaling",
        "synergie globale",
        "profil de dégâts",
        "tempo early",
    )
    for marker in comp_markers:
        idx = text.find(marker)
        if idx >= 0:
            positions["composition"] = idx
            break

    duo_idx = text.find("duo ")
    if duo_idx >= 0:
        positions["duo"] = duo_idx

    stat_markers = ("historiquement", "statistique historique moyenne", "C'est cohérent")
    for marker in stat_markers:
        idx = text.find(marker)
        if idx >= 0:
            positions["stats"] = idx
            break

    return positions


def assert_narrative_order(text: str) -> None:
    """Vérifie meta < composition < duo < stats quand présents."""
    pos = section_positions(text)
    order = ["meta", "composition", "duo", "stats"]
    last = -1
    for key in order:
        if key not in pos:
            continue
        assert pos[key] > last, f"Ordre narratif invalide pour {key!r} dans: {text!r}"
        last = pos[key]


def assert_justification_role_consistency(text: str, assigned_role: str) -> None:
    """Vérifie que meta et duo décrivent le même rôle assigné au pick."""
    role = normalize_role(assigned_role)
    role_fr = ROLE_LABELS_FR.get(role, role.lower())
    lower = text.lower()

    assert role_fr in lower.split(".")[0] or f"en {role_fr}" in lower, (
        f"Le rôle assigné {role_fr!r} devrait apparaître dans la phrase meta: {text!r}"
    )

    if "duo " in lower:
        duo_match = re.search(r"\ben (top|jungle|mid|adc|support), le duo\b", lower)
        assert duo_match is not None, f"Phrase duo introuvable dans: {text!r}"
        assert duo_match.group(1) == role_fr, (
            f"Le duo devrait décrire le rôle {role_fr!r}, trouvé {duo_match.group(1)!r}: {text!r}"
        )

    for other_role, other_fr in ROLE_LABELS_FR.items():
        if other_role == role:
            continue
        assert f"en {other_fr} pro" not in lower, (
            f"Rôle contradictoire {other_fr!r} dans la meta: {text!r}"
        )
        assert f"en {other_fr}," not in lower, (
            f"Rôle contradictoire {other_fr!r} dans le duo: {text!r}"
        )
