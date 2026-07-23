#!/usr/bin/env python3
"""Chatbot rule-based (sans LLM) pour DraftLoL — réutilise predict_draft et suggest_draft."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Literal

from predict_draft import (
    WEIGHT_FORCE,
    WEIGHT_SIDE,
    WEIGHT_SYNERGY,
    predict_draft,
    warmup_predict_caches,
)
from suggest_draft import (
    ROLE_LABELS_FR,
    build_matchup_teams,
    decompose_winrate_delta,
    get_champion_role_catalog,
    normalize_role,
    replace_role_pick,
    slots_to_team,
    team_side_win_probability,
    _champion_winrate_for,
)
from justification_builder import generate_pick_justification
from champion_profile_stats import format_descriptive_stats_clause
from predict_draft import get_meraki_context, resolve_soloq_champion_name

IntentName = Literal[
    "define_term",
    "explain_score",
    "simulate_change",
    "explain_suggestion",
    "explain_matchup",
    "unknown",
]

MERAKI_ATTRIBUTE_LABELS = {
    "damage": "dégâts",
    "toughness": "robustesse",
    "control": "contrôle",
    "mobility": "mobilité",
    "utility": "utilité",
}

ROLE_SYNONYMS: dict[str, str] = {
    "top": "TOP",
    "toplane": "TOP",
    "jungle": "JUNGLE",
    "jgl": "JUNGLE",
    "mid": "MIDDLE",
    "middle": "MIDDLE",
    "milieu": "MIDDLE",
    "adc": "BOTTOM",
    "bot": "BOTTOM",
    "bottom": "BOTTOM",
    "botlane": "BOTTOM",
    "support": "UTILITY",
    "sup": "UTILITY",
    "utility": "UTILITY",
}

ROLES_ORDER = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]

# Définitions en langage simple (glossaire affiché par le chatbot)
TERM_DEFINITIONS: dict[str, str] = {
    "affinité compo": (
        "Note sur la cohérence de tes 5 picks (poids : 40 % du score final). "
        "Un programme entraîné sur des matchs pro estime si la compo « tient la route » "
        "(équilibre dégâts / tank / contrôle / mobilité). "
        "50 % = neutre, au-dessus = plutôt harmonieuse, en dessous = plutôt bancale. "
        "Ce n'est pas la force soloQ de chaque champion pris un par un."
    ),
    "score ml": (
        "Même chose que « affinité compo ». "
        "ML signifie « machine learning » : un modèle a appris sur des drafts pro "
        "quels profils de compositions gagnent le plus souvent. "
        "Il ne prédit pas le résultat d'un match précis, il note la forme globale de la draft."
    ),
    "meraki": (
        "Meraki est une base de données publique sur les champions LoL. "
        "Pour chaque perso, elle indique son style (fighter, mage, tank…) "
        "et des notes (dégâts, robustesse, contrôle, mobilité, utilité). "
        "On s'en sert pour décrire la compo, pas pour le winrate soloQ."
    ),
    "force soloq": (
        "Winrate moyen en soloQ EUW de tes 5 picks sur le patch choisi (poids : 50 %). "
        "Exemple : 51 % = tes champions performent un peu mieux que la moyenne en ranked. "
        "En mode pro, c'est remplacé par la « force pro » (stats compétition)."
    ),
    "force pro": (
        "Winrate moyen en compétition pro (Oracle's Elixir) pour chaque pick/rôle "
        "(poids : 50 % en mode pro). Minimum 10 games en pro pour compter. "
        "Pas de fallback soloQ en mode pro."
    ),
    "score pondéré": (
        "Note finale avant le % affiché. On additionne : "
        "50 % force des picks (soloQ ou pro) + 40 % affinité compo + 10 % bonus/malus de side blue. "
        "Cette note est convertie en probabilité de victoire (voir « sigmoïde »)."
    ),
    "sigmoïde": (
        "Formule qui transforme le score pondéré en pourcentage (ex. 52 %). "
        "Deux notes proches → des % proches. Un gros écart de note → un % plus marqué."
    ),
    "matchup 2v2": (
        "Comparaison des duos adverses : jungle+support d'un côté vs l'autre, "
        "ou adc+support d'un côté vs l'autre. "
        "On regarde qui a le duo le plus performant en pro (ou une estimation soloQ). "
        "Les « synergies internes » mesurent, elles, si deux alliés vont bien ensemble."
    ),
    "synergie interne": (
        "À quel point deux alliés se complètent (jungle+support ou adc+support). "
        "Basé sur les stats pro quand on en a assez, sinon une estimation soloQ + Meraki."
    ),
    "mode pro": (
        "Analyse uniquement avec des stats compétition (Oracle's Elixir). "
        "Pas de winrate soloQ. Si une donnée pro manque, c'est signalé."
    ),
    "mode mixte": (
        "Analyse soloQ EUW + affinité compo + duos/matchups pro quand disponibles, "
        "sinon estimations soloQ + Meraki."
    ),
    "données insuffisantes": (
        "Pas assez de games pro pour ce champion, duo ou matchup. "
        "En mode pro, on n'invente pas de chiffre : le score reste vide ou partiel."
    ),
    "side blue": (
        "Petit bonus historique pour l'équipe blue (~+3 pts vs neutre), "
        "car les stats pro montrent que blue gagne un peu plus souvent. "
        "Compte pour 10 % du score pondéré."
    ),
    "side red": (
        "Petit malus symétrique pour l'équipe red dans le score pondéré "
        "(l'inverse du bonus blue side)."
    ),
    "bans manqués": (
        "Analyse « et si on avait banni X ? » : on simule un ban manqué et on recalcule le %. "
        "Seuls les bans avec un gain ≥ 0,35 pt sont affichés."
    ),
    "picks manqués": (
        "Pour l'équipe perdante : « et si on avait pick Y à la place ? » "
        "Jusqu'à 3 alternatives par rôle, avec le gain estimé en points de winrate."
    ),
}

TERM_ALIASES: dict[str, str] = {
    "affinite compo": "affinité compo",
    "affinité composition": "affinité compo",
    "affinite": "affinité compo",
    "composition": "affinité compo",
    "force soloq": "force soloq",
    "soloq": "force soloq",
    "solo q": "force soloq",
    "force pro": "force pro",
    "winrate pro": "force pro",
    "score pondere": "score pondéré",
    "score pondéré": "score pondéré",
    "score final": "score pondéré",
    "matchup 2v2": "matchup 2v2",
    "matchup 2v2 bot": "matchup 2v2",
    "matchup jungle support": "matchup 2v2",
    "duo 2v2": "matchup 2v2",
    "synergie interne": "synergie interne",
    "synergie duo": "synergie interne",
    "duo bot": "synergie interne",
    "duo jungle support": "synergie interne",
    "mode pro": "mode pro",
    "pro": "mode pro",
    "mode mixte": "mode mixte",
    "mixte": "mode mixte",
    "mixed": "mode mixte",
    "insufficient_data": "données insuffisantes",
    "donnees insuffisantes": "données insuffisantes",
    "données insuffisantes": "données insuffisantes",
    "données pro insuffisantes": "données insuffisantes",
    "side blue": "side blue",
    "blue side": "side blue",
    "cote blue": "side blue",
    "side red": "side red",
    "red side": "side red",
    "cote red": "side red",
    "bans manqués": "bans manqués",
    "bans manques": "bans manqués",
    "ban manqué": "bans manqués",
    "picks manqués": "picks manqués",
    "picks manques": "picks manqués",
    "pick manqué": "picks manqués",
    "ml": "score ml",
    "machine learning": "score ml",
    "score ml": "score ml",
    "meraki": "meraki",
    "sigmoide": "sigmoïde",
    "sigmoid": "sigmoïde",
}

KNOWN_TERMS = sorted(TERM_DEFINITIONS.keys())

EXAMPLE_QUESTIONS = [
    "Pourquoi mon winrate est de 48 % ?",
    "C'est quoi l'affinité compo ?",
    "Si je mets Yasuo en mid, ça fait quoi ?",
    "Pourquoi Gnar gagne contre Gwen en top ?",
]

MATCHUP_MARKERS = (
    r"\bcontre\b",
    r"\bvs\b",
    r"\bface a\b",
    r"\bbat\b",
    r"\bbattre\b",
    r"\bgagn",
    r"\bdomine\b",
    r"\bmatchup\b",
    r"\bcounter\b",
    r"\blui\b",
    r"\belle\b",
    r"ce perso",
    r"ce champion",
    r"mon pick",
    r"mon perso",
    r"l adversaire",
    r"le sien",
)


def _normalize_text(text: str) -> str:
    lowered = text.lower().strip()
    normalized = unicodedata.normalize("NFD", lowered)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def extract_entities(
    question: str,
    available_champions: list[str],
    draft_champions: list[str] | None = None,
) -> dict[str, Any]:
    """Extrait champion(s), rôle et terme technique depuis la question."""
    normalized = _normalize_text(question)
    entities: dict[str, Any] = {
        "champion": None,
        "champions": [],
        "role": None,
        "term": None,
        "raw_question_normalized": normalized,
    }

    champion_pool = sorted(
        set(available_champions) | set(draft_champions or []),
        key=lambda name: len(name),
        reverse=True,
    )
    found_champions: list[str] = []
    remaining = normalized
    for champion in champion_pool:
        champion_norm = _normalize_text(champion)
        if re.search(rf"\b{re.escape(champion_norm)}\b", remaining):
            found_champions.append(champion)
            remaining = re.sub(rf"\b{re.escape(champion_norm)}\b", " ", remaining)
    entities["champions"] = found_champions
    entities["champion"] = found_champions[0] if found_champions else None

    for synonym, role in ROLE_SYNONYMS.items():
        if re.search(rf"\b{re.escape(synonym)}\b", normalized):
            entities["role"] = role
            break

    if entities["role"] is None:
        for role_code in ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"):
            if re.search(rf"\b{role_code.lower()}\b", normalized):
                entities["role"] = role_code
                break

    best_term: str | None = None
    best_len = 0
    for alias, canonical in TERM_ALIASES.items():
        alias_norm = _normalize_text(alias)
        if alias_norm in normalized and len(alias_norm) > best_len:
            best_term = canonical
            best_len = len(alias_norm)
    for term in TERM_DEFINITIONS:
        term_norm = _normalize_text(term)
        if term_norm in normalized and len(term_norm) > best_len:
            best_term = term
            best_len = len(term_norm)
    entities["term"] = best_term

    return entities


def detect_intent(question: str) -> dict[str, Any]:
    """Identifie l'intention à partir de mots-clés simples."""
    normalized = _normalize_text(question)

    define_markers = (
        r"c'est quoi",
        r"cest quoi",
        r"ca veut dire",
        r"ça veut dire",
        r"qu'est-ce que",
        r"quest ce que",
        r"explique",
        r"definition de",
        r"définition de",
    )
    if any(re.search(marker, normalized) for marker in define_markers):
        return {"intent": "define_term", "confidence": "keyword"}

    if "pourquoi" in normalized and re.search(
        r"winrate|score|probabilit|favori|favorite|favorise",
        normalized,
    ):
        return {"intent": "explain_score", "confidence": "keyword"}

    if re.search(r"si (?:je|on)\b", normalized) and re.search(
        r"\b(mets|met|pick|remplace|prends|prend|choisis|swap)\b",
        normalized,
    ):
        return {"intent": "simulate_change", "confidence": "keyword"}

    has_matchup_marker = any(re.search(marker, normalized) for marker in MATCHUP_MARKERS)
    if has_matchup_marker and (
        "pourquoi" in normalized
        or "comment" in normalized
        or re.search(r"\bvs\b", normalized)
    ):
        return {"intent": "explain_matchup", "confidence": "keyword"}

    if "pourquoi" in normalized:
        return {"intent": "explain_suggestion", "confidence": "keyword"}

    return {"intent": "unknown", "confidence": "none"}


