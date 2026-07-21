#!/usr/bin/env python3
"""Build jungle-support and bot-lane duo winrate datasets from Oracle's Elixir."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

import build_training_dataset as btd

SEUIL_MIN_GAMES = 15

DATA_DIR = Path("data")
DEFAULT_ORACLE_CSV = DATA_DIR / "2026_LoL_esports_match_data_from_OraclesElixir.csv"
DUO_JUNGLE_SUPPORT_CSV = DATA_DIR / "duo_jungle_support.csv"
DUO_BOT_LANE_CSV = DATA_DIR / "duo_bot_lane.csv"
BOT_LANE_MATCHUP_CSV = DATA_DIR / "bot_lane_matchup.csv"
JUNGLE_SUPPORT_MATCHUP_CSV = DATA_DIR / "jungle_support_matchup.csv"

PLAYER_POSITIONS = {"top", "jng", "mid", "bot", "sup"}
DuoType = Literal["jungle_support", "bot_lane"]

DUO_CSV_PATHS: dict[DuoType, Path] = {
    "jungle_support": DUO_JUNGLE_SUPPORT_CSV,
    "bot_lane": DUO_BOT_LANE_CSV,
}

_duo_tables: dict[DuoType, pd.DataFrame | None] = {
    "jungle_support": None,
    "bot_lane": None,
}
_matchup_table: pd.DataFrame | None = None
_js_matchup_table: pd.DataFrame | None = None
_champion_features: dict[str, dict[str, Any]] | None = None
_champion_positions: dict[str, set[str]] | None = None
_lookup_by_norm: dict[str, str] | None = None


@dataclass(frozen=True)
class DuoScore:
    score: float | None
    is_fallback: bool
    games: int
    champion_1: str
    champion_2: str
    duo_type: DuoType
    insufficient_data: bool = False


@dataclass(frozen=True)
class BotLaneMatchupLookup:
    blue_win_probability: float
    games: int
    is_measured: bool


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def normalize_duo_pair(champion_a: str, champion_b: str) -> tuple[str, str]:
    cleaned = champion_a.strip(), champion_b.strip()
    return tuple(sorted(cleaned, key=str.casefold))


def load_player_rows(oracle_csv: Path) -> pd.DataFrame:
    logging.info("Chargement Oracle's Elixir: %s", oracle_csv)
    df = pd.read_csv(oracle_csv, low_memory=False)
    players = df[
        (df["datacompleteness"] == "complete")
        & (df["position"].isin(PLAYER_POSITIONS))
    ].copy()
    logging.info("%d lignes joueur (complete)", len(players))
    return players


def build_duo_records(players: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pivot = players.pivot_table(
        index=["gameid", "side"],
        columns="position",
        values="champion",
        aggfunc="first",
    )
    results = players.groupby(["gameid", "side"], sort=False)["result"].first()

    jungle_support_records: list[dict[str, Any]] = []
    bot_lane_records: list[dict[str, Any]] = []

    for (gameid, side), champions in pivot.iterrows():
        if len(champions.dropna()) != 5:
            continue

        result = int(results.loc[(gameid, side)])
        jungle = str(champions.get("jng", "")).strip()
        bot = str(champions.get("bot", "")).strip()
        support = str(champions.get("sup", "")).strip()
        if not support:
            continue

        if jungle:
            pair = normalize_duo_pair(jungle, support)
            jungle_support_records.append(
                {"champion_1": pair[0], "champion_2": pair[1], "result": result}
            )
        if bot:
            pair = normalize_duo_pair(bot, support)
            bot_lane_records.append(
                {"champion_1": pair[0], "champion_2": pair[1], "result": result}
            )

    logging.info(
        "Duos extraits: %d jungle-support, %d bot lane (%d games équipe)",
        len(jungle_support_records),
        len(bot_lane_records),
        len(pivot),
    )
    return jungle_support_records, bot_lane_records


def build_bot_lane_matchup_records(players: pd.DataFrame) -> list[dict[str, Any]]:
    pivot = players.pivot_table(
        index=["gameid", "side"],
        columns="position",
        values="champion",
        aggfunc="first",
    )
    results = players.groupby(["gameid", "side"], sort=False)["result"].first()
    records: list[dict[str, Any]] = []

    for gameid in pivot.index.get_level_values("gameid").unique():
        try:
            blue_row = pivot.loc[(gameid, "Blue")]
            red_row = pivot.loc[(gameid, "Red")]
            blue_win = int(results.loc[(gameid, "Blue")])
        except KeyError:
            continue

        if len(blue_row.dropna()) != 5 or len(red_row.dropna()) != 5:
            continue

        blue_adc = str(blue_row.get("bot", "")).strip()
        blue_sup = str(blue_row.get("sup", "")).strip()
        red_adc = str(red_row.get("bot", "")).strip()
        red_sup = str(red_row.get("sup", "")).strip()
        if not all([blue_adc, blue_sup, red_adc, red_sup]):
            continue

        records.append(
            {
                "blue_adc": blue_adc,
                "blue_sup": blue_sup,
                "red_adc": red_adc,
                "red_sup": red_sup,
                "blue_win": blue_win,
            }
        )

    logging.info("Matchups bot lane extraits: %d games", len(records))
    return records


def build_jungle_support_matchup_records(players: pd.DataFrame) -> list[dict[str, Any]]:
    pivot = players.pivot_table(
        index=["gameid", "side"],
        columns="position",
        values="champion",
        aggfunc="first",
    )
    results = players.groupby(["gameid", "side"], sort=False)["result"].first()
    records: list[dict[str, Any]] = []

    for gameid in pivot.index.get_level_values("gameid").unique():
        try:
            blue_row = pivot.loc[(gameid, "Blue")]
            red_row = pivot.loc[(gameid, "Red")]
            blue_win = int(results.loc[(gameid, "Blue")])
        except KeyError:
            continue

        if len(blue_row.dropna()) != 5 or len(red_row.dropna()) != 5:
            continue

        blue_jungle = str(blue_row.get("jng", "")).strip()
        blue_support = str(blue_row.get("sup", "")).strip()
        red_jungle = str(red_row.get("jng", "")).strip()
        red_support = str(red_row.get("sup", "")).strip()
        if not all([blue_jungle, blue_support, red_jungle, red_support]):
            continue

        records.append(
            {
                "blue_jungle": blue_jungle,
                "blue_support": blue_support,
                "red_jungle": red_jungle,
                "red_support": red_support,
                "blue_win": blue_win,
            }
        )

    logging.info("Matchups jungle-support extraits: %d games", len(records))
    return records


def aggregate_bot_lane_matchups(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(
            columns=["blue_adc", "blue_sup", "red_adc", "red_sup", "games", "blue_winrate"]
        )

    df = pd.DataFrame(records)
    grouped = df.groupby(
        ["blue_adc", "blue_sup", "red_adc", "red_sup"],
        as_index=False,
    ).agg(
        games=("blue_win", "count"),
        blue_winrate=("blue_win", "mean"),
    )
    grouped["blue_winrate"] = grouped["blue_winrate"].round(4)
    return grouped.sort_values(
        ["games", "blue_adc", "blue_sup", "red_adc", "red_sup"],
        ascending=[False, True, True, True, True],
    )


def aggregate_jungle_support_matchups(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(
            columns=[
                "blue_jungle",
                "blue_support",
                "red_jungle",
                "red_support",
                "games",
                "blue_winrate",
            ]
        )

    df = pd.DataFrame(records)
    grouped = df.groupby(
        ["blue_jungle", "blue_support", "red_jungle", "red_support"],
        as_index=False,
    ).agg(
        games=("blue_win", "count"),
        blue_winrate=("blue_win", "mean"),
    )
    grouped["blue_winrate"] = grouped["blue_winrate"].round(4)
    return grouped.sort_values(
        ["games", "blue_jungle", "blue_support", "red_jungle", "red_support"],
        ascending=[False, True, True, True, True],
    )


def aggregate_duos(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=["champion_1", "champion_2", "games", "winrate"])

    df = pd.DataFrame(records)
    grouped = df.groupby(["champion_1", "champion_2"], as_index=False).agg(
        games=("result", "count"),
        winrate=("result", "mean"),
    )
    grouped["winrate"] = grouped["winrate"].round(4)
    return grouped.sort_values(["games", "champion_1", "champion_2"], ascending=[False, True, True])


def export_duo_table(df: pd.DataFrame, output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)
    logging.info("Exporté: %s (%d duos uniques)", output_csv, len(df))


def log_duo_coverage(df: pd.DataFrame, label: str) -> tuple[int, int]:
    reliable = int((df["games"] >= SEUIL_MIN_GAMES).sum()) if not df.empty else 0
    fallback = int(len(df) - reliable) if not df.empty else 0
    logging.info(
        "%s — duos fiables (>= %d games): %d | duos sous seuil (fallback si demandés): %d",
        label,
        SEUIL_MIN_GAMES,
        reliable,
        fallback,
    )
    return reliable, fallback


def _ensure_meraki_context() -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    global _champion_features, _champion_positions, _lookup_by_norm
    if (
        _champion_features is None
        or _champion_positions is None
        or _lookup_by_norm is None
    ):
        champions = btd.load_meraki_champions(btd.MERAKI_URL, btd.DEFAULT_MERAKI_CACHE)
        _champion_features, _ = btd.build_champion_feature_dict(champions)
        _champion_positions = {}
        _lookup_by_norm = {btd.normalize_name(key): key for key in _champion_features}
        for key, payload in champions.items():
            _lookup_by_norm[btd.normalize_name(payload.get("name", key))] = key
            positions = {str(position).upper() for position in payload.get("positions", [])}
            _champion_positions[key] = positions
    return _champion_features, _lookup_by_norm


def reset_duo_cache() -> None:
    global _duo_tables, _champion_features, _champion_positions, _lookup_by_norm
    global _matchup_table, _js_matchup_table
    _duo_tables = {"jungle_support": None, "bot_lane": None}
    _matchup_table = None
    _js_matchup_table = None
    _champion_features = None
    _champion_positions = None
    _lookup_by_norm = None


def load_duo_table(duo_type: DuoType, csv_path: Path | None = None) -> pd.DataFrame:
    if _duo_tables[duo_type] is not None:
        return _duo_tables[duo_type]

    path = csv_path or DUO_CSV_PATHS[duo_type]
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset duo introuvable ({duo_type}): {path}. "
            f"Lance: python build_duo_dataset.py"
        )

    df = pd.read_csv(path)
    _duo_tables[duo_type] = df
    return df


def _lookup_measured_games(
    champion_1: str,
    champion_2: str,
    duo_type: DuoType,
) -> tuple[int, float | None]:
    """Retourne (games, winrate) ou (games, None) si sous le seuil de fiabilité."""
    pair = normalize_duo_pair(champion_1, champion_2)
    df = load_duo_table(duo_type)
    match = df[(df["champion_1"] == pair[0]) & (df["champion_2"] == pair[1])]
    if match.empty:
        return 0, None

    row = match.iloc[0]
    games = int(row["games"])
    if games < SEUIL_MIN_GAMES:
        return games, None
    return games, float(row["winrate"])


def load_bot_lane_matchup_table(csv_path: Path | None = None) -> pd.DataFrame:
    global _matchup_table
    if _matchup_table is not None:
        return _matchup_table

    path = csv_path or BOT_LANE_MATCHUP_CSV
    columns = ["blue_adc", "blue_sup", "red_adc", "red_sup", "games", "blue_winrate"]
    if not path.exists():
        _matchup_table = pd.DataFrame(columns=columns)
        return _matchup_table

    df = pd.read_csv(path)
    _matchup_table = df
    return df


def lookup_bot_lane_matchup(
    blue_adc: str,
    blue_sup: str,
    red_adc: str,
    red_sup: str,
) -> tuple[int, float | None]:
    """Retourne (games, blue_winrate) pour un 2v2 bot lane, ou (games, None) si absent."""
    df = load_bot_lane_matchup_table()
    if df.empty:
        return 0, None

    exact = df[
        (df["blue_adc"] == blue_adc)
        & (df["blue_sup"] == blue_sup)
        & (df["red_adc"] == red_adc)
        & (df["red_sup"] == red_sup)
    ]
    if not exact.empty:
        row = exact.iloc[0]
        return int(row["games"]), float(row["blue_winrate"])

    flipped = df[
        (df["blue_adc"] == red_adc)
        & (df["blue_sup"] == red_sup)
        & (df["red_adc"] == blue_adc)
        & (df["red_sup"] == blue_sup)
    ]
    if not flipped.empty:
        row = flipped.iloc[0]
        return int(row["games"]), round(1.0 - float(row["blue_winrate"]), 4)

    return 0, None


def load_jungle_support_matchup_table(csv_path: Path | None = None) -> pd.DataFrame:
    global _js_matchup_table
    if _js_matchup_table is not None:
        return _js_matchup_table

    path = csv_path or JUNGLE_SUPPORT_MATCHUP_CSV
    columns = [
        "blue_jungle",
        "blue_support",
        "red_jungle",
        "red_support",
        "games",
        "blue_winrate",
    ]
    if not path.exists():
        _js_matchup_table = pd.DataFrame(columns=columns)
        return _js_matchup_table

    df = pd.read_csv(path)
    _js_matchup_table = df
    return df


def lookup_jungle_support_matchup(
    blue_jungle: str,
    blue_support: str,
    red_jungle: str,
    red_support: str,
) -> tuple[int, float | None]:
    """Retourne (games, blue_winrate) pour un 2v2 jungle-support."""
    df = load_jungle_support_matchup_table()
    if df.empty:
        return 0, None

    exact = df[
        (df["blue_jungle"] == blue_jungle)
        & (df["blue_support"] == blue_support)
        & (df["red_jungle"] == red_jungle)
        & (df["red_support"] == red_support)
    ]
    if not exact.empty:
        row = exact.iloc[0]
        return int(row["games"]), float(row["blue_winrate"])

    flipped = df[
        (df["blue_jungle"] == red_jungle)
        & (df["blue_support"] == red_support)
        & (df["red_jungle"] == blue_jungle)
        & (df["red_support"] == blue_support)
    ]
    if not flipped.empty:
        row = flipped.iloc[0]
        return int(row["games"]), round(1.0 - float(row["blue_winrate"]), 4)

    return 0, None


def _rating(champion: str, attribute: str) -> float:
    champion_features, lookup_by_norm = _ensure_meraki_context()
    meraki_key = btd.resolve_champion_name(champion, champion_features, lookup_by_norm)
    if meraki_key is None:
        raise ValueError(f"Champion '{champion}' introuvable dans Meraki")

    ratings = champion_features[meraki_key]["attributeRatings"]
    value = ratings.get(attribute)
    if value is None:
        raise ValueError(f"Attribut Meraki '{attribute}' manquant pour {champion}")
    return float(value) / 3.0


def compute_fallback_duo_score(
    champion_1: str,
    champion_2: str,
    duo_type: DuoType,
) -> float:
    """Heuristique Meraki de repli — PAS une winrate mesurée sur games pro.

    Jungle-support : pathing/ganks — jungle control+mobility, support utility+control.
    Bot lane       : laning adc+sup — adc damage, support utility+toughness.

    Le score est centré ~0.50 avec une faible amplitude pour rester un signal faible.
    """
    if duo_type == "jungle_support":
        jungle, support = _assign_jungle_support_roles(champion_1, champion_2)
        jungle_setup = (_rating(jungle, "control") + _rating(jungle, "mobility")) / 2
        support_follow = (_rating(support, "utility") + _rating(support, "control")) / 2
        raw = (jungle_setup + support_follow) / 2
    elif duo_type == "bot_lane":
        adc, support = _assign_bot_lane_roles(champion_1, champion_2)
        adc_damage = _rating(adc, "damage")
        support_peel = (_rating(support, "utility") + _rating(support, "toughness")) / 2
        raw = (adc_damage + support_peel) / 2
    else:
        raise ValueError(f"duo_type inconnu: {duo_type}")

    # 0.45–0.55 : signal faible, comparable à une winrate légèrement décalée de 50 %
    return round(0.45 + raw * 0.10, 4)


def _meraki_positions_for(champion: str) -> set[str]:
    champion_features, lookup_by_norm = _ensure_meraki_context()
    meraki_key = btd.resolve_champion_name(champion, champion_features, lookup_by_norm)
    if meraki_key is None or _champion_positions is None:
        return set()
    return _champion_positions.get(meraki_key, set())


def _assign_jungle_support_roles(
    champion_1: str,
    champion_2: str,
) -> tuple[str, str]:
    c1_pos = _meraki_positions_for(champion_1)
    c2_pos = _meraki_positions_for(champion_2)

    c1_jng = "JUNGLE" in c1_pos
    c2_jng = "JUNGLE" in c2_pos
    c1_sup = "SUPPORT" in c1_pos
    c2_sup = "SUPPORT" in c2_pos

    if c1_jng and c2_sup:
        return champion_1, champion_2
    if c2_jng and c1_sup:
        return champion_2, champion_1
    return champion_1, champion_2


def _assign_bot_lane_roles(champion_1: str, champion_2: str) -> tuple[str, str]:
    c1_pos = _meraki_positions_for(champion_1)
    c2_pos = _meraki_positions_for(champion_2)

    c1_adc = "BOTTOM" in c1_pos
    c2_adc = "BOTTOM" in c2_pos
    c1_sup = "SUPPORT" in c1_pos
    c2_sup = "SUPPORT" in c2_pos

    if c1_adc and c2_sup:
        return champion_1, champion_2
    if c2_adc and c1_sup:
        return champion_2, champion_1
    return champion_1, champion_2


def get_duo_score(
    champion_1: str,
    champion_2: str,
    duo_type: DuoType,
    mode: Literal["mixed", "pro"] = "mixed",
) -> DuoScore:
    pair = normalize_duo_pair(champion_1, champion_2)
    games, measured_winrate = _lookup_measured_games(pair[0], pair[1], duo_type)

    if measured_winrate is not None:
        return DuoScore(
            score=round(measured_winrate, 4),
            is_fallback=False,
            games=games,
            champion_1=pair[0],
            champion_2=pair[1],
            duo_type=duo_type,
            insufficient_data=False,
        )

    if mode == "pro":
        return DuoScore(
            score=None,
            is_fallback=False,
            games=games,
            champion_1=pair[0],
            champion_2=pair[1],
            duo_type=duo_type,
            insufficient_data=True,
        )

    fallback_score = compute_fallback_duo_score(pair[0], pair[1], duo_type)
    return DuoScore(
        score=fallback_score,
        is_fallback=True,
        games=games,
        champion_1=pair[0],
        champion_2=pair[1],
        duo_type=duo_type,
        insufficient_data=False,
    )


def build_datasets(
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    players = load_player_rows(oracle_csv)
    jungle_support_records, bot_lane_records = build_duo_records(players)
    bot_matchup_records = build_bot_lane_matchup_records(players)
    js_matchup_records = build_jungle_support_matchup_records(players)
    jungle_support_df = aggregate_duos(jungle_support_records)
    bot_lane_df = aggregate_duos(bot_lane_records)
    bot_matchup_df = aggregate_bot_lane_matchups(bot_matchup_records)
    js_matchup_df = aggregate_jungle_support_matchups(js_matchup_records)
    return jungle_support_df, bot_lane_df, bot_matchup_df, js_matchup_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construit les datasets de synergie duo jungle-support et bot lane (Oracle's Elixir)."
    )
    parser.add_argument(
        "--oracle-csv",
        type=Path,
        default=DEFAULT_ORACLE_CSV,
        help="Chemin vers le CSV Oracle's Elixir",
    )
    parser.add_argument(
        "--min-games",
        type=int,
        default=SEUIL_MIN_GAMES,
        help="Seuil minimum de games pour considérer un duo fiable",
    )
    parser.add_argument("--verbose", action="store_true", help="Logs détaillés")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)

    global SEUIL_MIN_GAMES
    SEUIL_MIN_GAMES = args.min_games

    if not args.oracle_csv.exists():
        logging.error("Fichier Oracle introuvable: %s", args.oracle_csv)
        sys.exit(1)

    jungle_support_df, bot_lane_df, bot_matchup_df, js_matchup_df = build_datasets(args.oracle_csv)
    export_duo_table(jungle_support_df, DUO_JUNGLE_SUPPORT_CSV)
    export_duo_table(bot_lane_df, DUO_BOT_LANE_CSV)
    BOT_LANE_MATCHUP_CSV.parent.mkdir(parents=True, exist_ok=True)
    bot_matchup_df.to_csv(BOT_LANE_MATCHUP_CSV, index=False)
    logging.info("Exporté: %s (%d matchups uniques)", BOT_LANE_MATCHUP_CSV, len(bot_matchup_df))
    js_matchup_df.to_csv(JUNGLE_SUPPORT_MATCHUP_CSV, index=False)
    logging.info(
        "Exporté: %s (%d matchups uniques)",
        JUNGLE_SUPPORT_MATCHUP_CSV,
        len(js_matchup_df),
    )

    js_reliable, js_fallback = log_duo_coverage(jungle_support_df, "Jungle-support")
    bl_reliable, bl_fallback = log_duo_coverage(bot_lane_df, "Bot lane")
    bl_matchup_reliable, bl_matchup_fallback = log_duo_coverage(bot_matchup_df, "Bot lane matchup")
    js_matchup_reliable, js_matchup_fallback = log_duo_coverage(
        js_matchup_df, "Jungle-support matchup"
    )

    logging.info(
        "Total duos fiables: %d | Total duos fallback: %d | "
        "Matchups bot fiables: %d | Matchups js fiables: %d",
        js_reliable + bl_reliable,
        js_fallback + bl_fallback,
        bl_matchup_reliable,
        js_matchup_reliable,
    )

    reset_duo_cache()


if __name__ == "__main__":
    main()
