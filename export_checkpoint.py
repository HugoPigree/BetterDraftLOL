#!/usr/bin/env python3
"""Export CSV from a solo queue collection checkpoint."""

import json
import sys
from pathlib import Path

import pandas as pd

DATA_DIR = Path("data/solo_queue")


def export_checkpoint(region: str = "euw") -> Path:
    path = DATA_DIR / f"checkpoint_{region}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    patch = data["target_patch"]
    rows = []

    for key, values in data["stats"].items():
        champion, role, row_patch = key.split("|", 2)
        if row_patch != patch:
            continue
        games = values["games"]
        wins = values["wins"]
        rows.append(
            {
                "champion": champion,
                "role": role,
                "patch": row_patch,
                "games": games,
                "wins": wins,
                "winrate": round(wins / games, 4) if games else 0.0,
            }
        )

    df = pd.DataFrame(rows, columns=["champion", "role", "patch", "games", "wins", "winrate"])
    df = df.sort_values(["champion", "role"]).reset_index(drop=True)
    out = DATA_DIR / f"soloq_winrates_{region}_{patch}.csv"
    df.to_csv(out, index=False)

    print(f"matchs: {data['matches_collected']}")
    print(f"joueurs: {data['players_processed']}")
    print(f"lignes csv: {len(df)}")
    print(f"fichier: {out}")
    return out


if __name__ == "__main__":
    region = sys.argv[1] if len(sys.argv) > 1 else "euw"
    export_checkpoint(region)