def _resolve_focus_team_side(question: str, context: dict[str, Any]) -> str:
    if context.get("focus_team_side") in ("blue", "red"):
        return str(context["focus_team_side"])
    normalized = _normalize_text(question)
    if re.search(r"\b(red|cote red|equipe red)\b", normalized):
        return "red"
    if re.search(r"\b(blue|cote blue|equipe blue)\b", normalized):
        return "blue"
    if re.search(r"\b(adversaire|ennemi|eux|ils)\b", normalized):
        prediction = context.get("prediction") or {}
        blue_prob = float(prediction.get("blue_win_probability", 0.5))
        red_prob = float(prediction.get("red_win_probability", 0.5))
        return "red" if blue_prob >= red_prob else "blue"
    if re.search(r"\b(mon|notre|ma|mes|je|moi)\b", normalized):
        prediction = context.get("prediction") or {}
        blue_prob = float(prediction.get("blue_win_probability", 0.5))
        red_prob = float(prediction.get("red_win_probability", 0.5))
        return "blue" if blue_prob <= red_prob else "red"
    prediction = context.get("prediction") or {}
    blue_prob = float(prediction.get("blue_win_probability", 0.5))
    return "blue" if blue_prob >= red_prob else "red"


def _team_slots(context: dict[str, Any], team_side: str) -> list[dict[str, str]]:
    key = "blue_team" if team_side == "blue" else "red_team"
    team = context.get(key) or []
    return slots_to_team([{"champion": s["champion"], "role": s["role"]} for s in team])


