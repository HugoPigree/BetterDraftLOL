"""Tests pour build_duo_dataset.py."""

from __future__ import annotations

from build_duo_dataset import (
    SEUIL_MIN_GAMES,
    aggregate_bot_lane_matchups,
    aggregate_duos,
    aggregate_jungle_support_matchups,
    get_duo_score,
    load_duo_table,
    lookup_bot_lane_matchup,
    lookup_jungle_support_matchup,
    normalize_duo_pair,
    reset_duo_cache,
)


def test_normalize_duo_pair_is_order_invariant() -> None:
    assert normalize_duo_pair("Leona", "Xin Zhao") == normalize_duo_pair("Xin Zhao", "Leona")


def test_aggregate_duos_computes_winrate() -> None:
    records = [
        {"champion_1": "A", "champion_2": "B", "result": 1},
        {"champion_1": "A", "champion_2": "B", "result": 0},
        {"champion_1": "A", "champion_2": "B", "result": 1},
    ]
    df = aggregate_duos(records)
    assert len(df) == 1
    assert int(df.iloc[0]["games"]) == 3
    assert float(df.iloc[0]["winrate"]) == 0.6667


def test_get_duo_score_measured_vs_fallback() -> None:
    reset_duo_cache()
    measured = get_duo_score("Xin Zhao", "Seraphine", "jungle_support")
    assert measured.is_fallback is False
    assert measured.games >= SEUIL_MIN_GAMES

    fallback = get_duo_score("Gnar", "Ahri", "jungle_support")
    assert fallback.is_fallback is True
    assert fallback.games < SEUIL_MIN_GAMES


def test_duo_csv_files_exist_and_load() -> None:
    reset_duo_cache()
    js = load_duo_table("jungle_support")
    bl = load_duo_table("bot_lane")
    assert {"champion_1", "champion_2", "games", "winrate"}.issubset(js.columns)
    assert {"champion_1", "champion_2", "games", "winrate"}.issubset(bl.columns)
    assert len(js) > 0
    assert len(bl) > 0


def test_aggregate_bot_lane_matchups() -> None:
    records = [
        {
            "blue_adc": "Lucian",
            "blue_sup": "Nami",
            "red_adc": "Jhin",
            "red_sup": "Nautilus",
            "blue_win": 1,
        },
        {
            "blue_adc": "Lucian",
            "blue_sup": "Nami",
            "red_adc": "Jhin",
            "red_sup": "Nautilus",
            "blue_win": 0,
        },
    ]
    df = aggregate_bot_lane_matchups(records)
    assert len(df) == 1
    assert int(df.iloc[0]["games"]) == 2
    assert float(df.iloc[0]["blue_winrate"]) == 0.5


def test_lookup_bot_lane_matchup_supports_flipped_key(monkeypatch) -> None:
    reset_duo_cache()
    import build_duo_dataset as bdd
    import pandas as pd

    bdd._matchup_table = pd.DataFrame(
        [
            {
                "blue_adc": "Jhin",
                "blue_sup": "Nautilus",
                "red_adc": "Lucian",
                "red_sup": "Nami",
                "games": 20,
                "blue_winrate": 0.4,
            }
        ]
    )

    games, blue_wr = lookup_bot_lane_matchup("Lucian", "Nami", "Jhin", "Nautilus")
    assert games == 20
    assert blue_wr == 0.6


def test_aggregate_jungle_support_matchups() -> None:
    records = [
        {
            "blue_jungle": "Xin Zhao",
            "blue_support": "Leona",
            "red_jungle": "Graves",
            "red_support": "Nautilus",
            "blue_win": 1,
        },
        {
            "blue_jungle": "Xin Zhao",
            "blue_support": "Leona",
            "red_jungle": "Graves",
            "red_support": "Nautilus",
            "blue_win": 0,
        },
    ]
    df = aggregate_jungle_support_matchups(records)
    assert len(df) == 1
    assert int(df.iloc[0]["games"]) == 2
    assert float(df.iloc[0]["blue_winrate"]) == 0.5


def test_lookup_jungle_support_matchup_supports_flipped_key(monkeypatch) -> None:
    reset_duo_cache()
    import build_duo_dataset as bdd
    import pandas as pd

    bdd._js_matchup_table = pd.DataFrame(
        [
            {
                "blue_jungle": "Graves",
                "blue_support": "Nautilus",
                "red_jungle": "Xin Zhao",
                "red_support": "Leona",
                "games": 25,
                "blue_winrate": 0.44,
            }
        ]
    )

    games, blue_wr = lookup_jungle_support_matchup("Xin Zhao", "Leona", "Graves", "Nautilus")
    assert games == 25
    assert blue_wr == 0.56
