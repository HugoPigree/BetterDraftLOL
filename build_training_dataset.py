#!/usr/bin/env python3
"""Build a draft synergy training dataset from Oracle's Elixir and Meraki champion data."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import requests

MERAKI_URL = "http://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/champions.json"
ATTRIBUTE_COLUMNS = ["damage", "toughness", "control", "mobility", "utility"]
PICK_COLUMNS = ["pick1", "pick2", "pick3", "pick4", "pick5"]
DATA_DIR = Path("data")
DEFAULT_ORACLE_CSV = DATA_DIR / "2026_LoL_esports_match_data_from_OraclesElixir.csv"
DEFAULT_OUTPUT_CSV = DATA_DIR / "training_dataset.csv"
DEFAULT_MERAKI_CACHE = DATA_DIR / "meraki_champions.json"
DEFAULT_UNMAPPED_FILE = DATA_DIR / "unmapped_champions.txt"

# Mapping manuel Oracle's Elixir -> clé Meraki
NAME_MAPPING: dict[str, str] = {
    "Wukong": "MonkeyKing",
    "Monkey King": "MonkeyKing",
    "Nunu & Willump": "Nunu",
    "Nunu and Willump": "Nunu",
    "Renata Glasc": "Renata",
    "Dr. Mundo": "DrMundo",
    "Miss Fortune": "MissFortune",
    "Jarvan IV": "JarvanIV",
    "Twisted Fate": "TwistedFate",
    "Xin Zhao": "XinZhao",
    "Lee Sin": "LeeSin",
    "Master Yi": "MasterYi",
    "Aurelion Sol": "AurelionSol",
    "Cho'Gath": "Chogath",
    "Kai'Sa": "Kaisa",
    "Kha'Zix": "Khazix",
    "Rek'Sai": "RekSai",
    "Vel'Koz": "Velkoz",
    "Bel'Veth": "Belveth",
    "Kog'Maw": "KogMaw",
    "Tahm Kench": "TahmKench",
}


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def load_meraki_champions(url: str, cache_path: Path) -> dict[str, Any]:
    if cache_path.exists():
        logging.info("Chargement Meraki depuis le cache %s", cache_path)
        return json.loads(cache_path.read_text(encoding="utf-8"))

    logging.info("Téléchargement Meraki: %s", url)
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    champions = response.json()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(champions, indent=2), encoding="utf-8")
    logging.info("Cache Meraki sauvegardé dans %s", cache_path)
    return champions


def build_champion_feature_dict(champions: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    champion_features: dict[str, dict[str, Any]] = {}
    role_tags: set[str] = set()
    lookup_by_norm: dict[str, str] = {}

    for key, payload in champions.items():
        roles = payload.get("roles", [])
        ratings = payload.get("attributeRatings", {})
        champion_features[key] = {
            "roles": roles,
            "attributeRatings": {col: ratings.get(col) for col in ATTRIBUTE_COLUMNS},
        }
        role_tags.update(roles)
        lookup_by_norm[normalize_name(key)] = key
        display_name = payload.get("name", key)
        lookup_by_norm[normalize_name(display_name)] = key

    return champion_features, sorted(role_tags)


def resolve_champion_name(
    oracle_name: str,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
) -> str | None:
    if oracle_name in NAME_MAPPING:
        mapped = NAME_MAPPING[oracle_name]
        if mapped in champion_features:
            return mapped

    if oracle_name in champion_features:
        return oracle_name

    normalized = normalize_name(oracle_name)
    if normalized in lookup_by_norm:
        return lookup_by_norm[normalized]

    return None


def load_oracle_team_rows(oracle_csv: Path) -> pd.DataFrame:
    logging.info("Chargement Oracle's Elixir: %s", oracle_csv)
    df = pd.read_csv(oracle_csv, low_memory=False)
    team_rows = df[(df["datacompleteness"] == "complete") & (df["position"] == "team")].copy()
    logging.info("%d lignes équipe (complete)", len(team_rows))
    return team_rows


def encode_side(side: str) -> int | None:
    side_lower = str(side).strip().lower()
    if side_lower == "blue":
        return 0
    if side_lower == "red":
        return 1
    return None


def aggregate_team_features(
    picks: list[str],
    champion_features: dict[str, dict[str, Any]],
    role_tags: list[str],
) -> dict[str, float | int]:
    ratings_matrix = [
        [champion_features[pick]["attributeRatings"][attr] for attr in ATTRIBUTE_COLUMNS]
        for pick in picks
    ]
    ratings_df = pd.DataFrame(ratings_matrix, columns=ATTRIBUTE_COLUMNS)

    features: dict[str, float | int] = {}
    for attr in ATTRIBUTE_COLUMNS:
        series = ratings_df[attr]
        features[f"{attr}_sum"] = float(series.sum())
        features[f"{attr}_mean"] = float(series.mean())
        features[f"{attr}_std"] = float(series.std(ddof=0))

    role_counter = Counter()
    for pick in picks:
        role_counter.update(champion_features[pick]["roles"])

    for role in role_tags:
        features[f"role_{role}_count"] = int(role_counter.get(role, 0))

    return features


def build_dataset(
    team_rows: pd.DataFrame,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
    role_tags: list[str],
) -> tuple[pd.DataFrame, set[str], int]:
    rows: list[dict[str, Any]] = []
    unmapped_champions: set[str] = set()
    excluded_unmapped_rows = 0
    skipped_other_rows = 0

    for _, row in team_rows.iterrows():
        picks_raw = [row[col] for col in PICK_COLUMNS]
        if any(pd.isna(pick) or not str(pick).strip() for pick in picks_raw):
            skipped_other_rows += 1
            continue

        resolved_picks: list[str] = []
        row_unmapped: list[str] = []
        for pick in picks_raw:
            pick_name = str(pick).strip()
            meraki_key = resolve_champion_name(pick_name, champion_features, lookup_by_norm)
            if meraki_key is None:
                row_unmapped.append(pick_name)
            else:
                resolved_picks.append(meraki_key)

        if row_unmapped:
            unmapped_champions.update(row_unmapped)
            excluded_unmapped_rows += 1
            continue

        side_encoded = encode_side(row["side"])
        if side_encoded is None:
            skipped_other_rows += 1
            continue

        feature_row = aggregate_team_features(resolved_picks, champion_features, role_tags)
        feature_row["gameid"] = row["gameid"]
        feature_row["side"] = side_encoded
        feature_row["patch"] = row["patch"]
        feature_row["result"] = int(row["result"])
        rows.append(feature_row)

    dataset = pd.DataFrame(rows)
    logging.info(
        "Dataset construit: %d lignes (%d exclues pour champions non-mappés, %d ignorées pour autres raisons)",
        len(dataset),
        excluded_unmapped_rows,
        skipped_other_rows,
    )

    return dataset, unmapped_champions, excluded_unmapped_rows


def order_columns(dataset: pd.DataFrame, role_tags: list[str]) -> pd.DataFrame:
    attribute_cols: list[str] = []
    for attr in ATTRIBUTE_COLUMNS:
        attribute_cols.extend([f"{attr}_sum", f"{attr}_mean", f"{attr}_std"])

    role_cols = [f"role_{role}_count" for role in role_tags]
    ordered = ["gameid", "side", "patch", *attribute_cols, *role_cols, "result"]
    return dataset[ordered]


def write_unmapped_champions(unmapped_champions: set[str], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sorted_names = sorted(unmapped_champions)
    output_path.write_text("\n".join(sorted_names) + ("\n" if sorted_names else ""), encoding="utf-8")
    logging.info(
        "Champions uniques non-mappés: %d -> %s",
        len(unmapped_champions),
        output_path,
    )


def export_dataset(dataset: pd.DataFrame, output_csv: Path) -> Path:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output_csv, index=False)
    logging.info("Exporté: %s (%d lignes, %d colonnes)", output_csv, len(dataset), len(dataset.columns))
    return output_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construit un dataset d'entraînement draft synergy (Oracle + Meraki)."
    )
    parser.add_argument(
        "--oracle-csv",
        type=Path,
        default=DEFAULT_ORACLE_CSV,
        help="Chemin vers le CSV Oracle's Elixir",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=DEFAULT_OUTPUT_CSV,
        help="Chemin de sortie du dataset",
    )
    parser.add_argument(
        "--meraki-url",
        default=MERAKI_URL,
        help="URL du JSON Meraki champions",
    )
    parser.add_argument(
        "--meraki-cache",
        type=Path,
        default=DEFAULT_MERAKI_CACHE,
        help="Cache local du JSON Meraki",
    )
    parser.add_argument("--verbose", action="store_true", help="Logs détaillés")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)

    if not args.oracle_csv.exists():
        logging.error("Fichier Oracle introuvable: %s", args.oracle_csv)
        sys.exit(1)

    champions = load_meraki_champions(args.meraki_url, args.meraki_cache)
    champion_features, role_tags = build_champion_feature_dict(champions)
    lookup_by_norm = {
        normalize_name(key): key for key in champion_features
    }
    for key, payload in champions.items():
        lookup_by_norm[normalize_name(payload.get("name", key))] = key

    team_rows = load_oracle_team_rows(args.oracle_csv)
    dataset, unmapped_champions, excluded_unmapped_rows = build_dataset(
        team_rows, champion_features, lookup_by_norm, role_tags
    )
    dataset = order_columns(dataset, role_tags)
    export_dataset(dataset, args.output_csv)
    write_unmapped_champions(unmapped_champions, DEFAULT_UNMAPPED_FILE)
    logging.info("Lignes exclues pour champion(s) non-mappé(s) dans Meraki: %d", excluded_unmapped_rows)


if __name__ == "__main__":
    main()