def _opponent_slots(context: dict[str, Any], team_side: str) -> list[dict[str, str]]:
    return _team_slots(context, "red" if team_side == "blue" else "blue")


def _infer_role_for_champion(
    champion: str,
    role: str | None,
    team_side: str,
    context: dict[str, Any],
) -> str | None:
    if role:
        return normalize_role(role)

    catalog = get_champion_role_catalog()
    playable = catalog.get(champion, [])
    if not playable:
        return None

    team = _team_slots(context, team_side)
    for slot in team:
        if normalize_role(slot["role"]) in playable:
            return normalize_role(slot["role"])

    return normalize_role(playable[0])


def _find_suggestion_reason(champion: str, context: dict[str, Any]) -> str | None:
    champion_fold = champion.casefold()
    for key in ("retrospective_picks", "retrospective_bans", "suggestions"):
        for entry in context.get(key) or []:
            if str(entry.get("champion", "")).casefold() == champion_fold:
                reason = entry.get("reason")
                if reason:
                    return str(reason)
    return None


def _answer_define_term(entities: dict[str, Any]) -> str:
    term = entities.get("term")
    if term and term in TERM_DEFINITIONS:
        return f"{term.capitalize()} : {TERM_DEFINITIONS[term]}"
    known = ", ".join(KNOWN_TERMS)
    return (
        "Je ne connais pas ce terme. Essaie de me demander directement sur : "
        f"{known}."
    )


