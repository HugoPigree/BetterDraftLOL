from __future__ import annotations

from pathlib import Path

from build_duo_dataset import load_player_rows
from data_refresh.constants import DEFAULT_ORACLE_CSV


def parse_patch_value(patch: object) -> float:
    return float(str(patch).strip())


def detect_patch_info(oracle_csv: Path = DEFAULT_ORACLE_CSV) -> dict[str, object]:
    """Détecte le patch le plus récent et la liste des patchs dans Oracle."""
    players = load_player_rows(oracle_csv)
    if players.empty or "patch" not in players.columns:
        return {
            "latest_patch": "16.13",
            "patches": [],
            "player_rows": 0,
        }

    patches_sorted = sorted(
        {parse_patch_value(value) for value in players["patch"].dropna().unique()},
    )
    patch_labels = [format_patch_label(value) for value in patches_sorted]
    latest = patch_labels[-1] if patch_labels else "16.13"

    team_games = int(players["gameid"].nunique()) if "gameid" in players.columns else 0

    return {
        "latest_patch": latest,
        "patches": patch_labels,
        "player_rows": int(len(players)),
        "team_games": team_games,
    }


def format_patch_label(patch_value: float) -> str:
    text = f"{patch_value:.2f}".rstrip("0").rstrip(".")
    if "." not in text:
        return f"{text}.0"
    return text
