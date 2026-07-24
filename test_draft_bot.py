"""Tests pour draft_bot.py."""

from __future__ import annotations

from unittest.mock import patch

import predict_draft as pd

from draft_bot import choose_bot_action
from pro_force import MIN_GAMES_EXCLUSION, get_meta_pool_for_role
from suggest_draft import get_champion_role_catalog, suggest_bot_pick

PATCH = "16.13"
MOCK_LOW_VOLUME = "MockLowVolume"


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


def test_choose_bot_pick_returns_champion_without_locked_role() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    bot_picks = [{"champion": "Gnar"}]
    opponent_picks = [{"champion": "Renekton"}]

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
    assert move["role"] is None


def test_choose_bot_pick_ignores_client_roles() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    # Rôles client volontairement absurdes : le bot doit quand même pick sans les figer.
    bot_picks = [{"champion": "Gnar", "role": "UTILITY"}]
    opponent_picks = [{"champion": "Renekton", "role": "UTILITY"}]

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
    assert move["role"] is None


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


def test_get_meta_pool_excludes_low_volume_champion() -> None:
    pd.reset_predict_state()
    import pro_force

    champion_features, _, lookup_by_norm = pd.get_meraki_context()
    real_lookup = dict(pro_force.get_pro_winrate_lookup())

    mocked_lookup = dict(real_lookup)
    mocked_lookup[(MOCK_LOW_VOLUME, "JUNGLE")] = (0.80, 14)

    with patch.object(pro_force, "get_pro_winrate_lookup", return_value=mocked_lookup):
        pro_force.reset_pro_force_state()
        pool = get_meta_pool_for_role(
            "JUNGLE",
            PATCH,
            top_n=15,
            candidates=[MOCK_LOW_VOLUME, "Vi", "Pantheon"],
            champion_features=champion_features,
            lookup_by_norm=lookup_by_norm,
        )

    assert MOCK_LOW_VOLUME not in pool
    assert "Vi" in pool


def test_bot_never_picks_low_volume_mock_even_with_high_synergy() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    import pro_force

    real_lookup = dict(pro_force.get_pro_winrate_lookup())
    mocked_lookup = dict(real_lookup)
    mocked_lookup[(MOCK_LOW_VOLUME, "JUNGLE")] = (0.80, 14)

    bot_picks: list[dict[str, str]] = []
    opponent_picks = [
        {"champion": "Olaf", "role": "TOP"},
        {"champion": "Galio", "role": "MIDDLE"},
    ]
    pool = _available_excluding(bot_picks, opponent_picks)
    pool = [MOCK_LOW_VOLUME, *pool]

    with patch.object(pro_force, "get_pro_winrate_lookup", return_value=mocked_lookup):
        pro_force.reset_pro_force_state()
        result = suggest_bot_pick(
            bot_partial_picks=bot_picks,
            opponent_partial_picks=opponent_picks,
            patch=PATCH,
            available_champions=pool,
            team_side="red",
            mode="pro",
        )

    assert result["champion"]
    assert result["champion"] != MOCK_LOW_VOLUME
    if result.get("pro_games") is not None:
        assert result["pro_games"] >= MIN_GAMES_EXCLUSION


def test_bot_pick_softmax_produces_role_diversity_across_seeds() -> None:
    """Sur plusieurs seeds, au moins 2 champions distincts par role touche."""
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    bot_picks = [
        {"champion": "Azir", "role": "MIDDLE"},
        {"champion": "Rumble", "role": "TOP"},
    ]
    opponent_picks = [
        {"champion": "Renekton", "role": "TOP"},
        {"champion": "Syndra", "role": "MIDDLE"},
    ]
    pool = _available_excluding(bot_picks, opponent_picks)

    picks_by_role: dict[str, set[str]] = {}
    for seed in (11, 22, 33, 44, 55, 66, 77, 88):
        result = suggest_bot_pick(
            bot_partial_picks=bot_picks,
            opponent_partial_picks=opponent_picks,
            patch=PATCH,
            available_champions=pool,
            team_side="blue",
            mode="pro",
            rng_seed=seed,
        )
        assert result["champion"] and result["role"]
        role = result["role"]
        picks_by_role.setdefault(role, set()).add(result["champion"])

    roles_with_multiple = [
        role for role, names in picks_by_role.items() if len(names) >= 2
    ]
    assert roles_with_multiple, (
        "Softmax trop deterministe: un seul champion par role sur 8 seeds — "
        f"distribution={ {r: sorted(n) for r, n in picks_by_role.items()} }"
    )