def _format_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def _answer_explain_score(question: str, context: dict[str, Any]) -> str:
    prediction = context.get("prediction")
    if not prediction:
        return "Je n'ai pas de prédiction dans le contexte actuel. Termine une draft pour analyser le score."

    mode = context.get("mode", prediction.get("mode", "mixed"))
    is_pro = mode == "pro"
    force_label = "Force pro" if is_pro else "Force soloQ"

    team_side = _resolve_focus_team_side(question, context)
    opponent_side = "red" if team_side == "blue" else "blue"
    our = prediction[team_side]
    opp = prediction[opponent_side]
    our_prob = float(prediction[f"{team_side}_win_probability"])
    opp_prob = float(prediction[f"{opponent_side}_win_probability"])

    our_force = our.get("score_force")
    opp_force = opp.get("score_force")
    force_diff = 0.0
    if our_force is not None and opp_force is not None:
        force_diff = (float(our_force) - float(opp_force)) * 100

    synergy_diff = (float(our["score_synergie"]) - float(opp["score_synergie"])) * 100

    parts = [
        f"Winrate estimé {team_side.upper()} : {_format_pct(our_prob)} "
        f"(adverse : {_format_pct(opp_prob)}).",
        f"- {force_label} : {_format_pct(our_force)} vs {_format_pct(opp_force)} "
        f"({force_diff:+.1f} pt, poids {WEIGHT_FORCE * 100:.0f} %).",
        f"- Affinité compo : {_format_pct(our['score_synergie'])} vs "
        f"{_format_pct(opp['score_synergie'])} ({synergy_diff:+.1f} pt, "
        f"poids {WEIGHT_SYNERGY * 100:.0f} %).",
        f"- Score pondéré : {float(our['score_final']) * 100:.1f} pts vs "
        f"{float(opp['score_final']) * 100:.1f} pts "
        f"(inclut {WEIGHT_SIDE * 100:.0f} % bonus/malus side).",
    ]

    reasons: list[str] = []
    if abs(force_diff) >= 1.5:
        force_phrase = (
            "des champions plus performants en pro"
            if is_pro
            else "des champions plus performants sur le patch soloQ"
        )
        if force_diff >= 0:
            reasons.append(f"votre {force_label.lower()} est plus haute")
        else:
            reasons.append(f"l'adversaire a {force_phrase}")
    if abs(synergy_diff) >= 1.5:
        if synergy_diff >= 0:
            reasons.append("votre affinité compo est meilleure")
        else:
            reasons.append("l'adversaire a une meilleure affinité compo")

    duo_diff = prediction.get("duo_differential") or {}
    for label, key in (
        ("un avantage jungle-support 2v2", "jungle_support_advantage"),
        ("un avantage bot lane 2v2", "bot_lane_advantage"),
    ):
        adv = duo_diff.get(key) or {}
        if adv.get("stronger_side") == team_side and float(adv.get("difference", 0)) >= 0.02:
            reasons.append(label)

    if reasons:
        parts.append(
            "Principaux facteurs : " + " et ".join(reasons[:2]) + "."
        )
    elif our_prob < opp_prob:
        parts.append("L'écart reste fin : aucun axe ne domine nettement.")
    else:
        parts.append("L'avantage repose sur la combinaison force + affinité + side.")

    return " ".join(parts)


