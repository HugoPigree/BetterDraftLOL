#!/usr/bin/env python3
"""Predict draft win probability from solo queue strength, synergy model, and side."""

from __future__ import annotations

import json
import logging
import math
import random
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

from build_training_dataset import (
    ATTRIBUTE_COLUMNS,
    DEFAULT_MERAKI_CACHE,
    MERAKI_URL,
    aggregate_team_features,
    build_champion_feature_dict,
    load_meraki_champions,
    normalize_name,
    resolve_champion_name,
)

# --- Poids configurables ---
WEIGHT_FORCE = 0.5
WEIGHT_SYNERGY = 0.4
WEIGHT_SIDE = 0.1
SIGMOID_SCALE = 2.0
CALIBRATION_FACTOR = 0.3
MODEL_AUC = 0.55
BLUE_SIDE_WINRATE: float | None = None
DEFAULT_WINRATE = 0.5

VALID_ROLES = {"TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"}

MODEL_PATH = Path("model/synergy_model.json")
FEATURES_ORDER_PATH = Path("model/features_order.json")
DEFAULT_ORACLE_CSV = Path("data/2026_LoL_esports_match_data_from_OraclesElixir.csv")
SOLOQ_DIR = Path("data/solo_queue")
SOLOQ_FILE_PATTERN = "soloq_winrates_euw_{patch}.csv"

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


@lru_cache(maxsize=1)
def get_meraki_context() -> tuple[dict[str, dict[str, Any]], list[str], dict[str, str]]:
    champions = load_meraki_champions(MERAKI_URL, DEFAULT_MERAKI_CACHE)
    champion_features, role_tags = build_champion_feature_dict(champions)
    lookup_by_norm = {normalize_name(key): key for key in champion_features}
    for key, payload in champions.items():
        lookup_by_norm[normalize_name(payload.get("name", key))] = key
    return champion_features, role_tags, lookup_by_norm


