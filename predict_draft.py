#!/usr/bin/env python3
"""Predict draft win probability from solo queue strength, synergy model, and side.

IMPORTANT — Ne pas importer champion_profile_stats dans ce module.
Les stats in-game Oracle (golddiffat15, dpm, csdiffat15) ne doivent jamais entrer
dans le calcul du score de victoire (fuite de données). Texte descriptif uniquement
via suggest_draft / api.enrich_predict_response_descriptions.
"""

from __future__ import annotations

import json
import logging
import math
import random
from collections import Counter
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import xgboost as xgb

import build_training_dataset as btd
from build_duo_dataset import (
    DuoScore,
    get_duo_score,
    lookup_bot_lane_matchup,
    lookup_jungle_support_matchup,
)
from build_duo_dataset import SEUIL_MIN_GAMES as DUO_MIN_GAMES
from pro_force import (
    compute_pro_winrate_by_champion,
    pro_meta_score,
    reset_pro_force_state,
)
from build_training_dataset import (
    ATTRIBUTE_COLUMNS,
    DEFAULT_MERAKI_CACHE,
    MERAKI_URL,
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
NEUTRAL_SYNERGY_ATTRIBUTE = 1.5
PredictionMode = Literal["mixed", "pro"]

VALID_ROLES = {"TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"}
ROLE_JUNGLE = "JUNGLE"
ROLE_BOTTOM = "BOTTOM"
ROLE_SUPPORT = "UTILITY"

MODEL_PATH = Path("model/synergy_model.json")
FEATURES_ORDER_PATH = Path("model/features_order.json")
DEFAULT_ORACLE_CSV = Path("data/2026_LoL_esports_match_data_from_OraclesElixir.csv")
SOLOQ_DIR = Path("data/solo_queue")
SOLOQ_FILE_PATTERN = "soloq_winrates_euw_{patch}.csv"

logger = logging.getLogger(__name__)

MerakiContext = tuple[dict[str, dict[str, Any]], list[str], dict[str, str]]
_meraki_context: MerakiContext | None = None
_feature_order: list[str] | None = None
_synergy_model: xgb.XGBClassifier | None = None
_soloq_cache: dict[str, pd.DataFrame] = {}


def reset_predict_state() -> None:
    """Vide le cache d'inférence. Appelé au startup API (incl. uvicorn --reload)."""
    global BLUE_SIDE_WINRATE, _meraki_context, _feature_order, _synergy_model, _soloq_cache
    BLUE_SIDE_WINRATE = None
    _meraki_context = None
    _feature_order = None
    _synergy_model = None
    _soloq_cache = {}
    reset_pro_force_state()


def _parse_meraki_features(
    raw: object,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    if not isinstance(raw, tuple):
        raise ValueError(
            f"build_champion_feature_dict a retourné {type(raw).__name__}, tuple de 2 éléments attendu"
        )
    if len(raw) != 2:
        raise ValueError(
            f"build_champion_feature_dict a retourné {len(raw)} valeurs, 2 attendues "
            f"(champion_features, role_tags)"
        )
    champion_features, role_tags = raw
    return champion_features, role_tags


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def get_meraki_context() -> MerakiContext:
    global _meraki_context
    if _meraki_context is not None:
        return _meraki_context

    champions = btd.load_meraki_champions(MERAKI_URL, DEFAULT_MERAKI_CACHE)
    champion_features, role_tags = _parse_meraki_features(
        btd.build_champion_feature_dict(champions)
    )
    lookup_by_norm = {normalize_name(key): key for key in champion_features}
    for key, payload in champions.items():
        lookup_by_norm[normalize_name(payload.get("name", key))] = key
    _meraki_context = (champion_features, role_tags, lookup_by_norm)
    return _meraki_context


def get_feature_order() -> list[str]:
    global _feature_order
    if _feature_order is None:
        _feature_order = json.loads(FEATURES_ORDER_PATH.read_text(encoding="utf-8"))
    return _feature_order


def get_synergy_model() -> xgb.XGBClassifier:
    global _synergy_model
    if _synergy_model is None:
        model = xgb.XGBClassifier()
        model.load_model(MODEL_PATH)
        _synergy_model = model
    return _synergy_model


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
    patch_key = parse_patch(patch)
    cached = _soloq_cache.get(patch_key)
    if cached is not None:
        return cached

    path = soloq_file_for_patch(patch_key)
    df = pd.read_csv(path)
    _soloq_cache[patch_key] = df
    logger.info("Solo queue chargé: %s (%d lignes)", path, len(df))
    return df


def warmup_predict_caches(patch: str) -> None:
    """Précharge modèle, Meraki et soloQ avant une boucle de prédictions."""
    get_meraki_context()
    get_feature_order()
    get_synergy_model()
    load_soloq_scores(patch)
    if BLUE_SIDE_WINRATE is None:
        initialize_blue_side_winrate()


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


def build_soloq_lookup(soloq_df: pd.DataFrame) -> dict[tuple[str, str], float]:
    required = {"champion", "role", "winrate"}
    missing = required.difference(soloq_df.columns)
    if missing:
        raise ValueError(
            f"CSV solo queue invalide, colonnes manquantes: {', '.join(sorted(missing))}"
        )

    lookup: dict[tuple[str, str], float] = {}
    for champion, role, winrate in zip(
        soloq_df["champion"],
        soloq_df["role"],
        soloq_df["winrate"],
        strict=True,
    ):
        lookup[(str(champion), str(role))] = float(winrate)
    return lookup


def compute_force_score(
    team: list[dict[str, str]],
    soloq_df: pd.DataFrame,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
) -> tuple[float, list[dict[str, Any]], list[str]]:
    lookup = build_soloq_lookup(soloq_df)
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


def compute_pro_force_score(
    team: list[dict[str, str]],
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
) -> tuple[float | None, list[dict[str, Any]], list[str], int]:
    """Force score from pro Oracle data: meta volume + shrunk WR, not raw winrates."""
    warnings: list[str] = []
    meta_scores: list[float] = []
    champions_detail: list[dict[str, Any]] = []

    for slot in team:
        champion = slot["champion"]
        role = slot["role"].upper()
        if role not in VALID_ROLES:
            warnings.append(f"Rôle invalide '{role}' pour {champion}")
            champions_detail.append(
                {
                    "champion": champion,
                    "role": role,
                    "winrate": None,
                    "games": None,
                    "meta_score": None,
                    "role_fitness": None,
                    "insufficient_data": True,
                    "data_source": "pro",
                }
            )
            continue

        meta_entry = pro_meta_score(champion, role, champion_features, lookup_by_norm)
        if meta_entry is None:
            warnings.append(
                f"Pas assez de données pro pour {champion} à ce rôle ({role})"
            )
            champions_detail.append(
                {
                    "champion": champion,
                    "role": role,
                    "winrate": None,
                    "games": None,
                    "meta_score": None,
                    "role_fitness": None,
                    "insufficient_data": True,
                    "data_source": "pro",
                }
            )
            continue

        meta_score, games, shrunk_wr, fitness, resolved_name = meta_entry
        raw_entry = compute_pro_winrate_by_champion(
            champion, role, champion_features, lookup_by_norm
        )
        raw_wr = raw_entry[0] if raw_entry else shrunk_wr

        meta_scores.append(meta_score)
        champions_detail.append(
            {
                "champion": champion,
                "role": role,
                "winrate": round(raw_wr, 4),
                "shrunk_winrate": round(shrunk_wr, 4),
                "meta_score": round(meta_score, 4),
                "role_fitness": round(fitness, 4),
                "games": games,
                "insufficient_data": False,
                "data_source": "pro",
            }
        )
        if fitness < 0.5:
            warnings.append(
                f"{resolved_name} est surtout joué ailleurs en pro "
                f"(adéquation rôle {role}: {fitness:.0%})"
            )

    if not meta_scores:
        warnings.append(
            "Score de force indisponible : aucun pick avec assez de données pro sur les patchs disponibles"
        )
        return None, champions_detail, warnings, 0

    valid_count = len(meta_scores)
    if valid_count < 5:
        warnings.append(
            f"Score de force partiel : {valid_count}/5 picks avec données pro suffisantes"
        )

    force_score = float(np.mean(meta_scores))
    return force_score, champions_detail, warnings, valid_count


def _compute_weighted_team_score(
    force_score: float | None,
    synergy_cal: float,
    side_bonus: float,
    mode: PredictionMode,
) -> float:
    if force_score is None and mode == "pro":
        total = WEIGHT_SYNERGY + WEIGHT_SIDE
        return (WEIGHT_SYNERGY * synergy_cal + WEIGHT_SIDE * side_bonus) / total
    force_component = force_score if force_score is not None else DEFAULT_WINRATE
    return (
        WEIGHT_FORCE * force_component
        + WEIGHT_SYNERGY * synergy_cal
        + WEIGHT_SIDE * side_bonus
    )


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

    features = btd.aggregate_team_features(resolved_picks, champion_features, role_tags)
    features["side"] = side
    features["patch"] = patch_to_float(patch)
    return features, resolved_picks, warnings


def aggregate_team_features_ablated(
    picks: list[str],
    ablated_index: int,
    champion_features: dict[str, dict[str, Any]],
    role_tags: list[str],
) -> dict[str, float | int]:
    """Agrège les features en neutralisant un champion (attributs neutres, rôles exclus)."""
    ratings_matrix: list[list[float]] = []
    for index, pick in enumerate(picks):
        if index == ablated_index:
            ratings_matrix.append([NEUTRAL_SYNERGY_ATTRIBUTE] * len(ATTRIBUTE_COLUMNS))
        else:
            ratings_matrix.append(
                [champion_features[pick]["attributeRatings"][attr] for attr in ATTRIBUTE_COLUMNS]
            )

    ratings_df = pd.DataFrame(ratings_matrix, columns=ATTRIBUTE_COLUMNS)
    features: dict[str, float | int] = {}
    for attr in ATTRIBUTE_COLUMNS:
        series = ratings_df[attr]
        features[f"{attr}_sum"] = float(series.sum())
        features[f"{attr}_mean"] = float(series.mean())
        features[f"{attr}_std"] = float(series.std(ddof=0))

    role_counter = Counter()
    for index, pick in enumerate(picks):
        if index != ablated_index:
            role_counter.update(champion_features[pick]["roles"])

    for role in role_tags:
        features[f"role_{role}_count"] = int(role_counter.get(role, 0))

    return features


def compute_synergy_score_ablated(
    team: list[dict[str, str]],
    ablated_index: int,
    side: int,
    patch: str,
) -> float:
    """Score de synergie calibré avec un champion neutralisé (ablation)."""
    champion_features, role_tags, lookup_by_norm = get_meraki_context()
    feature_order = get_feature_order()
    model = get_synergy_model()

    resolved_picks, _ = resolve_team_picks(team, champion_features, lookup_by_norm)
    if len(resolved_picks) != 5:
        return DEFAULT_WINRATE

    feature_map = aggregate_team_features_ablated(
        resolved_picks, ablated_index, champion_features, role_tags
    )
    feature_map["side"] = side
    feature_map["patch"] = patch_to_float(patch)
    vector = vectorize_features(feature_map, feature_order)
    raw_score = float(model.predict_proba(vector)[0, 1])
    return calibrate_synergy_probability(raw_score)


def compute_synergy_contributions(
    team: list[dict[str, str]],
    side: int,
    patch: str,
    full_synergy_cal: float,
) -> dict[str, Any]:
    """Estime la contribution marginale de chaque champion via ablation."""
    contributions: list[dict[str, Any]] = []
    for index in range(len(team)):
        ablated_score = compute_synergy_score_ablated(team, index, side, patch)
        marginal_points = round((full_synergy_cal - ablated_score) * 100, 2)
        contributions.append(
            {
                "champion": team[index]["champion"],
                "role": team[index]["role"].upper(),
                "marginal_points": marginal_points,
            }
        )

    top = max(contributions, key=lambda entry: entry["marginal_points"])
    least = min(contributions, key=lambda entry: entry["marginal_points"])
    return {
        "contributions": contributions,
        "top_contributor": top,
        "least_contributor": least,
    }


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
    soloq_df: pd.DataFrame | None,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
    role_tags: list[str],
    mode: PredictionMode = "mixed",
) -> tuple[dict[str, Any], list[str]]:
    force_partial = False
    if mode == "pro":
        force_score, champions, warnings_force, valid_count = compute_pro_force_score(
            team, champion_features, lookup_by_norm
        )
        force_partial = valid_count < 5
    else:
        force_score, champions, warnings_force = compute_force_score(
            team, soloq_df, champion_features, lookup_by_norm  # type: ignore[arg-type]
        )

    synergy_raw, synergy_cal, warnings_synergy = compute_synergy_score(team, side, patch)
    synergy_insight = compute_synergy_contributions(team, side, patch, synergy_cal)
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
    score_final = _compute_weighted_team_score(force_score, synergy_cal, side_bonus, mode)

    warnings = warnings_force + warnings_synergy + warnings_features
    details = {
        "score_force": round(force_score, 4) if force_score is not None else None,
        "score_synergie_brut": round(synergy_raw, 4),
        "score_synergie": round(synergy_cal, 4),
        "score_final": round(score_final, 4),
        "champions": champions,
        "attribute_profile": attribute_profile,
        "meraki_roles": meraki_roles,
        "force_partial": force_partial if mode == "pro" else False,
        "synergy_insight": synergy_insight,
    }
    return details, warnings


def champion_for_role(team: list[dict[str, str]], role: str) -> str | None:
    role_upper = role.upper()
    for slot in team:
        if slot["role"].upper() == role_upper:
            return slot["champion"]
    return None


def duo_score_to_payload(
    duo_score: DuoScore,
    champions: list[str],
) -> dict[str, Any]:
    return {
        "champions": champions,
        "score": duo_score.score,
        "games": duo_score.games,
        "is_fallback": duo_score.is_fallback,
        "insufficient_data": duo_score.insufficient_data,
    }


def _empty_duo_payload(
    champions: list[str | None],
    mode: PredictionMode,
    *,
    missing_role: bool = False,
) -> dict[str, Any]:
    if mode == "pro":
        return {
            "champions": [c for c in champions if c],
            "score": None,
            "games": 0,
            "is_fallback": False,
            "insufficient_data": True,
        }
    return {
        "champions": [c for c in champions if c],
        "score": DEFAULT_WINRATE,
        "games": 0,
        "is_fallback": True,
        "insufficient_data": missing_role,
    }


def build_team_duo_synergies(
    team: list[dict[str, str]],
    mode: PredictionMode = "mixed",
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    jungle = champion_for_role(team, ROLE_JUNGLE)
    support = champion_for_role(team, ROLE_SUPPORT)
    adc = champion_for_role(team, ROLE_BOTTOM)

    if jungle is None:
        warnings.append("Jungle introuvable dans la draft, synergie jungle-support indisponible")
    if support is None:
        warnings.append("Support introuvable dans la draft, synergies duo indisponibles")
    if adc is None:
        warnings.append("ADC introuvable dans la draft, synergie bot lane indisponible")

    if jungle and support:
        js_score = get_duo_score(jungle, support, "jungle_support", mode=mode)
        duo_jungle_support = duo_score_to_payload(js_score, [jungle, support])
    else:
        duo_jungle_support = _empty_duo_payload([jungle, support], mode, missing_role=True)

    if adc and support:
        bl_score = get_duo_score(adc, support, "bot_lane", mode=mode)
        duo_bot_lane = duo_score_to_payload(bl_score, [adc, support])
    else:
        duo_bot_lane = _empty_duo_payload([adc, support], mode, missing_role=True)

    return {
        "duo_jungle_support": duo_jungle_support,
        "duo_bot_lane": duo_bot_lane,
    }, warnings


def compute_duo_advantage(blue_score: float, red_score: float) -> dict[str, Any]:
    difference = round(blue_score - red_score, 4)
    if difference > 0:
        stronger_side = "blue"
    elif difference < 0:
        stronger_side = "red"
    else:
        stronger_side = "even"
    return {
        "stronger_side": stronger_side,
        "difference": abs(difference),
    }


def _duo_payload_insufficient(duo: dict[str, Any]) -> bool:
    return bool(duo.get("insufficient_data")) or duo.get("score") is None


def compute_internal_duo_advantage(
    blue_duo: dict[str, Any],
    red_duo: dict[str, Any],
    mode: PredictionMode = "mixed",
) -> dict[str, Any]:
    """Compare les synergies duo internes blue vs red, côté par côté en mode pro."""
    blue_insuf = _duo_payload_insufficient(blue_duo)
    red_insuf = _duo_payload_insufficient(red_duo)
    insufficient_sides: list[str] = []
    if blue_insuf:
        insufficient_sides.append("blue")
    if red_insuf:
        insufficient_sides.append("red")

    if mode == "pro" and (blue_insuf or red_insuf):
        if blue_insuf and red_insuf:
            message = "Comparaison impossible : données pro insuffisantes des deux côtés"
        elif blue_insuf:
            message = "Comparaison impossible : données pro insuffisantes côté Blue"
        else:
            message = "Comparaison impossible : données pro insuffisantes côté Red"
        return {
            "stronger_side": "even",
            "difference": 0.0,
            "insufficient_data": True,
            "comparison_message": message,
            "insufficient_sides": insufficient_sides,
        }

    if blue_insuf or red_insuf:
        return {
            "stronger_side": "even",
            "difference": 0.0,
            "insufficient_data": True,
            "comparison_message": None,
            "insufficient_sides": insufficient_sides,
        }

    adv = compute_duo_advantage(float(blue_duo["score"]), float(red_duo["score"]))
    return {
        **adv,
        "insufficient_data": False,
        "comparison_message": None,
        "insufficient_sides": [],
    }


def compute_matchup_advantage(
    blue_win_probability: float | None,
    *,
    insufficient_data: bool = False,
) -> dict[str, Any]:
    if insufficient_data or blue_win_probability is None:
        return {
            "stronger_side": "even",
            "difference": 0.0,
            "insufficient_data": True,
        }

    difference = round(blue_win_probability - 0.5, 4)
    if difference > 0:
        stronger_side = "blue"
    elif difference < 0:
        stronger_side = "red"
    else:
        stronger_side = "even"
    return {
        "stronger_side": stronger_side,
        "difference": abs(difference),
        "insufficient_data": False,
    }


def get_role_winrate(
    champion: str,
    role: str,
    soloq_lookup: dict[tuple[str, str], float],
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
) -> float:
    resolved = resolve_soloq_champion_name(champion, champion_features, lookup_by_norm)
    if resolved is None:
        return DEFAULT_WINRATE
    return soloq_lookup.get((resolved, role), DEFAULT_WINRATE)


def compute_soloq_bot_lane_matchup(
    blue_adc: str,
    blue_sup: str,
    red_adc: str,
    red_sup: str,
    soloq_lookup: dict[tuple[str, str], float],
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
    blue_duo_score: float,
    red_duo_score: float,
) -> float:
    """Estime le 2v2 bot lane via soloQ (lane + counters + synergie interne)."""
    blue_adc_wr = get_role_winrate(
        blue_adc, ROLE_BOTTOM, soloq_lookup, champion_features, lookup_by_norm
    )
    blue_sup_wr = get_role_winrate(
        blue_sup, ROLE_SUPPORT, soloq_lookup, champion_features, lookup_by_norm
    )
    red_adc_wr = get_role_winrate(
        red_adc, ROLE_BOTTOM, soloq_lookup, champion_features, lookup_by_norm
    )
    red_sup_wr = get_role_winrate(
        red_sup, ROLE_SUPPORT, soloq_lookup, champion_features, lookup_by_norm
    )

    lane_diff = ((blue_adc_wr + blue_sup_wr) / 2) - ((red_adc_wr + red_sup_wr) / 2)
    counter_diff = 0.5 * (blue_adc_wr - red_adc_wr) + 0.5 * (blue_sup_wr - red_sup_wr)
    synergy_diff = blue_duo_score - red_duo_score
    combined = 0.5 * lane_diff + 0.35 * counter_diff + 0.15 * synergy_diff
    return round(min(max(0.5 + combined, 0.32), 0.68), 4)


def compute_soloq_jungle_support_matchup(
    blue_jungle: str,
    blue_support: str,
    red_jungle: str,
    red_support: str,
    soloq_lookup: dict[tuple[str, str], float],
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
    blue_duo_score: float,
    red_duo_score: float,
) -> float:
    """Estime le 2v2 jungle-support via soloQ (impact map + counters + synergie interne)."""
    blue_jng_wr = get_role_winrate(
        blue_jungle, ROLE_JUNGLE, soloq_lookup, champion_features, lookup_by_norm
    )
    blue_sup_wr = get_role_winrate(
        blue_support, ROLE_SUPPORT, soloq_lookup, champion_features, lookup_by_norm
    )
    red_jng_wr = get_role_winrate(
        red_jungle, ROLE_JUNGLE, soloq_lookup, champion_features, lookup_by_norm
    )
    red_sup_wr = get_role_winrate(
        red_support, ROLE_SUPPORT, soloq_lookup, champion_features, lookup_by_norm
    )

    duo_diff = ((blue_jng_wr + blue_sup_wr) / 2) - ((red_jng_wr + red_sup_wr) / 2)
    counter_diff = 0.5 * (blue_jng_wr - red_jng_wr) + 0.5 * (blue_sup_wr - red_sup_wr)
    synergy_diff = blue_duo_score - red_duo_score
    combined = 0.5 * duo_diff + 0.35 * counter_diff + 0.15 * synergy_diff
    return round(min(max(0.5 + combined, 0.32), 0.68), 4)


def _build_duo_matchup_result(
    blue_first: str | None,
    blue_second: str | None,
    red_first: str | None,
    red_second: str | None,
    fallback_prob: float,
    games: int,
    measured: float | None,
    mode: PredictionMode = "mixed",
) -> dict[str, Any]:
    empty_matchup = {
        "blue_champions": [c for c in (blue_first, blue_second) if c],
        "red_champions": [c for c in (red_first, red_second) if c],
        "blue_win_probability": None if mode == "pro" else DEFAULT_WINRATE,
        "games": 0,
        "is_fallback": mode != "pro",
        "method": "measured" if mode == "pro" else "soloq_composite",
        "insufficient_data": mode == "pro",
    }
    if not all([blue_first, blue_second, red_first, red_second]):
        return empty_matchup

    if mode == "pro":
        if measured is not None and games >= DUO_MIN_GAMES:
            return {
                "blue_champions": [blue_first, blue_second],
                "red_champions": [red_first, red_second],
                "blue_win_probability": round(measured, 4),
                "games": games,
                "is_fallback": False,
                "method": "measured",
                "insufficient_data": False,
            }
        return {
            "blue_champions": [blue_first, blue_second],
            "red_champions": [red_first, red_second],
            "blue_win_probability": None,
            "games": games,
            "is_fallback": False,
            "method": "measured",
            "insufficient_data": True,
        }

    if measured is not None and games >= DUO_MIN_GAMES:
        return {
            "blue_champions": [blue_first, blue_second],
            "red_champions": [red_first, red_second],
            "blue_win_probability": round(measured, 4),
            "games": games,
            "is_fallback": False,
            "method": "measured",
            "insufficient_data": False,
        }

    if measured is not None and games > 0:
        weight = games / DUO_MIN_GAMES
        blended = round(
            0.5 + (measured - 0.5) * weight + (fallback_prob - 0.5) * (1 - weight),
            4,
        )
        return {
            "blue_champions": [blue_first, blue_second],
            "red_champions": [red_first, red_second],
            "blue_win_probability": blended,
            "games": games,
            "is_fallback": True,
            "method": "blended",
            "insufficient_data": False,
        }

    return {
        "blue_champions": [blue_first, blue_second],
        "red_champions": [red_first, red_second],
        "blue_win_probability": fallback_prob,
        "games": games,
        "is_fallback": True,
        "method": "soloq_composite",
        "insufficient_data": False,
    }


def _duo_score_for_matchup(duo_payload: dict[str, Any]) -> float:
    score = duo_payload.get("score")
    if score is None:
        return DEFAULT_WINRATE
    return float(score)


def build_bot_lane_matchup(
    blue_team: list[dict[str, str]],
    red_team: list[dict[str, str]],
    soloq_df: pd.DataFrame | None,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
    blue_duo_payload: dict[str, Any],
    red_duo_payload: dict[str, Any],
    mode: PredictionMode = "mixed",
) -> dict[str, Any]:
    blue_adc = champion_for_role(blue_team, ROLE_BOTTOM)
    blue_sup = champion_for_role(blue_team, ROLE_SUPPORT)
    red_adc = champion_for_role(red_team, ROLE_BOTTOM)
    red_sup = champion_for_role(red_team, ROLE_SUPPORT)

    games, measured = (
        lookup_bot_lane_matchup(blue_adc, blue_sup, red_adc, red_sup)
        if all([blue_adc, blue_sup, red_adc, red_sup])
        else (0, None)
    )

    if mode == "pro":
        return _build_duo_matchup_result(
            blue_adc, blue_sup, red_adc, red_sup, DEFAULT_WINRATE, games, measured, mode=mode
        )

    if not all([blue_adc, blue_sup, red_adc, red_sup]):
        return _build_duo_matchup_result(
            blue_adc, blue_sup, red_adc, red_sup, DEFAULT_WINRATE, 0, None, mode=mode
        )

    soloq_lookup = build_soloq_lookup(soloq_df)  # type: ignore[arg-type]
    fallback_prob = compute_soloq_bot_lane_matchup(
        blue_adc,
        blue_sup,
        red_adc,
        red_sup,
        soloq_lookup,
        champion_features,
        lookup_by_norm,
        _duo_score_for_matchup(blue_duo_payload),
        _duo_score_for_matchup(red_duo_payload),
    )

    return _build_duo_matchup_result(
        blue_adc, blue_sup, red_adc, red_sup, fallback_prob, games, measured, mode=mode
    )


def build_jungle_support_matchup(
    blue_team: list[dict[str, str]],
    red_team: list[dict[str, str]],
    soloq_df: pd.DataFrame | None,
    champion_features: dict[str, dict[str, Any]],
    lookup_by_norm: dict[str, str],
    blue_duo_payload: dict[str, Any],
    red_duo_payload: dict[str, Any],
    mode: PredictionMode = "mixed",
) -> dict[str, Any]:
    blue_jungle = champion_for_role(blue_team, ROLE_JUNGLE)
    blue_sup = champion_for_role(blue_team, ROLE_SUPPORT)
    red_jungle = champion_for_role(red_team, ROLE_JUNGLE)
    red_sup = champion_for_role(red_team, ROLE_SUPPORT)

    games, measured = (
        lookup_jungle_support_matchup(blue_jungle, blue_sup, red_jungle, red_sup)
        if all([blue_jungle, blue_sup, red_jungle, red_sup])
        else (0, None)
    )

    if mode == "pro":
        return _build_duo_matchup_result(
            blue_jungle, blue_sup, red_jungle, red_sup, DEFAULT_WINRATE, games, measured, mode=mode
        )

    if not all([blue_jungle, blue_sup, red_jungle, red_sup]):
        return _build_duo_matchup_result(
            blue_jungle, blue_sup, red_jungle, red_sup, DEFAULT_WINRATE, 0, None, mode=mode
        )

    soloq_lookup = build_soloq_lookup(soloq_df)  # type: ignore[arg-type]
    fallback_prob = compute_soloq_jungle_support_matchup(
        blue_jungle,
        blue_sup,
        red_jungle,
        red_sup,
        soloq_lookup,
        champion_features,
        lookup_by_norm,
        _duo_score_for_matchup(blue_duo_payload),
        _duo_score_for_matchup(red_duo_payload),
    )

    return _build_duo_matchup_result(
        blue_jungle, blue_sup, red_jungle, red_sup, fallback_prob, games, measured, mode=mode
    )


def build_duo_differential(
    bot_lane_matchup: dict[str, Any],
    jungle_support_matchup: dict[str, Any],
    blue_duos: dict[str, Any] | None = None,
    red_duos: dict[str, Any] | None = None,
    mode: PredictionMode = "mixed",
) -> dict[str, Any]:
    if mode == "pro" and blue_duos is not None and red_duos is not None:
        return {
            "jungle_support_advantage": compute_internal_duo_advantage(
                blue_duos["duo_jungle_support"],
                red_duos["duo_jungle_support"],
                mode=mode,
            ),
            "bot_lane_advantage": compute_internal_duo_advantage(
                blue_duos["duo_bot_lane"],
                red_duos["duo_bot_lane"],
                mode=mode,
            ),
        }

    return {
        "jungle_support_advantage": compute_matchup_advantage(
            jungle_support_matchup.get("blue_win_probability"),
            insufficient_data=jungle_support_matchup.get("insufficient_data", False),
        ),
        "bot_lane_advantage": compute_matchup_advantage(
            bot_lane_matchup.get("blue_win_probability"),
            insufficient_data=bot_lane_matchup.get("insufficient_data", False),
        ),
    }


def predict_draft(
    blue_team: list[dict[str, str]],
    red_team: list[dict[str, str]],
    patch: str,
    mode: PredictionMode = "mixed",
) -> dict[str, Any]:
    if len(blue_team) != 5 or len(red_team) != 5:
        raise ValueError("Chaque équipe doit contenir exactement 5 champions")

    patch = parse_patch(patch)
    soloq_df = None if mode == "pro" else load_soloq_scores(patch)
    champion_features, role_tags, lookup_by_norm = get_meraki_context()

    blue_details, warnings_blue = build_team_prediction_details(
        blue_team,
        side=0,
        patch=patch,
        soloq_df=soloq_df,
        champion_features=champion_features,
        lookup_by_norm=lookup_by_norm,
        role_tags=role_tags,
        mode=mode,
    )
    red_details, warnings_red = build_team_prediction_details(
        red_team,
        side=1,
        patch=patch,
        soloq_df=soloq_df,
        champion_features=champion_features,
        lookup_by_norm=lookup_by_norm,
        role_tags=role_tags,
        mode=mode,
    )

    score_blue = blue_details["score_final"]
    score_red = red_details["score_final"]
    blue_prob, red_prob = score_diff_to_probabilities(score_blue, score_red)

    differential = compute_attribute_differential(
        blue_details["attribute_profile"],
        red_details["attribute_profile"],
    )

    blue_duos, warnings_blue_duos = build_team_duo_synergies(blue_team, mode=mode)
    red_duos, warnings_red_duos = build_team_duo_synergies(red_team, mode=mode)
    bot_lane_matchup = build_bot_lane_matchup(
        blue_team,
        red_team,
        soloq_df,
        champion_features,
        lookup_by_norm,
        blue_duos["duo_bot_lane"],
        red_duos["duo_bot_lane"],
        mode=mode,
    )
    jungle_support_matchup = build_jungle_support_matchup(
        blue_team,
        red_team,
        soloq_df,
        champion_features,
        lookup_by_norm,
        blue_duos["duo_jungle_support"],
        red_duos["duo_jungle_support"],
        mode=mode,
    )
    duo_differential = build_duo_differential(
        bot_lane_matchup,
        jungle_support_matchup,
        blue_duos=blue_duos,
        red_duos=red_duos,
        mode=mode,
    )

    return {
        "mode": mode,
        "blue_win_probability": round(blue_prob, 4),
        "red_win_probability": round(red_prob, 4),
        "blue": blue_details,
        "red": red_details,
        "differential": differential,
        "duo_synergies": {
            "blue": blue_duos,
            "red": red_duos,
        },
        "bot_lane_matchup": bot_lane_matchup,
        "jungle_support_matchup": jungle_support_matchup,
        "duo_differential": duo_differential,
        "warnings": warnings_blue + warnings_red + warnings_blue_duos + warnings_red_duos,
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
    unique_pairs = filtered[["champion", "role"]].drop_duplicates()
    candidates = [
        (str(champion), str(role))
        for champion, role in zip(unique_pairs["champion"], unique_pairs["role"], strict=True)
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