def _answer_simulate_change(
    entities: dict[str, Any],
    context: dict[str, Any],
    available_champions: list[str],
) -> str:
    champion = entities.get("champion")
    if not champion:
        return (
            "Pour simuler un changement, précise un champion disponible, "
            "par ex. « Si je mets Yasuo en mid, ça fait quoi ? »"
        )

    if champion.casefold() not in {name.casefold() for name in available_champions}:
        return f"{champion} n'est pas disponible dans le pool actuel (déjà pické ou banni)."

    patch = str(context.get("patch", "")).strip()
    mode = context.get("mode", "mixed")
    team_side = _resolve_focus_team_side("", context)
    role = _infer_role_for_champion(champion, entities.get("role"), team_side, context)
    if not role:
        return (
            f"Je n'arrive pas à déterminer le rôle pour {champion}. "
            "Précise-le : top, jungle, mid, adc ou support."
        )

    team = _team_slots(context, team_side)
    opponent = _opponent_slots(context, team_side)
    current = next(
        (slot["champion"] for slot in team if normalize_role(slot["role"]) == role),
        None,
    )
    if current and current.casefold() == champion.casefold():
        return f"{champion} est déjà votre pick en {role.lower()}."

    warmup_predict_caches(patch)
    blue_team, red_team = build_matchup_teams(team, opponent, team_side)
    baseline = predict_draft(blue_team, red_team, patch=patch, mode=mode)
    modified_team = replace_role_pick(team, role, champion)
    mod_blue, mod_red = build_matchup_teams(modified_team, opponent, team_side)
    updated = predict_draft(mod_blue, mod_red, patch=patch, mode=mode)

    p_before = team_side_win_probability(baseline, team_side)
    p_after = team_side_win_probability(updated, team_side)
    decomposition = decompose_winrate_delta(
        baseline, updated, team_side, role, "team", mode
    )
    reason = generate_pick_justification(
        champion,
        role,
        team_context=modified_team,
        opponent_context=opponent,
        source_data={
            "patch": patch,
            "mode": mode,
            "pick_side": "team",
            "changed_side": "team",
            "decomposition": decomposition,
        },
    )

    return (
        f"Avant : {p_before * 100:.1f} % → Après : {p_after * 100:.1f} % "
        f"({decomposition['delta_total']:+.1f} pt). {reason}"
    )


