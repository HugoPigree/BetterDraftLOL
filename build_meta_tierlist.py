#!/usr/bin/env python3
"""Construit la tierlist meta pro (Wilson, pick/ban rate, trend) depuis Oracle's Elixir.

Les bans Oracle (ban1-ban5) sont au niveau equipe sans role cible : ban_rate est
calcule au niveau champion global puis reporte sur chaque ligne champion/role.
presence_score = pick_rate (role) + ban_rate (champion global).

Le bot consomme presence_score via get_meta_pool_for_role() (bonus leger sur meta_score).
"""

from __future__ import annotations

import argparse
import logging
import math
from pathlib import Path

import pandas as pd

from build_duo_dataset import load_player_rows
from predict_draft import get_meraki_context
from pro_force import (
    ORACLE_POSITION_TO_ROLE,
    get_pro_winrate_lookup,
    print_meta_pool_comparison,
    pro_meta_score,
)

DATA_DIR = Path("data")
DEFAULT_ORACLE_CSV = DATA_DIR / "2026_LoL_esports_match_data_from_OraclesElixir.csv"
OUTPUT_CSV = DATA_DIR / "meta_tierlist.csv"
OUTPUT_REPORT = DATA_DIR / "meta_tierlist_report.md"

ROLES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
BAN_COLUMNS = ["ban1", "ban2", "ban3", "ban4", "ban5"]
Z_95 = 1.96
TREND_STABLE_EPS = 0.005  # 0.5 pp sur pick_rate entre patch le plus ancien et le plus recent
MIN_GAMES_REPORT = 10


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def wilson_lower_bound(wins: int, games: int, z: float = Z_95) -> float:
    if games <= 0:
        return 0.0
    p = wins / games
    z2 = z * z
    denom = 1.0 + z2 / games
    radicand = (p * (1.0 - p) + z2 / (4.0 * games)) / games
    numerator = p + z2 / (2.0 * games) - z * math.sqrt(max(0.0, radicand))
    return numerator / denom


def parse_patch_value(patch: object) -> float:
    return float(str(patch).strip())


def sorted_patches(patches: pd.Series) -> list[float]:
    unique = {parse_patch_value(value) for value in patches.dropna().unique()}
    return sorted(unique)


