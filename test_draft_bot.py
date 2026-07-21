"""Tests pour draft_bot.py."""

from __future__ import annotations

import predict_draft as pd

from draft_bot import choose_bot_action
from suggest_draft import get_champion_role_catalog

PATCH = "16.13"


def _available_excluding(*teams: list[dict[str, str]]) -> list[str]:
    catalog = get_champion_role_catalog()
    used = {slot["champion"].casefold() for team in teams for slot in team}
    return sorted(
        [name for name in catalog if name.casefold() not in used],
        key=str.casefold,
    )


def test_choose_bot_ban_returns_champion() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    move = choose_bot_action(
        action_type="ban",
        bot_side="blue",
        bot_picks=[],
        opponent_picks=[],
        patch=PATCH,
        available_champions=_available_excluding(),
    )

    assert move["action"] == "ban"
    assert move["champion"]
    assert move["role"] is None


def test_choose_bot_pick_returns_champion_and_role() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    bot_picks = [{"champion": "Gnar", "role": "TOP"}]
    opponent_picks = [{"champion": "Renekton", "role": "TOP"}]

    move = choose_bot_action(
        action_type="pick",
        bot_side="blue",
        bot_picks=bot_picks,
        opponent_picks=opponent_picks,
        patch=PATCH,
        available_champions=_available_excluding(bot_picks, opponent_picks),
        mode="pro",
    )

    assert move["action"] == "pick"
    assert move["champion"]
    assert move["role"] in {"JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"}


def test_suggest_bot_pick_prefers_meta_candidate() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    from suggest_draft import suggest_bot_pick

    bot_picks = [
        {"champion": "Azir", "role": "MIDDLE"},
        {"champion": "Rumble", "role": "TOP"},
    ]
    opponent_picks = [
        {"champion": "Renekton", "role": "TOP"},
        {"champion": "Syndra", "role": "MIDDLE"},
    ]
    pool = _available_excluding(bot_picks, opponent_picks)

    result = suggest_bot_pick(
        bot_partial_picks=bot_picks,
        opponent_partial_picks=opponent_picks,
        patch=PATCH,
        available_champions=pool,
        team_side="blue",
        mode="pro",
        candidates_per_role=8,
    )

    assert result["champion"]
    assert result["role"] in {"JUNGLE", "BOTTOM", "UTILITY"}
    assert result["win_probability"] is not None
    assert result["synergy"] is not None


def test_bot_ranks_meta_volume_above_low_sample_winrate() -> None:
    from pro_force import pro_meta_score
    from predict_draft import get_meraki_context

    champion_features, _, lookup_by_norm = get_meraki_context()
    riven = pro_meta_score("Riven", "TOP", champion_features, lookup_by_norm)
    gnar = pro_meta_score("Gnar", "TOP", champion_features, lookup_by_norm)

    assert riven is not None and gnar is not None
    assert gnar[0] > riven[0]
    assert gnar[1] > riven[1]  # plus de games pro


def test_pro_role_fitness_filters_off_role_flex() -> None:
    from pro_force import is_pro_viable_on_role, pro_role_fitness
    from predict_draft import get_meraki_context

    champion_features, _, lookup_by_norm = get_meraki_context()

    taliyah_jg = pro_role_fitness(
        "Taliyah", "JUNGLE", champion_features, lookup_by_norm
    )
    taliyah_mid = pro_role_fitness(
        "Taliyah", "MIDDLE", champion_features, lookup_by_norm
    )
    assert taliyah_mid == 1.0
    assert taliyah_jg < 0.20
    assert not is_pro_viable_on_role(
        "Taliyah", "JUNGLE", champion_features, lookup_by_norm
    )


def test_pro_force_uses_meta_not_raw_low_sample_winrate() -> None:
    from predict_draft import compute_pro_force_score, get_meraki_context

    champion_features, _, lookup_by_norm = get_meraki_context()

    meta_comp = [
        {"champion": "Gnar", "role": "TOP"},
        {"champion": "Vi", "role": "JUNGLE"},
        {"champion": "Ahri", "role": "MIDDLE"},
        {"champion": "Caitlyn", "role": "BOTTOM"},
        {"champion": "Nautilus", "role": "UTILITY"},
    ]
    noise_comp = [
        {"champion": "Riven", "role": "TOP"},
        {"champion": "Taliyah", "role": "JUNGLE"},
        {"champion": "Yasuo", "role": "MIDDLE"},
        {"champion": "Caitlyn", "role": "BOTTOM"},
        {"champion": "Lux", "role": "UTILITY"},
    ]

    meta_force, _, _, _ = compute_pro_force_score(
        meta_comp, champion_features, lookup_by_norm
    )
    noise_force, _, _, _ = compute_pro_force_score(
        noise_comp, champion_features, lookup_by_norm
    )

    assert meta_force is not None and noise_force is not None
    assert meta_force > noise_force


def test_suggest_bot_pick_avoids_riven_top() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    from suggest_draft import suggest_bot_pick

    bot_picks: list[dict[str, str]] = []
    opponent_picks = [
        {"champion": "Olaf", "role": "TOP"},
        {"champion": "Trundle", "role": "JUNGLE"},
        {"champion": "Galio", "role": "MIDDLE"},
    ]
    pool = _available_excluding(bot_picks, opponent_picks)

    result = suggest_bot_pick(
        bot_partial_picks=bot_picks,
        opponent_partial_picks=opponent_picks,
        patch=PATCH,
        available_champions=pool,
        team_side="red",
        mode="pro",
        candidates_per_role=10,
    )

    assert result["champion"]
    assert result["champion"] != "Riven"
    if result.get("role_fitness") is not None:
        assert result["role_fitness"] >= 0.20