def _draft_champion_index(context: dict[str, Any]) -> dict[str, tuple[str, str]]:
    index: dict[str, tuple[str, str]] = {}
    for side in ("blue", "red"):
        for slot in context.get(f"{side}_team") or []:
            champion = str(slot.get("champion", "")).strip()
            role = normalize_role(str(slot.get("role", "")))
            if champion:
                index[champion.casefold()] = (side, role)
    return index


def _champion_at_role(context: dict[str, Any], team_side: str, role: str) -> str | None:
    role = normalize_role(role)
    for slot in context.get(f"{team_side}_team") or []:
        if normalize_role(str(slot.get("role", ""))) == role:
            champion = str(slot.get("champion", "")).strip()
            return champion or None
    return None


def _winrate_from_prediction(
    prediction: dict[str, Any],
    team_side: str,
    role: str,
) -> tuple[float | None, bool]:
    team = prediction.get(team_side) or {}
    for entry in team.get("champions") or []:
        if normalize_role(str(entry.get("role", ""))) == normalize_role(role):
            if entry.get("insufficient_data"):
                return None, True
            winrate = entry.get("winrate")
            if winrate is None:
                return None, False
            return float(winrate), False
    return None, False


def _infer_role_for_pair(
    champion_a: str,
    champion_b: str,
    role_hint: str | None,
    context: dict[str, Any],
) -> str | None:
    if role_hint:
        return normalize_role(role_hint)

    draft_index = _draft_champion_index(context)
    info_a = draft_index.get(champion_a.casefold())
    info_b = draft_index.get(champion_b.casefold())
    if info_a and info_b and info_a[1] == info_b[1]:
        return info_a[1]
    if info_a:
        return info_a[1]
    if info_b:
        return info_b[1]

    catalog = get_champion_role_catalog()
    roles_a = set(catalog.get(champion_a, []))
    roles_b = set(catalog.get(champion_b, []))
    shared = sorted(roles_a & roles_b, key=ROLES_ORDER.index)  # type: ignore[name-defined]
    if shared:
        return normalize_role(shared[0])
    return None


def _resolve_matchup_pair(
    question: str,
    entities: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, str, str] | None:
    """Retourne (champion_subject, champion_opponent, role) ou None."""
    normalized = entities["raw_question_normalized"]
    named = list(entities.get("champions") or [])
    role_hint = entities.get("role")
    draft_index = _draft_champion_index(context)
    focus_side = _resolve_focus_team_side(question, context)
    opponent_side = "red" if focus_side == "blue" else "blue"

    if len(named) >= 2:
        subject, opponent = named[0], named[1]
        role = _infer_role_for_pair(subject, opponent, role_hint, context)
        if role:
            return subject, opponent, role
        return None

    if len(named) == 1:
        subject = named[0]
        info = draft_index.get(subject.casefold())
        if info:
            _, role = info
            opponent = _champion_at_role(context, "red" if info[0] == "blue" else "blue", role)
            if opponent:
                return subject, opponent, role
        if role_hint:
            opponent_side_for_subject = opponent_side
            if draft_index.get(subject.casefold()):
                subject_side = draft_index[subject.casefold()][0]
                opponent_side_for_subject = "red" if subject_side == "blue" else "blue"
            opponent = _champion_at_role(context, opponent_side_for_subject, role_hint)
            if opponent:
                return subject, opponent, normalize_role(role_hint)
        return None

    uses_subject_pronoun = bool(
        re.search(r"ce perso|ce champion|mon pick|mon perso|notre pick", normalized)
    )
    uses_opponent_pronoun = bool(
        re.search(r"\blui\b|\belle\b|l adversaire|le sien", normalized)
    )
    if uses_subject_pronoun or uses_opponent_pronoun:
        if not role_hint:
            return None
        role = normalize_role(role_hint)
        ours = _champion_at_role(context, focus_side, role)
        theirs = _champion_at_role(context, opponent_side, role)
        if not ours or not theirs:
            return None
        if uses_opponent_pronoun and not uses_subject_pronoun:
            return theirs, ours, role
        return ours, theirs, role

    return None