def load_team_rows(oracle_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(oracle_csv, low_memory=False)
    teams = df[(df["datacompleteness"] == "complete") & (df["position"] == "team")].copy()
    logging.info("%d lignes equipe (complete)", len(teams))
    return teams


def compute_champion_ban_rates(teams: pd.DataFrame) -> tuple[dict[str, float], int]:
    """Ban rate global par champion : games banis / total games.

    Oracle stocke ban1-ban5 sur chaque ligne equipe (5 bans par side).
    Un ban ne cible pas un role : on ne peut pas ventiler ban_rate par role.
    """
    missing = [col for col in BAN_COLUMNS if col not in teams.columns]
    if missing:
        logging.warning(
            "Colonnes ban absentes (%s) — ban_rate et presence_score seront 0.",
            ", ".join(missing),
        )
        return {}, 0

    total_games = teams["gameid"].nunique()
    if total_games == 0:
        return {}, 0

    ban_counts: dict[str, int] = {}
    for _, row in teams.iterrows():
        seen_in_game_side: set[str] = set()
        for col in BAN_COLUMNS:
            champion = row.get(col)
            if pd.isna(champion):
                continue
            name = str(champion).strip()
            if not name or name in seen_in_game_side:
                continue
            seen_in_game_side.add(name)
            ban_counts[name] = ban_counts.get(name, 0) + 1

    ban_rates = {
        champion: count / total_games for champion, count in ban_counts.items()
    }
    logging.info(
        "Ban rates calcules pour %d champions (%d games, colonnes %s).",
        len(ban_rates),
        total_games,
        ", ".join(BAN_COLUMNS),
    )
    return ban_rates, total_games


def aggregate_player_stats(players: pd.DataFrame) -> pd.DataFrame:
    players = players.copy()
    players["role"] = players["position"].map(ORACLE_POSITION_TO_ROLE)
    players = players.dropna(subset=["role", "champion", "patch"])
    players["champion"] = players["champion"].astype(str).str.strip()
    players["patch"] = players["patch"].map(parse_patch_value)
    players["result"] = players["result"].astype(int)

    grouped = (
        players.groupby(["champion", "role"], as_index=False)
        .agg(games=("result", "count"), wins=("result", "sum"))
    )
    grouped["winrate_brut"] = grouped["wins"] / grouped["games"]
    grouped["wilson_lower_bound"] = grouped.apply(
        lambda row: wilson_lower_bound(int(row["wins"]), int(row["games"])),
        axis=1,
    )
    return grouped


def compute_pick_rates(players: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    players = players.copy()
    players["role"] = players["position"].map(ORACLE_POSITION_TO_ROLE)
    players = players.dropna(subset=["role", "champion", "patch"])
    players["champion"] = players["champion"].astype(str).str.strip()
    players["patch"] = players["patch"].map(parse_patch_value)

    role_totals = players.groupby("role", as_index=False).size().rename(columns={"size": "role_games"})
    pick_counts = (
        players.groupby(["champion", "role"], as_index=False)
        .size()
        .rename(columns={"size": "pick_count"})
    )
    pick_rates = pick_counts.merge(role_totals, on="role", how="left")
    pick_rates["pick_rate"] = pick_rates["pick_count"] / pick_rates["role_games"]

    patch_role_totals = (
        players.groupby(["patch", "role"], as_index=False)
        .size()
        .rename(columns={"size": "role_games_patch"})
    )
    patch_pick_counts = (
        players.groupby(["patch", "champion", "role"], as_index=False)
        .size()
        .rename(columns={"size": "pick_count_patch"})
    )
    patch_pick_rates = patch_pick_counts.merge(
        patch_role_totals, on=["patch", "role"], how="left"
    )
    patch_pick_rates["pick_rate_patch"] = (
        patch_pick_rates["pick_count_patch"] / patch_pick_rates["role_games_patch"]
    )
    return pick_rates, patch_pick_rates


def compute_trend(
    patch_pick_rates: pd.DataFrame,
    patches_sorted: list[float],
) -> pd.DataFrame:
    if len(patches_sorted) < 3:
        logging.warning(
            "Moins de 3 patchs (%d) — trend='stable (0.000)' pour toutes les lignes.",
            len(patches_sorted),
        )
        return pd.DataFrame(columns=["champion", "role", "trend"])

    last_three = patches_sorted[-3:]
    subset = patch_pick_rates[patch_pick_rates["patch"].isin(last_three)]
    pivot = subset.pivot_table(
        index=["champion", "role"],
        columns="patch",
        values="pick_rate_patch",
        aggfunc="first",
    )

    rows: list[dict[str, str]] = []
    oldest, _, newest = last_three
    for (champion, role), series in pivot.iterrows():
        rate_old_raw = series.get(oldest)
        rate_new_raw = series.get(newest)
        rate_old = 0.0 if pd.isna(rate_old_raw) else float(rate_old_raw)
        rate_new = 0.0 if pd.isna(rate_new_raw) else float(rate_new_raw)
        if pd.isna(rate_old_raw) or pd.isna(rate_new_raw):
            rows.append(
                {
                    "champion": champion,
                    "role": role,
                    "trend": "stable (+0.000)",
                }
            )
            continue
        delta = rate_new - rate_old
        if delta > TREND_STABLE_EPS:
            label = "hausse"
        elif delta < -TREND_STABLE_EPS:
            label = "baisse"
        else:
            label = "stable"
        rows.append(
            {
                "champion": champion,
                "role": role,
                "trend": f"{label} ({delta:+.3f})",
            }
        )
    return pd.DataFrame(rows)


def build_tierlist(oracle_csv: Path) -> pd.DataFrame:
    players = load_player_rows(oracle_csv)
    teams = load_team_rows(oracle_csv)
    ban_rates, total_games = compute_champion_ban_rates(teams)

    stats = aggregate_player_stats(players)
    pick_rates, patch_pick_rates = compute_pick_rates(players)
    patches_sorted = sorted_patches(players["patch"])
    trends = compute_trend(patch_pick_rates, patches_sorted)

    tierlist = stats.merge(
        pick_rates[["champion", "role", "pick_rate"]],
        on=["champion", "role"],
        how="left",
    )
    tierlist["ban_rate"] = tierlist["champion"].map(ban_rates).fillna(0.0)
    tierlist["pick_rate"] = tierlist["pick_rate"].fillna(0.0)
    tierlist["presence_score"] = tierlist["pick_rate"] + tierlist["ban_rate"]

    if trends.empty:
        tierlist["trend"] = "stable (+0.000)"
    else:
        tierlist = tierlist.merge(trends, on=["champion", "role"], how="left")
        tierlist["trend"] = tierlist["trend"].fillna("stable (+0.000)")

    tierlist = tierlist[
        [
            "champion",
            "role",
            "games",
            "winrate_brut",
            "wilson_lower_bound",
            "pick_rate",
            "ban_rate",
            "presence_score",
            "trend",
        ]
    ].sort_values(["role", "wilson_lower_bound", "games"], ascending=[True, False, False])
    return tierlist


def write_csv(tierlist: pd.DataFrame, output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    tierlist.to_csv(output_csv, index=False, float_format="%.6f")
    logging.info("CSV exporte: %s (%d lignes)", output_csv, len(tierlist))


def write_report(tierlist: pd.DataFrame, output_report: Path, patches_sorted: list[float]) -> None:
    lines: list[str] = [
        "# Meta tierlist pro (Oracle's Elixir)",
        "",
        "Classement par `wilson_lower_bound` (IC Wilson 95%, borne inferieure).",
        "",
        "## Notes ban_rate",
        "",
        "- Colonnes Oracle `ban1`…`ban5` : bans par equipe, **sans role associe**.",
        "- `ban_rate` = part des games ou le champion est banni (max 1 ban/game cote global).",
        "- Reporte identique sur chaque ligne champion/role du meme champion.",
        "- `presence_score` = `pick_rate` (role) + `ban_rate` (global champion).",
        "",
    ]
    if len(patches_sorted) >= 3:
        last_three = patches_sorted[-3:]
        lines.append(
            f"## Trend (pick_rate sur patchs {last_three[0]:.2f} → {last_three[-1]:.2f})"
        )
    else:
        lines.append("## Trend")
        lines.append("Moins de 3 patchs disponibles — trend stable par defaut.")
    lines.append("")

    for role in ROLES:
        role_df = tierlist[
            (tierlist["role"] == role) & (tierlist["games"] >= MIN_GAMES_REPORT)
        ].head(20)
        lines.append(f"## {role}")
        lines.append("")
        lines.append(
            "| Rang | Champion | Games | WR brut | Wilson LB | Pick rate | Ban rate | Trend |"
        )
        lines.append("|---:|---|---:|---:|---:|---:|---:|---|")
        for rank, row in enumerate(role_df.itertuples(index=False), start=1):
            lines.append(
                f"| {rank} | {row.champion} | {row.games} | "
                f"{row.winrate_brut:.1%} | {row.wilson_lower_bound:.1%} | "
                f"{row.pick_rate:.2%} | {row.ban_rate:.2%} | {row.trend} |"
            )
        lines.append("")

    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_report.write_text("\n".join(lines), encoding="utf-8")
    logging.info("Rapport exporte: %s", output_report)


def _top_meta_score_by_role(
    oracle_csv: Path,
    min_games: int = MIN_GAMES_REPORT,
) -> dict[str, list[tuple[str, float]]]:
    champion_features, _, lookup_by_norm = get_meraki_context()
    pro_lookup_keys = {
        (champion, role)
        for (champion, role), (_, games) in get_pro_winrate_lookup(oracle_csv).items()
        if games >= min_games
    }

    by_role: dict[str, list[tuple[str, float]]] = {role: [] for role in ROLES}
    seen: set[tuple[str, str]] = set()
    for champion, role in pro_lookup_keys:
        if (champion, role) in seen:
            continue
        seen.add((champion, role))
        scored = pro_meta_score(champion, role, champion_features, lookup_by_norm, oracle_csv)
        if scored is None:
            continue
        meta, games, _, fitness, name = scored
        if games < min_games or fitness < 0.20:
            continue
        by_role[role].append((name, meta))

    for role in ROLES:
        by_role[role].sort(key=lambda item: (-item[1], item[0].casefold()))
    return by_role


def _top_wilson_by_role(
    tierlist: pd.DataFrame,
    min_games: int = MIN_GAMES_REPORT,
) -> dict[str, list[tuple[str, float]]]:
    by_role: dict[str, list[tuple[str, float]]] = {}
    for role in ROLES:
        role_df = tierlist[
            (tierlist["role"] == role) & (tierlist["games"] >= min_games)
        ].sort_values(["wilson_lower_bound", "games"], ascending=[False, False])
        by_role[role] = [
            (row.champion, float(row.wilson_lower_bound))
            for row in role_df.head(10).itertuples(index=False)
        ]
    return by_role


def print_comparison(tierlist: pd.DataFrame, oracle_csv: Path) -> dict[str, str]:
    meta_tops = _top_meta_score_by_role(oracle_csv)
    wilson_tops = _top_wilson_by_role(tierlist)

    print("\n" + "=" * 88)
    print("COMPARAISON TOP 10 — meta_score (bot actuel) vs wilson_lower_bound")
    print("=" * 88)

    role_verdicts: dict[str, str] = {}
    quasi_identical_roles = 0

    for role in ROLES:
        meta_list = meta_tops.get(role, [])[:10]
        wilson_list = wilson_tops.get(role, [])[:10]
        meta_names = [name for name, _ in meta_list]
        wilson_names = [name for name, _ in wilson_list]

        only_meta = sorted(set(meta_names) - set(wilson_names), key=str.casefold)
        only_wilson = sorted(set(wilson_names) - set(meta_names), key=str.casefold)
        top5_meta = set(meta_names[:5])
        top5_wilson = set(wilson_names[:5])
        same_top5 = top5_meta == top5_wilson
        if same_top5:
            quasi_identical_roles += 1
            role_verdicts[role] = "quasi_identique"
        else:
            role_verdicts[role] = "different"

        print(f"\n--- {role} ---")
        print(f"{'#':>2}  {'meta_score':<28}  {'wilson_lower_bound':<28}")
        for index in range(10):
            meta_cell = (
                f"{index + 1:2}. {meta_list[index][0]:<18} ({meta_list[index][1]:.3f})"
                if index < len(meta_list)
                else ""
            )
            wilson_cell = (
                f"{index + 1:2}. {wilson_list[index][0]:<18} ({wilson_list[index][1]:.3f})"
                if index < len(wilson_list)
                else ""
            )
            print(f"{index + 1:2}  {meta_cell:<28}  {wilson_cell}")

        if only_meta:
            print(f"  Seulement meta_score top10 : {', '.join(only_meta)}")
        if only_wilson:
            print(f"  Seulement wilson top10     : {', '.join(only_wilson)}")
        if not only_meta and not only_wilson and meta_names == wilson_names:
            print("  Top 10 identiques (meme ordre possiblement different).")

    print("\n" + "=" * 88)
    print("RESUME")
    print("=" * 88)
    diff_roles = [role for role, verdict in role_verdicts.items() if verdict == "different"]
    print(
        f"  Quasi identiques (meme top 5) : {quasi_identical_roles}/{len(ROLES)} roles "
        f"({', '.join(r for r, v in role_verdicts.items() if v == 'quasi_identique') or 'aucun'})"
    )
    print(
        f"  Significativement differents   : {len(diff_roles)}/{len(ROLES)} roles "
        f"({', '.join(diff_roles) or 'aucun'})"
    )
    return role_verdicts


def main() -> None:
    parser = argparse.ArgumentParser(description="Build meta tierlist from Oracle's Elixir")
    parser.add_argument("--oracle-csv", type=Path, default=DEFAULT_ORACLE_CSV)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    parser.add_argument("--output-report", type=Path, default=OUTPUT_REPORT)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    setup_logging(args.verbose)

    if not args.oracle_csv.exists():
        raise FileNotFoundError(f"Oracle CSV introuvable: {args.oracle_csv}")

    players = load_player_rows(args.oracle_csv)
    patches_sorted = sorted_patches(players["patch"])
    logging.info("Patchs disponibles (%d): %s", len(patches_sorted), patches_sorted)

    tierlist = build_tierlist(args.oracle_csv)
    write_csv(tierlist, args.output_csv)
    write_report(tierlist, args.output_report, patches_sorted)
    print_comparison(tierlist, args.oracle_csv)
    print_meta_pool_comparison(patch=str(patches_sorted[-1]) if patches_sorted else "16.13")


if __name__ == "__main__":
    main()
