"""Tests integration meta_tierlist.csv avec get_meta_pool_for_role()."""

from __future__ import annotations

from unittest.mock import patch

import predict_draft as pd

from pro_force import (
    MIN_GAMES_EXCLUSION,
    get_meta_pool_for_role,
    load_presence_lookup,
    reset_pro_force_state,
)

PATCH = "16.13"
MOCK_LOW_VOLUME = "MockHighBanLowGames"


def test_low_volume_high_presence_still_excluded_from_pool() -> None:
    """20 games + presence_score eleve : filtre dur >= 30 prime toujours."""
    pd.reset_predict_state()
    import pro_force

    champion_features, _, lookup_by_norm = pd.get_meraki_context()
    real_lookup = dict(pro_force.get_pro_winrate_lookup())
    mocked_lookup = dict(real_lookup)
    mocked_lookup[(MOCK_LOW_VOLUME, "JUNGLE")] = (0.82, 20)

    mocked_presence = dict(load_presence_lookup())
    mocked_presence[(MOCK_LOW_VOLUME, "JUNGLE")] = 0.85

    with patch.object(pro_force, "get_pro_winrate_lookup", return_value=mocked_lookup):
        with patch.object(pro_force, "load_presence_lookup", return_value=mocked_presence):
            reset_pro_force_state()
            pool = get_meta_pool_for_role(
                "JUNGLE",
                PATCH,
                top_n=15,
                candidates=[MOCK_LOW_VOLUME, "Vi", "Pantheon", "Nocturne"],
                champion_features=champion_features,
                lookup_by_norm=lookup_by_norm,
            )

    assert MOCK_LOW_VOLUME not in pool
    assert len(pool) >= 1
    assert all(name != MOCK_LOW_VOLUME for name in pool)


def test_presence_bonus_can_reorder_without_bypassing_volume_filter() -> None:
    """Le bonus presence ne doit pas introduire un candidat sous MIN_GAMES_EXCLUSION."""
    pd.reset_predict_state()
    import pro_force

    champion_features, _, lookup_by_norm = pd.get_meraki_context()
    real_lookup = dict(pro_force.get_pro_winrate_lookup())

    with patch.object(pro_force, "get_pro_winrate_lookup", return_value=real_lookup):
        reset_pro_force_state()
        pool = get_meta_pool_for_role(
            "JUNGLE",
            PATCH,
            top_n=15,
            champion_features=champion_features,
            lookup_by_norm=lookup_by_norm,
        )

    pro_lookup = pro_force.get_pro_winrate_lookup()
    for name in pool:
        games = pro_lookup.get((name, "JUNGLE"), (0.0, 0))[1]
        assert games >= MIN_GAMES_EXCLUSION, f"{name} JUNGLE n'a que {games} games"