def _meraki_profile_advantages(winner: str, loser: str) -> list[str]:
    try:
        champion_features, _, lookup_by_norm = get_meraki_context()
    except (FileNotFoundError, ValueError):
        return []

    key_w = resolve_soloq_champion_name(winner, champion_features, lookup_by_norm)
    key_l = resolve_soloq_champion_name(loser, champion_features, lookup_by_norm)
    if not key_w or not key_l:
        return []

    ratings_w = champion_features[key_w].get("attributeRatings") or {}
    ratings_l = champion_features[key_l].get("attributeRatings") or {}
    advantages: list[tuple[float, str]] = []
    for attr, label in MERAKI_ATTRIBUTE_LABELS.items():
        val_w = ratings_w.get(attr)
        val_l = ratings_l.get(attr)
        if val_w is None or val_l is None:
            continue
        diff = float(val_w) - float(val_l)
        if diff >= 0.4:
            advantages.append((diff, f"plus de {label}"))
        elif diff <= -0.4:
            advantages.append((-diff, f"moins de {label}"))

    advantages.sort(key=lambda item: item[0], reverse=True)
    return [phrase for _, phrase in advantages[:2]]


def _answer_explain_matchup(
    question: str,
    entities: dict[str, Any],
    context: dict[str, Any],
) -> str:
    prediction = context.get("prediction")
    if not prediction:
        return "Termine une draft pour comparer deux champions de la partie."

    pair = _resolve_matchup_pair(question, entities, context)
    if pair is None:
        return (
            "Pour expliquer un matchup, cite les deux champions et le rôle, "
            "par ex. « Pourquoi Gnar gagne contre Gwen en top ? » ou "
            "« Pourquoi mon pick gagne contre lui en mid ? »."
        )

    subject, opponent, role = pair
    mode = context.get("mode", prediction.get("mode", "mixed"))
    is_pro = mode == "pro"
    force_label = "force pro" if is_pro else "winrate soloQ"
    role_fr = ROLE_LABELS_FR.get(role, role.lower())
    patch = str(context.get("patch", "")).strip()

    draft_index = _draft_champion_index(context)
    subject_info = draft_index.get(subject.casefold())
    opponent_info = draft_index.get(opponent.casefold())

    subject_wr: float | None = None
    opponent_wr: float | None = None
    subject_missing = False
    opponent_missing = False

    if subject_info:
        subject_wr, subject_missing = _winrate_from_prediction(
            prediction, subject_info[0], role
        )
    if opponent_info:
        opponent_wr, opponent_missing = _winrate_from_prediction(
            prediction, opponent_info[0], role
        )

    if subject_wr is None:
        subject_wr = _champion_winrate_for(subject, role, patch, mode)
    if opponent_wr is None:
        opponent_wr = _champion_winrate_for(opponent, role, patch, mode)

    if is_pro and (subject_missing or opponent_missing or subject_wr is None or opponent_wr is None):
        return (
            f"Données pro insuffisantes pour comparer {subject} et {opponent} en {role_fr}."
        )

    subject_wr = subject_wr if subject_wr is not None else 0.5
    opponent_wr = opponent_wr if opponent_wr is not None else 0.5
    delta_pts = (subject_wr - opponent_wr) * 100

    parts = [
        f"Matchup {role_fr} : {subject} vs {opponent}.",
        f"{force_label.capitalize()} patch : {_format_pct(subject_wr)} pour {subject}, "
        f"{_format_pct(opponent_wr)} pour {opponent} ({delta_pts:+.1f} pt).",
        "Ce n'est pas un historique 1v1 en lane, mais la force moyenne de chaque pick sur le rôle.",
    ]

    if delta_pts >= 1.5:
        parts.append(
            f"{subject} part donc avec un avantage {force_label} sur {opponent} au {role_fr}."
        )
        winner, loser = subject, opponent
    elif delta_pts <= -1.5:
        parts.append(
            f"En réalité {opponent} a plutôt l'avantage {force_label} sur {subject} au {role_fr}."
        )
        winner, loser = opponent, subject
    else:
        parts.append("Le matchup reste équilibré sur la force individuelle des picks.")
        winner, loser = subject, opponent

    meraki_adv = _meraki_profile_advantages(winner, loser)
    if meraki_adv:
        parts.append(
            f"Profil Meraki : {winner} apporte " + " et ".join(meraki_adv) + "."
        )

    descriptive = format_descriptive_stats_clause(
        winner,
        role,
        caller="chatbot_rules",
        role_fr=role_fr,
        context="counter",
    )
    if descriptive:
        parts.append(descriptive)

    return " ".join(parts)