@lru_cache(maxsize=1)
def get_feature_order() -> list[str]:
    return json.loads(FEATURES_ORDER_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def get_synergy_model() -> xgb.XGBClassifier:
    model = xgb.XGBClassifier()
    model.load_model(MODEL_PATH)
    return model


def parse_patch(patch: str) -> str:
    return patch.strip()


def patch_to_float(patch: str) -> float:
    return float(parse_patch(patch))


def soloq_file_for_patch(patch: str) -> Path:
    path = SOLOQ_DIR / SOLOQ_FILE_PATTERN.format(patch=parse_patch(patch))
    if not path.exists():
        available = sorted(p.stem.replace("soloq_winrates_euw_", "") for p in SOLOQ_DIR.glob("soloq_winrates_euw_*.csv"))
        raise FileNotFoundError(
            f"Fichier solo queue introuvable pour le patch {patch}: {path}. "
            f"Patches disponibles: {', '.join(available) if available else 'aucun'}"
        )
    return path


def load_soloq_scores(patch: str) -> pd.DataFrame:
    path = soloq_file_for_patch(patch)
    df = pd.read_csv(path)
    logger.info("Solo queue chargé: %s (%d lignes)", path, len(df))
    return df


def compute_actual_blue_side_winrate(oracle_csv: Path = DEFAULT_ORACLE_CSV) -> float:
    """Calcule le winrate historique du côté blue sur les lignes équipe Oracle's Elixir."""
    df = pd.read_csv(oracle_csv, low_memory=False)
    team_rows = df[(df["datacompleteness"] == "complete") & (df["position"] == "team")]
    blue_rows = team_rows[team_rows["side"].str.lower() == "blue"]
    if blue_rows.empty:
        raise ValueError("Aucune ligne blue side trouvée dans Oracle's Elixir")

    winrate = float(blue_rows["result"].mean())
    logger.info(
        "Blue side winrate mesuré: %.2f%% (%d games blue / %d lignes équipe)",
        winrate * 100,
        len(blue_rows),
        len(team_rows),
    )
    return winrate


def initialize_blue_side_winrate(oracle_csv: Path = DEFAULT_ORACLE_CSV) -> float:
    global BLUE_SIDE_WINRATE
    winrate = compute_actual_blue_side_winrate(oracle_csv)
    BLUE_SIDE_WINRATE = winrate

    blue_bonus = winrate - 0.5
    red_bonus = (1.0 - winrate) - 0.5
    print(f"\n=== Side winrate mesuré (Oracle's Elixir) ===")
    print(f"Blue side winrate historique : {winrate:.2%}")
    print(f"Bonus side blue vs 50%       : {blue_bonus:+.4f}")
    print(f"Bonus side red vs 50%        : {red_bonus:+.4f}")
    return winrate


def get_side_bonuses() -> tuple[float, float]:
    if BLUE_SIDE_WINRATE is None:
        initialize_blue_side_winrate()
    blue_bonus = BLUE_SIDE_WINRATE - 0.5
    red_bonus = (1.0 - BLUE_SIDE_WINRATE) - 0.5
    return blue_bonus, red_bonus


def resolve_meraki_key(
    champion_name: str,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
) -> str | None:
    return resolve_champion_name(champion_name, champion_features, lookup_by_norm)


def resolve_soloq_champion_name(
    champion_name: str,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
) -> str | None:
    meraki_key = resolve_meraki_key(champion_name, champion_features, lookup_by_norm)
    if meraki_key is None:
        return None
    return meraki_key


def compute_force_score(
    team: list[dict[str, str]],
    soloq_df: pd.DataFrame,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
) -> tuple[float, list[dict[str, Any]], list[str]]:
    lookup = {
        (row.champion, row.role): float(row.winrate)
        for row in soloq_df.itertuples(index=False)
    }
    warnings: list[str] = []
    winrates: list[float] = []
    champions_detail: list[dict[str, Any]] = []

    for slot in team:
        champion = slot["champion"]
        role = slot["role"].upper()
        if role not in VALID_ROLES:
            warnings.append(f"Rôle invalide '{role}' pour {champion}, winrate par défaut 50%")
            winrate = DEFAULT_WINRATE
            winrates.append(winrate)
            champions_detail.append(
                {"champion": champion, "role": role, "winrate": round(winrate, 4)}
            )
            continue

        resolved = resolve_soloq_champion_name(champion, champion_features, lookup_by_norm)
        if resolved is None:
            warnings.append(f"Champion '{champion}' introuvable dans Meraki/solo queue, winrate par défaut 50%")
            winrate = DEFAULT_WINRATE
            winrates.append(winrate)
            champions_detail.append(
                {"champion": champion, "role": role, "winrate": round(winrate, 4)}
            )
            continue

        winrate = lookup.get((resolved, role))
        if winrate is None:
            warnings.append(
                f"Winrate solo queue introuvable pour {champion} ({resolved}) / {role}, winrate par défaut 50%"
            )
            winrate = DEFAULT_WINRATE
        else:
            winrate = float(winrate)

        winrates.append(winrate)
        champions_detail.append(
            {"champion": champion, "role": role, "winrate": round(winrate, 4)}
        )

    force_score = float(np.mean(winrates))
    return force_score, champions_detail, warnings


def resolve_team_picks(
    team: list[dict[str, str]],
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    resolved_picks: list[str] = []

    for slot in team:
        meraki_key = resolve_meraki_key(slot["champion"], champion_features, lookup_by_norm)
        if meraki_key is None:
            warnings.append(f"Champion '{slot['champion']}' introuvable dans Meraki pour la synergie")
            continue
        resolved_picks.append(meraki_key)

    return resolved_picks, warnings


def build_team_feature_vector(
    team: list[dict[str, str]],
    side: int,
    patch: str,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
    role_tags: list[str],
) -> tuple[dict[str, float | int], list[str], list[str]]:
    resolved_picks, warnings = resolve_team_picks(team, champion_features, lookup_by_norm)

    if len(resolved_picks) != 5:
        return {}, resolved_picks, warnings

    features = aggregate_team_features(resolved_picks, champion_features, role_tags)
    features["side"] = side
    features["patch"] = patch_to_float(patch)
    return features, resolved_picks, warnings


def empty_attribute_profile() -> dict[str, float]:
    return {f"{attr}_mean": 0.0 for attr in ATTRIBUTE_COLUMNS}


def extract_attribute_profile(feature_map: dict[str, float | int]) -> dict[str, float]:
    if not feature_map:
        return empty_attribute_profile()

    return {
        f"{attr}_mean": round(float(feature_map[f"{attr}_mean"]), 4)
        for attr in ATTRIBUTE_COLUMNS
    }


def extract_top_meraki_roles(
    resolved_picks: list[str],
    champion_features: dict[str, dict[str, Any]],
    top_n: int = 3,
) -> list[dict[str, Any]]:
    if len(resolved_picks) != 5:
        return []

    role_counter = Counter()
    for pick in resolved_picks:
        role_counter.update(champion_features[pick]["roles"])

    return [
        {"role": role, "count": count}
        for role, count in role_counter.most_common(top_n)
    ]


def build_team_enrichment(
    champion_features: dict[str, dict[str, Any]],
    feature_map: dict[str, float | int] | None = None,
    resolved_picks: list[str] | None = None,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    picks = resolved_picks or []
    attribute_profile = extract_attribute_profile(feature_map or {})
    meraki_roles = extract_top_meraki_roles(picks, champion_features)
    return attribute_profile, meraki_roles


def compute_attribute_differential(
    blue_profile: dict[str, float],
    red_profile: dict[str, float],
) -> dict[str, float]:
    return {
        f"{attr}_mean": round(blue_profile[f"{attr}_mean"] - red_profile[f"{attr}_mean"], 4)
        for attr in ATTRIBUTE_COLUMNS
    }


def vectorize_features(feature_map: dict[str, float | int], feature_order: list[str]) -> np.ndarray:
    return np.array([[feature_map[name] for name in feature_order]], dtype=float)


def calibrate_synergy_probability(
    raw_probability: float,
    factor: float = CALIBRATION_FACTOR,
) -> float:
    """Ramène la probabilité XGBoost vers 0.5 selon la fiabilité du modèle."""
    calibrated = 0.5 + (raw_probability - 0.5) * factor
    return float(min(max(calibrated, 0.0), 1.0))


def compute_synergy_score_raw(
    team: list[dict[str, str]],
    side: int,
    patch: str,
) -> tuple[float, list[str]]:
    champion_features, role_tags, lookup_by_norm = get_meraki_context()
    feature_order = get_feature_order()
    model = get_synergy_model()

    feature_map, resolved_picks, warnings = build_team_feature_vector(
        team, side, patch, champion_features, lookup_by_norm, role_tags
    )
    if not feature_map:
        warnings.append("Synergie indisponible, score par défaut 50%")
        return DEFAULT_WINRATE, warnings

    vector = vectorize_features(feature_map, feature_order)
    raw_score = float(model.predict_proba(vector)[0, 1])
    return raw_score, warnings


def compute_synergy_score(
    team: list[dict[str, str]],
    side: int,
    patch: str,
) -> tuple[float, float, list[str]]:
    raw_score, warnings = compute_synergy_score_raw(team, side, patch)
    calibrated_score = calibrate_synergy_probability(raw_score)
    return raw_score, calibrated_score, warnings


def combine_scores(
    force_blue: float,
    force_red: float,
    synergy_blue: float,
    synergy_red: float,
) -> tuple[float, float]:
    side_bonus_blue, side_bonus_red = get_side_bonuses()
    score_blue = (
        WEIGHT_FORCE * force_blue
        + WEIGHT_SYNERGY * synergy_blue
        + WEIGHT_SIDE * side_bonus_blue
    )
    score_red = (
        WEIGHT_FORCE * force_red
        + WEIGHT_SYNERGY * synergy_red
        + WEIGHT_SIDE * side_bonus_red
    )
    return score_blue, score_red


def score_diff_to_probabilities(score_blue: float, score_red: float) -> tuple[float, float]:
    diff = score_blue - score_red
    blue_prob = 1.0 / (1.0 + math.exp(-SIGMOID_SCALE * diff))
    red_prob = 1.0 - blue_prob
    return blue_prob, red_prob


def build_team_prediction_details(
    team: list[dict[str, str]],
    side: int,
    patch: str,
    soloq_df: pd.DataFrame,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
    role_tags: list[str],
) -> tuple[dict[str, Any], list[str]]:
    force_score, champions, warnings_force = compute_force_score(
        team, soloq_df, champion_features, lookup_by_norm
    )
    synergy_raw, synergy_cal, warnings_synergy = compute_synergy_score(team, side, patch)
    feature_map, resolved_picks, warnings_features = build_team_feature_vector(
        team, side, patch, champion_features, lookup_by_norm, role_tags
    )
    attribute_profile, meraki_roles = build_team_enrichment(
        champion_features,
        feature_map=feature_map,
        resolved_picks=resolved_picks,
    )

    side_bonus_blue, side_bonus_red = get_side_bonuses()
    side_bonus = side_bonus_blue if side == 0 else side_bonus_red
    score_final = (
        WEIGHT_FORCE * force_score
        + WEIGHT_SYNERGY * synergy_cal
        + WEIGHT_SIDE * side_bonus
    )

    warnings = warnings_force + warnings_synergy + warnings_features
    details = {
        "score_force": round(force_score, 4),
        "score_synergie_brut": round(synergy_raw, 4),
        "score_synergie": round(synergy_cal, 4),
        "score_final": round(score_final, 4),
        "champions": champions,
        "attribute_profile": attribute_profile,
        "meraki_roles": meraki_roles,
    }
    return details, warnings


def predict_draft(blue_team: list[dict[str, str]], red_team: list[dict[str, str]], patch: str) -> dict[str, Any]:
    if len(blue_team) != 5 or len(red_team) != 5:
        raise ValueError("Chaque équipe doit contenir exactement 5 champions")

    patch = parse_patch(patch)
    soloq_df = load_soloq_scores(patch)
    champion_features, role_tags, lookup_by_norm = get_meraki_context()

    blue_details, warnings_blue = build_team_prediction_details(
        blue_team, side=0, patch=patch, soloq_df=soloq_df,
        champion_features=champion_features, lookup_by_norm=lookup_by_norm, role_tags=role_tags,
    )
    red_details, warnings_red = build_team_prediction_details(
        red_team, side=1, patch=patch, soloq_df=soloq_df,
        champion_features=champion_features, lookup_by_norm=lookup_by_norm, role_tags=role_tags,
    )

    score_blue = blue_details["score_final"]
    score_red = red_details["score_final"]
    blue_prob, red_prob = score_diff_to_probabilities(score_blue, score_red)

    differential = compute_attribute_differential(
        blue_details["attribute_profile"],
        red_details["attribute_profile"],
    )

    return {
        "blue_win_probability": round(blue_prob, 4),
        "red_win_probability": round(red_prob, 4),
        "blue": blue_details,
        "red": red_details,
        "differential": differential,
        "warnings": warnings_blue + warnings_red,
    }


def build_random_team(
    candidates: list[tuple[str, str]],
    team_size: int = 5,
) -> list[dict[str, str]]:
    picks = random.sample(candidates, team_size)
    return [{"champion": champion, "role": role} for champion, role in picks]


def get_soloq_candidates(patch: str, min_games: int = 20) -> list[tuple[str, str]]:
    soloq_df = load_soloq_scores(patch)
    filtered = soloq_df[soloq_df["games"] >= min_games]
    candidates = [
        (row.champion, row.role)
        for row in filtered[["champion", "role"]].drop_duplicates().itertuples(index=False)
    ]
    if len(candidates) < 10:
        raise ValueError("Pas assez de couples champion/rôle pour générer des drafts aléatoires")
    return candidates


def test_random_drafts(n_drafts: int = 20, patch: str = "16.13") -> None:
    patch = parse_patch(patch)
    candidates = get_soloq_candidates(patch)
    champion_features, _, lookup_by_norm = get_meraki_context()
    soloq_df = load_soloq_scores(patch)

    print(f"\n=== Test sur {n_drafts} drafts aléatoires (patch {patch}) ===")
    print(
        f"{'#':>3}  {'Blue force':>10} {'B syn raw':>10} {'B syn cal':>10} "
        f"{'Red force':>10} {'R syn raw':>10} {'R syn cal':>10} {'Blue win':>9}"
    )

    blue_probs: list[float] = []

    for index in range(1, n_drafts + 1):
        blue_candidates = candidates
        red_candidates = [item for item in candidates]
        blue_team = build_random_team(blue_candidates)
        blue_champions = {slot["champion"] for slot in blue_team}
        red_pool = [item for item in red_candidates if item[0] not in blue_champions]
        if len(red_pool) < 5:
            red_pool = red_candidates
        red_team = build_random_team(red_pool)

        force_blue, _, _ = compute_force_score(blue_team, soloq_df, champion_features, lookup_by_norm)
        force_red, _, _ = compute_force_score(red_team, soloq_df, champion_features, lookup_by_norm)
        syn_blue_raw, syn_blue_cal, _ = compute_synergy_score(blue_team, side=0, patch=patch)
        syn_red_raw, syn_red_cal, _ = compute_synergy_score(red_team, side=1, patch=patch)
        score_blue, score_red = combine_scores(force_blue, force_red, syn_blue_cal, syn_red_cal)
        blue_prob, _ = score_diff_to_probabilities(score_blue, score_red)
        blue_probs.append(blue_prob)

        print(
            f"{index:>3}  {force_blue:10.4f} {syn_blue_raw:10.4f} {syn_blue_cal:10.4f} "
            f"{force_red:10.4f} {syn_red_raw:10.4f} {syn_red_cal:10.4f} {blue_prob:9.2%}"
        )

    mean_prob = float(np.mean(blue_probs))
    std_prob = float(np.std(blue_probs))
    min_prob = float(np.min(blue_probs))
    max_prob = float(np.max(blue_probs))

    print("\n=== Synthèse ===")
    print(f"Moyenne blue_win_probability : {mean_prob:.2%}")
    print(f"Écart-type blue_win_probability : {std_prob:.2%}")
    print(f"Min / Max blue_win_probability : {min_prob:.2%} / {max_prob:.2%}")
    print(f"Blue side winrate mesuré       : {BLUE_SIDE_WINRATE:.2%}")
    print(f"Calibration synergy factor     : {CALIBRATION_FACTOR} (AUC modèle ~{MODEL_AUC})")
    print(f"Sigmoid scale                  : {SIGMOID_SCALE}")


def print_prediction(result: dict[str, Any]) -> None:
    print("\n=== Prédiction draft ===")
    print(f"Blue win probability: {result['blue_win_probability']:.2%}")
    print(f"Red win probability:  {result['red_win_probability']:.2%}")
    print("\nBlue:")
    for key, value in result["blue"].items():
        print(f"  {key}: {value:.4f}")
    print("\nRed:")
    for key, value in result["red"].items():
        print(f"  {key}: {value:.4f}")
    if result["warnings"]:
        print("\nWarnings:")
        for warning in result["warnings"]:
            print(f"  - {warning}")


if __name__ == "__main__":
    setup_logging()
    initialize_blue_side_winrate()

    example_blue = [
        {"champion": "Gnar", "role": "TOP"},
        {"champion": "Xin Zhao", "role": "JUNGLE"},
        {"champion": "Ahri", "role": "MIDDLE"},
        {"champion": "Corki", "role": "BOTTOM"},
        {"champion": "Leona", "role": "UTILITY"},
    ]
    example_red = [
        {"champion": "Renekton", "role": "TOP"},
        {"champion": "Graves", "role": "JUNGLE"},
        {"champion": "Syndra", "role": "MIDDLE"},
        {"champion": "Jhin", "role": "BOTTOM"},
        {"champion": "Nautilus", "role": "UTILITY"},
    ]

    prediction = predict_draft(example_blue, example_red, patch="16.13")
    print_prediction(prediction)
    test_random_drafts(n_drafts=20, patch="16.13")