def test_bot_prioritizes_support_when_adc_locked() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    from suggest_draft import (
        BOT_ROLE_PRIORITY_DUO,
        _bot_role_priority_bonus,
        _bot_role_priority_multiplier,
    )

    bot_picks = [
        {"champion": "Caitlyn", "role": "BOTTOM"},
        {"champion": "Renekton", "role": "TOP"},
    ]
    remaining = ["JUNGLE", "MIDDLE", "UTILITY"]

    assert _bot_role_priority_multiplier(bot_picks, "UTILITY", remaining) >= BOT_ROLE_PRIORITY_DUO
    assert _bot_role_priority_multiplier(bot_picks, "JUNGLE", remaining) == 1.0
    assert _bot_role_priority_bonus(bot_picks, "UTILITY", remaining) > 0.0
    assert _bot_role_priority_bonus(bot_picks, "JUNGLE", remaining) == 0.0


def test_bot_pick_favors_support_after_adc_lock() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    bot_picks = [
        {"champion": "Caitlyn", "role": "BOTTOM"},
        {"champion": "Renekton", "role": "TOP"},
        {"champion": "Azir", "role": "MIDDLE"},
    ]
    opponent_picks = [
        {"champion": "Gnar", "role": "TOP"},
        {"champion": "Syndra", "role": "MIDDLE"},
    ]
    pool = _available_excluding(bot_picks, opponent_picks)

    support_scores: list[float] = []
    jungle_scores: list[float] = []
    for candidate in pool[:40]:
        from suggest_draft import decompose_bot_candidate_score

        sup_row = decompose_bot_candidate_score(
            bot_picks,
            opponent_picks,
            candidate,
            "UTILITY",
            PATCH,
            pool,
            team_side="blue",
            mode="pro",
        )
        jg_row = decompose_bot_candidate_score(
            bot_picks,
            opponent_picks,
            candidate,
            "JUNGLE",
            PATCH,
            pool,
            team_side="blue",
            mode="pro",
        )
        if sup_row:
            support_scores.append(sup_row["selection_score"])
        if jg_row:
            jungle_scores.append(jg_row["selection_score"])

    assert support_scores and jungle_scores
    assert max(support_scores) >= max(jungle_scores)


def test_lookahead_duo_bonus_favors_jungle_with_support_synergy() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    from suggest_draft import _lookahead_duo_bonus, get_champion_role_catalog

    bot_picks = [{"champion": "Renekton", "role": "TOP"}]
    opponent_picks = [{"champion": "Azir", "role": "MIDDLE"}]
    pool = _available_excluding(bot_picks, opponent_picks)
    catalog = get_champion_role_catalog()

    vi_bonus = _lookahead_duo_bonus(
        bot_picks, "Vi", "JUNGLE", pool, catalog, PATCH, "pro"
    )
    taliyah_bonus = _lookahead_duo_bonus(
        bot_picks, "Taliyah", "JUNGLE", pool, catalog, PATCH, "pro"
    )

    assert vi_bonus >= 0.0
    assert vi_bonus >= taliyah_bonus


def test_duo_denial_ban_boost_targets_bot_lane_partner() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    from suggest_draft import _duo_denial_ban_boost

    opponent = [{"champion": "Caitlyn", "role": "BOTTOM"}]
    support_boost = _duo_denial_ban_boost(opponent, "Nautilus", "UTILITY", "pro")
    jungle_boost = _duo_denial_ban_boost(opponent, "Nocturne", "JUNGLE", "pro")

    assert support_boost >= 0.0
    assert support_boost >= jungle_boost


def test_bot_pick_reason_follows_narrative_order() -> None:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()

    from justification_builder import assert_narrative_order, section_positions

    bot_picks = [
        {"champion": "Corki", "role": "BOTTOM"},
        {"champion": "Leona", "role": "UTILITY"},
    ]
    opponent_picks = [
        {"champion": "Renekton", "role": "TOP"},
        {"champion": "Graves", "role": "JUNGLE"},
        {"champion": "Syndra", "role": "MIDDLE"},
    ]
    result = suggest_bot_pick(
        bot_partial_picks=bot_picks,
        opponent_partial_picks=opponent_picks,
        patch=PATCH,
        available_champions=_available_excluding(bot_picks, opponent_picks),
        team_side="blue",
        mode="pro",
        rng_seed=7,
    )

    assert result.get("reason")
    assert_narrative_order(result["reason"])
    positions = section_positions(result["reason"])
    assert "meta" in positions
    if "duo" in positions and "composition" in positions:
        assert positions["composition"] < positions["duo"]