def _answer_explain_suggestion(entities: dict[str, Any], context: dict[str, Any]) -> str:
    champion = entities.get("champion")
    if not champion:
        return (
            "Pour expliquer une suggestion, cite le champion concerné, "
            "par ex. « Pourquoi Zac ? »"
        )

    reason = _find_suggestion_reason(champion, context)
    if reason:
        return f"Suggestion pour {champion} : {reason}"

    return (
        f"Je ne trouve pas {champion} dans les suggestions affichées (bans ou picks manqués). "
        "Attends que l'analyse rétrospective soit chargée ou reformule avec un champion suggéré."
    )


def _answer_unknown() -> str:
    examples = " · ".join(f"« {q} »" for q in EXAMPLE_QUESTIONS[:3])
    return (
        "Je peux répondre sur les scores, les termes du modèle, les matchups 1v1 de lane, "
        "ou simuler un changement de pick. Reformule avec un nom de champion ou un terme précis. "
        f"Exemples : {examples}."
    )


def _draft_champions_from_context(context: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for side in ("blue_team", "red_team"):
        for slot in context.get(side) or []:
            champion = str(slot.get("champion", "")).strip()
            if champion:
                names.append(champion)
    return names


def answer_question(
    question: str,
    prediction_context: dict[str, Any],
    available_champions: list[str],
) -> dict[str, str]:
    """Point d'entrée principal du chatbot rule-based."""
    draft_champions = _draft_champions_from_context(prediction_context)
    entities = extract_entities(question, available_champions, draft_champions)
    intent_result = detect_intent(question)
    intent: IntentName = intent_result["intent"]

    if intent == "explain_suggestion" or (
        intent == "explain_score"
        and entities.get("champion")
        and _find_suggestion_reason(str(entities["champion"]), prediction_context)
    ):
        intent = "explain_suggestion"
        answer = _answer_explain_suggestion(entities, prediction_context)
    elif intent == "define_term":
        answer = _answer_define_term(entities)
    elif intent == "explain_score":
        answer = _answer_explain_score(question, prediction_context)
    elif intent == "explain_matchup":
        answer = _answer_explain_matchup(question, entities, prediction_context)
    elif intent == "simulate_change":
        if not entities.get("champion"):
            intent = "unknown"
            answer = _answer_unknown()
        else:
            answer = _answer_simulate_change(entities, prediction_context, available_champions)
    else:
        intent = "unknown"
        answer = _answer_unknown()

    return {"answer": answer, "intent_detected": intent}
