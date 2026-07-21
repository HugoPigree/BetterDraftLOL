"""Tests du chatbot rule-based (chatbot_rules.py)."""

from __future__ import annotations

import predict_draft as pd
from chatbot_rules import (
    EXAMPLE_QUESTIONS,
    answer_question,
    detect_intent,
    extract_entities,
)
from suggest_draft import (
    build_matchup_teams,
    get_champion_role_catalog,
    replace_role_pick,
    slots_to_team,
    team_side_win_probability,
)

BLUE = [
    {"champion": "Gnar", "role": "TOP"},
    {"champion": "Xin Zhao", "role": "JUNGLE"},
    {"champion": "Ahri", "role": "MIDDLE"},
    {"champion": "Corki", "role": "BOTTOM"},
    {"champion": "Leona", "role": "UTILITY"},
]
RED = [
    {"champion": "Gwen", "role": "TOP"},
    {"champion": "Viego", "role": "JUNGLE"},
    {"champion": "Syndra", "role": "MIDDLE"},
    {"champion": "Jhin", "role": "BOTTOM"},
    {"champion": "Nautilus", "role": "UTILITY"},
]
PATCH = "16.13"


def _available() -> list[str]:
    catalog = get_champion_role_catalog()
    used = {slot["champion"].casefold() for slot in BLUE + RED}
    return sorted(name for name in catalog if name.casefold() not in used)


def _build_context(
    *,
    retrospective_picks: list[dict] | None = None,
    focus_team_side: str = "red",
) -> dict:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()
    prediction = pd.predict_draft(BLUE, RED, patch=PATCH)
    return {
        "mode": "mixed",
        "patch": PATCH,
        "focus_team_side": focus_team_side,
        "blue_team": BLUE,
        "red_team": RED,
        "prediction": prediction,
        "retrospective_picks": retrospective_picks or [],
        "retrospective_bans": [],
    }


class TestDetectIntent:
    def test_define_term_formulations(self) -> None:
        assert detect_intent("C'est quoi l'affinité compo ?")["intent"] == "define_term"
        assert detect_intent("Qu'est-ce que le score pondéré ?")["intent"] == "define_term"

    def test_explain_score_formulations(self) -> None:
        assert detect_intent("Pourquoi mon winrate est bas ?")["intent"] == "explain_score"
        assert detect_intent("Pourquoi blue est favorite ?")["intent"] == "explain_score"

    def test_simulate_change_formulations(self) -> None:
        assert detect_intent("Si je mets Zac en top ?")["intent"] == "simulate_change"
        assert detect_intent("Si on remplace Gwen par Fiora top")["intent"] == "simulate_change"

    def test_explain_suggestion_formulations(self) -> None:
        assert detect_intent("Pourquoi Zac ?")["intent"] == "explain_suggestion"
        assert detect_intent("Pourquoi suggérer Camille")["intent"] == "explain_suggestion"

    def test_unknown(self) -> None:
        assert detect_intent("Salut comment ça va ?")["intent"] == "unknown"


class TestExtractEntities:
    def test_champion_and_role(self) -> None:
        avail = _available()
        entities = extract_entities("Si je mets Zac en top lane", avail)
        assert entities["champion"] == "Zac"
        assert entities["role"] == "TOP"

    def test_term(self) -> None:
        entities = extract_entities("Explique le mode pro", _available())
        assert entities["term"] == "mode pro"


class TestAnswerQuestion:
    def test_define_term_returns_definition(self) -> None:
        result = answer_question(
            "C'est quoi la synergie interne ?",
            _build_context(),
            _available(),
        )
        assert result["intent_detected"] == "define_term"
        assert "synergie interne" in result["answer"].lower()

    def test_explain_score_uses_prediction(self) -> None:
        ctx = _build_context(focus_team_side="red")
        result = answer_question(
            "Pourquoi mon winrate est faible ?",
            ctx,
            _available(),
        )
        assert result["intent_detected"] == "explain_score"
        assert "Winrate estimé RED" in result["answer"]
        assert "Affinité compo" in result["answer"]

    def test_explain_suggestion_returns_reason(self) -> None:
        ctx = _build_context(
            retrospective_picks=[
                {
                    "champion": "Zac",
                    "role": "TOP",
                    "reason": "Zac à la place de Gwen (top) +1.6 pt au total.",
                }
            ],
        )
        result = answer_question("Pourquoi Zac ?", ctx, _available())
        assert result["intent_detected"] == "explain_suggestion"
        assert "Zac à la place de Gwen" in result["answer"]

    def test_unknown_shows_examples(self) -> None:
        result = answer_question("Bonjour", _build_context(), _available())
        assert result["intent_detected"] == "unknown"
        assert EXAMPLE_QUESTIONS[0].split("'")[0] in result["answer"] or "Pourquoi" in result["answer"]

    def test_simulate_change_matches_predict_draft(self) -> None:
        pd.reset_predict_state()
        pd.initialize_blue_side_winrate()
        avail = _available()
        ctx = _build_context(focus_team_side="red")

        team = slots_to_team(RED)
        opponent = slots_to_team(BLUE)
        baseline = pd.predict_draft(BLUE, RED, patch=PATCH)
        modified = replace_role_pick(team, "TOP", "Zac")
        mod_blue, mod_red = build_matchup_teams(modified, opponent, "red")
        updated = pd.predict_draft(mod_blue, mod_red, patch=PATCH)
        expected_before = team_side_win_probability(baseline, "red")
        expected_after = team_side_win_probability(updated, "red")
        expected_delta = round((expected_after - expected_before) * 100, 2)

        result = answer_question(
            "Si je mets Zac en top, ça fait quoi ?",
            ctx,
            avail,
        )
        assert result["intent_detected"] == "simulate_change"
        assert f"{expected_before * 100:.1f} %" in result["answer"]
        assert f"{expected_after * 100:.1f} %" in result["answer"]
        assert f"{expected_delta:+.1f} pt" in result["answer"]

    def test_simulate_change_second_formulation(self) -> None:
        ctx = _build_context(focus_team_side="red")
        result = answer_question(
            "Si on pick Camille top à la place",
            ctx,
            _available(),
        )
        assert result["intent_detected"] == "simulate_change"
        assert "Simulation" in result["answer"] or "Avant" in result["answer"]
