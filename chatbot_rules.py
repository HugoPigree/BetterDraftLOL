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
    build_decomposed_reason,
    build_matchup_teams,
    decompose_winrate_delta,
    get_champion_role_catalog,
    normalize_role,
    replace_role_pick,
    slots_to_team,
    team_side_win_probability,
)

IntentName = Literal[
    "define_term",
    "explain_score",
    "simulate_change",
    "explain_suggestion",
    "unknown",
]

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

# Définitions alignées sur frontend/src/copy/methodology.ts
TERM_DEFINITIONS: dict[str, str] = {
    "affinité compo": (
        "Score ML (40 % du score pondéré) basé sur les archétypes et attributs Meraki "
        "(dégâts, contrôle, mobilité…). Il mesure la cohérence globale de la composition, "
        "pas la force brute soloQ/pro d'un seul champion."
    ),
    "force soloq": (
        "Winrate moyen soloQ EUW des 5 picks sur le patch sélectionné (50 % du score pondéré "
        "en mode mixte). En mode pro, c'est la « force pro » Oracle's Elixir à la place."
    ),
    "force pro": (
        "Winrate moyen pro Oracle's Elixir par champion/rôle (50 % du score pondéré en mode pro), "
        "sans fallback soloQ. Minimum 10 games par pick pour être pris en compte."
    ),
    "score pondéré": (
        "Combinaison linéaire : 50 % force (soloQ ou pro) + 40 % affinité compo Meraki + "
        "10 % bonus/malus de side blue. Ce score alimente la sigmoïde qui produit la "
        "probabilité de victoire finale."
    ),
    "matchup 2v2": (
        "Comparaison des duos jungle-support ou bot lane adverses (winrate 2v2 mesuré ou estimé). "
        "Intégré qualitativement à l'analyse duo ; les duos internes mesurent la complémentarité "
        "au sein d'une même équipe."
    ),
    "synergie interne": (
        "Score de complémentarité d'un duo au sein de la même équipe (jungle+support ou adc+support), "
        "basé sur les games pro Oracle's Elixir quand disponibles, sinon estimation soloQ + Meraki."
    ),
    "mode pro": (
        "Prédiction basée uniquement sur les données pro : winrates Oracle's Elixir, duos et "
        "matchups 2v2 mesurés. Pas de fallback soloQ ; les données manquantes sont signalées."
    ),
    "mode mixte": (
        "Prédiction combinant force soloQ (patch EUW), affinité Meraki, bonus side, synergies "
        "duo internes et matchups 2v2 (pro quand disponible, sinon estimation soloQ + Meraki)."
    ),
    "données insuffisantes": (
        "Le modèle n'a pas assez de games pro pour ce champion, duo ou matchup. En mode pro, "
        "aucune estimation soloQ/Meraki ne remplace la donnée : le score est absent ou partiel "
        "et l'UI affiche « Données pro insuffisantes »."
    ),
    "side blue": (
        "Bonus historique mesuré sur Oracle's Elixir (~+3,2 pt vs 50 % neutre) appliqué à l'équipe "
        "blue dans le score pondéré (10 % du poids total). Red reçoit le malus symétrique."
    ),
    "side red": (
        "Malus side appliqué à l'équipe red dans le score pondéré, symétrique au bonus blue side."
    ),
    "bans manqués": (
        "Analyse rétrospective : pour chaque pick adverse, simulation d'un ban manqué avec "
        "recalcul du winrate. Seuls les bans avec un gain estimé ≥ 0,35 pt sont retenus, "
        "avec justification décomposée (force, synergie, duo)."
    ),
    "picks manqués": (
        "Pour l'équipe perdante : jusqu'à 3 alternatives par rôle remplaçant le pick actuel, "
        "recalcul via predict_draft. Le gain = delta en points de winrate, avec justification "
        "décomposée."
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
}

KNOWN_TERMS = sorted(TERM_DEFINITIONS.keys())

EXAMPLE_QUESTIONS = [
    "Pourquoi mon winrate est de 48 % ?",
    "C'est quoi l'affinité compo ?",
    "Si je mets Yasuo en mid, ça fait quoi ?",
    "Pourquoi Zac est suggéré en top ?",
]


def _normalize_text(text: str) -> str:
    lowered = text.lower().strip()
    normalized = unicodedata.normalize("NFD", lowered)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def extract_entities(question: str, available_champions: list[str]) -> dict[str, Any]:
    """Extrait champion, rôle et terme technique depuis la question."""
    normalized = _normalize_text(question)
    entities: dict[str, Any] = {
        "champion": None,
        "role": None,
        "term": None,
        "raw_question_normalized": normalized,
    }

    champion_match: str | None = None
    for champion in sorted(set(available_champions), key=lambda name: len(name), reverse=True):
        champion_norm = _normalize_text(champion)
        if re.search(rf"\b{re.escape(champion_norm)}\b", normalized):
            champion_match = champion
            break
    entities["champion"] = champion_match

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
    if re.search(r"\b(mon|notre|ma|mes)\b", normalized):
        prediction = context.get("prediction") or {}
        blue_prob = float(prediction.get("blue_win_probability", 0.5))
        red_prob = float(prediction.get("red_win_probability", 0.5))
        return "blue" if blue_prob <= red_prob else "red"
    return "blue"


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
        reasons.append(
            "des champions plus performants en pro"
            if is_pro
            else "des champions plus performants sur le patch soloQ"
        )
    if abs(synergy_diff) >= 1.5:
        reasons.append("une meilleure synergie de composition")

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
    reason = build_decomposed_reason(
        headline=f"Simulation : {champion} en {role.lower()}",
        decomposition=decomposition,
        role=role,
        candidate=champion,
        current=current,
        opponent=opponent,
        team=modified_team,
        baseline=baseline,
        updated=updated,
        team_side=team_side,
        changed_side="team",
        patch=patch,
        mode=mode,
    )

    return (
        f"Avant : {p_before * 100:.1f} % → Après : {p_after * 100:.1f} % "
        f"({decomposition['delta_total']:+.1f} pt). {reason}"
    )


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
        "Je ne peux répondre qu'à des questions sur les scores, les termes techniques du projet, "
        "ou des simulations de changement de pick. Reformule ta question avec un nom de champion "
        f"ou un terme précis. Exemples : {examples}."
    )


def answer_question(
    question: str,
    prediction_context: dict[str, Any],
    available_champions: list[str],
) -> dict[str, str]:
    """Point d'entrée principal du chatbot rule-based."""
    entities = extract_entities(question, available_champions)
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
