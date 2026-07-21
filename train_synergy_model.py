#!/usr/bin/env python3
"""Train an XGBoost model to predict team win from draft composition features."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, confusion_matrix, roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold, train_test_split

DATA_PATH = Path("data/training_dataset.csv")
MODEL_DIR = Path("model")
MODEL_PATH = MODEL_DIR / "synergy_model.json"
FEATURES_ORDER_PATH = MODEL_DIR / "features_order.json"

TARGET_COLUMN = "result"
ID_COLUMNS = {"gameid"}
RANDOM_STATE = 42

PARAM_GRID = {
    "max_depth": [3, 4, 5],
    "n_estimators": [100, 150, 200],
    "learning_rate": [0.05, 0.1],
}


def load_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"ERREUR: dataset introuvable -> {path}", file=sys.stderr)
        sys.exit(1)
    df = pd.read_csv(path)
    print(f"Dataset chargé: {df.shape[0]} lignes, {df.shape[1]} colonnes")
    return df


def split_features_target(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series, list[str]]:
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"Colonne target '{TARGET_COLUMN}' absente du dataset")

    if "gameid" not in df.columns:
        raise ValueError("Colonne 'gameid' absente du dataset")

    feature_columns = [col for col in df.columns if col not in ID_COLUMNS and col != TARGET_COLUMN]
    X = df[feature_columns].copy()
    y = df[TARGET_COLUMN].astype(int)
    groups = df["gameid"]

    print(f"Features ({len(feature_columns)}): {feature_columns}")
    print(f"Target: {TARGET_COLUMN} (balance={y.mean():.4f})")
    return X, y, groups, feature_columns


def split_by_gameid(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    test_size: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series, pd.Series]:
    unique_games = groups.unique()
    train_games, test_games = train_test_split(
        unique_games,
        test_size=test_size,
        random_state=RANDOM_STATE,
    )
    train_mask = groups.isin(train_games)
    test_mask = groups.isin(test_games)

    X_train = X.loc[train_mask].reset_index(drop=True)
    X_test = X.loc[test_mask].reset_index(drop=True)
    y_train = y.loc[train_mask].reset_index(drop=True)
    y_test = y.loc[test_mask].reset_index(drop=True)
    groups_train = groups.loc[train_mask].reset_index(drop=True)
    groups_test = groups.loc[test_mask].reset_index(drop=True)

    overlap = set(train_games).intersection(set(test_games))
    if overlap:
        raise RuntimeError(f"Fuite détectée: {len(overlap)} gameid partagés entre train et test")

    print("\n=== Split train/test par gameid ===")
    print(f"Games train: {len(train_games)} | Games test: {len(test_games)}")
    print(f"Lignes train: {len(X_train)} | Lignes test: {len(X_test)}")
    print(f"Winrate train: {y_train.mean():.4f} | Winrate test: {y_test.mean():.4f}")
    return X_train, X_test, y_train, y_test, groups_train, groups_test


def train_with_cv(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    groups_train: pd.Series,
) -> xgb.XGBClassifier:
    base_model = xgb.XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    search = GridSearchCV(
        estimator=base_model,
        param_grid=PARAM_GRID,
        scoring="roc_auc",
        cv=cv,
        n_jobs=-1,
        verbose=1,
    )

    print("\n=== Recherche d'hyperparamètres (StratifiedGroupKFold, 5 folds, group=gameid) ===")
    print(f"Grille testée: {PARAM_GRID}")
    search.fit(X_train, y_train, groups=groups_train)

    print("\nMeilleurs hyperparamètres:")
    for key, value in search.best_params_.items():
        print(f"  - {key}: {value}")
    print(f"Meilleur AUC-ROC CV: {search.best_score_:.4f}")

    return search.best_estimator_


def print_confusion_matrix(y_true: pd.Series, y_pred: np.ndarray) -> None:
    matrix = confusion_matrix(y_true, y_pred)
    print("\nMatrice de confusion (seuil=0.5):")
    print("                 Pred 0    Pred 1")
    print(f"  Actual 0      {matrix[0, 0]:8d}  {matrix[0, 1]:8d}")
    print(f"  Actual 1      {matrix[1, 0]:8d}  {matrix[1, 1]:8d}")


def print_calibration(y_true: pd.Series, y_proba: np.ndarray, n_bins: int = 10) -> None:
    df = pd.DataFrame({"y_true": y_true, "y_proba": y_proba})
    df["bucket"] = pd.cut(df["y_proba"], bins=np.linspace(0.0, 1.0, n_bins + 1), include_lowest=True)

    calibration = (
        df.groupby("bucket", observed=False)
        .agg(predicted_prob=("y_proba", "mean"), actual_winrate=("y_true", "mean"), count=("y_true", "size"))
        .reset_index()
    )

    print("\n=== Calibration (test set) ===")
    print(f"{'Bucket':<28} {'Pred moy':>10} {'Winrate réel':>14} {'Count':>8}")
    for _, row in calibration.iterrows():
        if row["count"] == 0:
            continue
        print(
            f"{str(row['bucket']):<28} "
            f"{row['predicted_prob']:10.4f} "
            f"{row['actual_winrate']:14.4f} "
            f"{int(row['count']):8d}"
        )


def print_feature_importance(model: xgb.XGBClassifier, feature_names: list[str], top_n: int = 20) -> None:
    importances = model.feature_importances_
    ranked = sorted(zip(feature_names, importances), key=lambda item: item[1], reverse=True)

    print(f"\n=== Importance des features (top {top_n}) ===")
    print(f"{'Feature':<28} {'Importance':>12}")
    for name, score in ranked[:top_n]:
        print(f"{name:<28} {score:12.6f}")


def evaluate(model: xgb.XGBClassifier, X_test: pd.DataFrame, y_test: pd.Series) -> None:
    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= 0.5).astype(int)

    accuracy = accuracy_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_proba)

    print("\n=== Évaluation test set ===")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"AUC-ROC:  {auc:.4f}")

    print_confusion_matrix(y_test, y_pred)
    print_calibration(y_test, y_proba)


def save_artifacts(model: xgb.XGBClassifier, feature_names: list[str]) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save_model(MODEL_PATH)
    FEATURES_ORDER_PATH.write_text(json.dumps(feature_names, indent=2), encoding="utf-8")

    print("\n=== Export ===")
    print(f"Modèle: {MODEL_PATH}")
    print(f"Ordre des features: {FEATURES_ORDER_PATH}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Entraîne un modèle XGBoost de synergie de draft.")
    parser.add_argument("--data", type=Path, default=DATA_PATH, help="Chemin vers training_dataset.csv")
    parser.add_argument("--test-size", type=float, default=0.2, help="Part du test set par gameid")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df = load_dataset(args.data)
    X, y, groups, feature_columns = split_features_target(df)
    X_train, X_test, y_train, y_test, groups_train, groups_test = split_by_gameid(
        X, y, groups, test_size=args.test_size
    )

    model = train_with_cv(X_train, y_train, groups_train)
    evaluate(model, X_test, y_test)
    print_feature_importance(model, feature_columns)
    save_artifacts(model, feature_columns)

    print("\nEntraînement terminé.")


if __name__ == "__main__":
    main()
