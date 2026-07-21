#!/usr/bin/env python3
"""Audit de couverture des seuils pro sur Oracle's Elixir.

Usage:
    python audit_pro_coverage.py
    python audit_pro_coverage.py --oracle-csv data/2026_LoL_esports_match_data_from_OraclesElixir.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from build_duo_dataset import (
    DEFAULT_ORACLE_CSV,
    aggregate_duos,
    build_duo_records,
    load_player_rows,
)
from pro_force import MIN_GAMES_PRO_FORCE, ORACLE_POSITION_TO_ROLE

# Seuil actuel des duos (build_duo_dataset.SEUIL_MIN_GAMES)
DUO_MIN_GAMES = 15

# ---------------------------------------------------------------------------
# Seuils alternatifs à envisager si la couverture actuelle est faible.
# NE PAS modifier les constantes de production sans décision explicite.
#
# Exemple après audit (à recalculer si le CSV change) :
#   Force pro (champion/role) : seuil 10 -> ~X% couverts | seuil 7 -> ~Y%
#   Duos jungle-support / bot : seuil 15 -> ~X% | seuil 10 -> ~Y% | seuil 8 -> ~Z%
# ---------------------------------------------------------------------------
ALTERNATIVE_FORCE_THRESHOLDS = (7, 8, 5)
ALTERNATIVE_DUO_THRESHOLDS = (12, 10, 8, 5)
LOW_COVERAGE_THRESHOLD = 0.40  # >40% sous le seuil = couverture insuffisante


def pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return 100.0 * numerator / denominator


def audit_champion_role_force(players: pd.DataFrame, min_games: int) -> tuple[int, int]:
    df = players.copy()
    df["role"] = df["position"].map(ORACLE_POSITION_TO_ROLE)
    df = df.dropna(subset=["role", "champion"])
    grouped = df.groupby(["champion", "role"], as_index=False).agg(games=("result", "count"))
    total = len(grouped)
    covered = int((grouped["games"] >= min_games).sum())
    return covered, total


def audit_duo_pairs(
    records: list[dict],
    min_games: int,
) -> tuple[int, int]:
    table = aggregate_duos(records)
    total = len(table)
    covered = int((table["games"] >= min_games).sum()) if total else 0
    return covered, total


def print_threshold_suggestions(
    label: str,
    covered: int,
    total: int,
    current_threshold: int,
    alternatives: tuple[int, ...],
    audit_fn,
    players_or_records,
) -> None:
    coverage = covered / total if total else 0.0
    below_pct = 100.0 - pct(covered, total)
    if below_pct <= LOW_COVERAGE_THRESHOLD * 100:
        return

    print(f"\n--- Suggestions de seuil alternatif : {label} ---")
    print(
        "Couverture actuelle (seuil %d) : %.1f%% (%.1f%% sous le seuil)"
        % (current_threshold, pct(covered, total), below_pct)
    )
    for alt in alternatives:
        if alt >= current_threshold:
            continue
        alt_covered, alt_total = audit_fn(players_or_records, alt)
        print(
            "  Seuil %2d games -> %.1f%% couverts (%d/%d)"
            % (alt, pct(alt_covered, alt_total), alt_covered, alt_total)
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit couverture données pro Oracle's Elixir")
    parser.add_argument(
        "--oracle-csv",
        type=Path,
        default=DEFAULT_ORACLE_CSV,
        help="Chemin vers le CSV Oracle's Elixir",
    )
    args = parser.parse_args()

    if not args.oracle_csv.exists():
        raise SystemExit(f"CSV introuvable: {args.oracle_csv}")

    players = load_player_rows(args.oracle_csv)
    js_records, bl_records = build_duo_records(players)

    force_covered, force_total = audit_champion_role_force(players, MIN_GAMES_PRO_FORCE)
    js_covered, js_total = audit_duo_pairs(js_records, DUO_MIN_GAMES)
    bl_covered, bl_total = audit_duo_pairs(bl_records, DUO_MIN_GAMES)

    print("=== Audit couverture pro (Oracle's Elixir) ===")
    print(f"Fichier : {args.oracle_csv}")
    print(f"Lignes joueur (complete) : {len(players)}")
    print()

    print(
        f"(a) Force pro champion/rôle (seuil {MIN_GAMES_PRO_FORCE} games) : "
        f"{pct(force_covered, force_total):.1f}% "
        f"({force_covered}/{force_total} paires)"
    )
    print(
        f"(b) Duos jungle-support (seuil {DUO_MIN_GAMES} games) : "
        f"{pct(js_covered, js_total):.1f}% "
        f"({js_covered}/{js_total} paires)"
    )
    print(
        f"(b) Duos bot lane (seuil {DUO_MIN_GAMES} games) : "
        f"{pct(bl_covered, bl_total):.1f}% "
        f"({bl_covered}/{bl_total} paires)"
    )

    duo_total = js_total + bl_total
    duo_covered = js_covered + bl_covered
    print(
        f"(b) Duos tous types confondus : "
        f"{pct(duo_covered, duo_total):.1f}% "
        f"({duo_covered}/{duo_total} paires)"
    )

    print_threshold_suggestions(
        "force champion/role",
        force_covered,
        force_total,
        MIN_GAMES_PRO_FORCE,
        ALTERNATIVE_FORCE_THRESHOLDS,
        audit_champion_role_force,
        players,
    )

    def audit_all_duos(records: list, min_games: int) -> tuple[int, int]:
        js_c, js_t = audit_duo_pairs(js_records, min_games)
        bl_c, bl_t = audit_duo_pairs(bl_records, min_games)
        return js_c + bl_c, js_t + bl_t

    print_threshold_suggestions(
        "duos (jungle-support + bot lane)",
        duo_covered,
        duo_total,
        DUO_MIN_GAMES,
        ALTERNATIVE_DUO_THRESHOLDS,
        lambda _records, min_games: audit_all_duos([], min_games),
        [],
    )


if __name__ == "__main__":
    main()
