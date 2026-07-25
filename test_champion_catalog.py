"""Tests catalogue unifié Meraki + Data Dragon + Oracle."""

from __future__ import annotations

import build_training_dataset as btd
from champion_catalog import (
    build_api_position_catalog,
    infer_oracle_positions,
    list_estimated_champion_names,
    load_unified_champions,
    merge_champion_catalog,
)
from data_refresh.constants import DEFAULT_ORACLE_CSV, MERAKI_CACHE_PATH


def test_unified_catalog_includes_locke_and_zaahen() -> None:
    if not MERAKI_CACHE_PATH.exists():
        return

    champions = load_unified_champions(ensure_ddragon=True)
    names = {payload.get("name", key) for key, payload in champions.items()}
    assert "Locke" in names
    assert "Zaahen" in names


def test_estimated_champions_have_roles_and_positions() -> None:
    if not MERAKI_CACHE_PATH.exists():
        return

    champions = load_unified_champions(ensure_ddragon=True)
    estimated = list_estimated_champion_names(champions)
    assert "Locke" in estimated or "Zaahen" in estimated

    for name in ("Locke", "Zaahen"):
        entry = champions.get(name)
        assert entry is not None, name
        assert entry.get("roles")
        assert entry.get("positions")
        assert entry.get("attributeRatings")


def test_zaahen_positions_from_oracle_pro() -> None:
    if not DEFAULT_ORACLE_CSV.exists():
        return

    positions = infer_oracle_positions(DEFAULT_ORACLE_CSV)
    assert "TOP" in positions.get("Zaahen", [])
    assert "JUNGLE" in positions.get("Zaahen", [])


def test_api_catalog_maps_support_to_utility() -> None:
    if not MERAKI_CACHE_PATH.exists():
        return

    champions = load_unified_champions(ensure_ddragon=False)
    catalog = build_api_position_catalog(champions)
    for positions in catalog.values():
        assert "SUPPORT" not in positions


def test_build_champion_feature_dict_includes_estimated() -> None:
    if not MERAKI_CACHE_PATH.exists():
        return

    champions = btd.load_meraki_champions(btd.MERAKI_URL, btd.DEFAULT_MERAKI_CACHE)
    features, role_tags = btd.build_champion_feature_dict(champions)
    assert "Locke" in features
    assert "Zaahen" in features
    assert any(tag in role_tags for tag in features["Zaahen"]["roles"])


def test_merge_does_not_duplicate_meraki_entries() -> None:
    meraki = {"Ahri": {"name": "Ahri", "positions": ["MIDDLE"], "roles": ["BURST"], "attributeRatings": {}}}
    ddragon = {
        "Ahri": {"id": "Ahri", "name": "Ahri", "tags": ["Mage"], "info": {}, "stats": {}},
        "Locke": {
            "id": "Locke",
            "name": "Locke",
            "tags": ["Assassin", "Mage"],
            "info": {"attack": 6, "defense": 4, "magic": 2, "difficulty": 5},
            "stats": {"movespeed": 340, "attackrange": 125},
        },
    }
    merged, estimated = merge_champion_catalog(meraki, ddragon, {"Locke": ["MIDDLE"]}, ddragon_version="16.14.1")
    assert "Ahri" in merged
    assert "Locke" in merged
    assert estimated == ["Locke"]
    assert len(merged) == 2
