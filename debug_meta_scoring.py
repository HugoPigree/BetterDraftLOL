#!/usr/bin/env python3
"""Diagnostic isole du scoring meta pro (pro_meta_score / pool candidats bot).

Usage:
  python debug_meta_scoring.py --role JUNGLE
  python debug_meta_scoring.py --role TOP --top-n 15 --highlight Riven
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import predict_draft as pd
from pro_force import (
    MIN_GAMES_EXCLUSION,
    MIN_GAMES_PRO_FORCE,
    PRO_VOLUME_WEIGHT,
    PRO_WINRATE_WEIGHT,
    PRO_WINRATE_PRIOR_RATIO,
    compute_pro_winrate_by_champion,
    get_meta_pool_for_role,
    get_pro_winrate_lookup,
    get_role_pro_volume_context,
    pro_meta_score,
    pro_volume_norm,
    pro_role_fitness,
    shrink_pro_winrate,
)
from suggest_draft import (
    BOT_CANDIDATES_PER_ROLE,
    champions_playable_on_role,
    get_champion_role_catalog,
    get_meraki_context,
)


@dataclass
class ChampionMetaRow:
    champion: str
    games: int
    raw_winrate: float
    shrunk_winrate: float
    volume_norm: float
    role_fitness: float
    raw_meta: float
    meta_score: float
    rank: int
    in_bot_pool: bool
    in_top20: bool


def _normalize_role(role: str) -> str:
    return role.strip().upper()


def build_all_meta_rows(role: str) -> list[ChampionMetaRow]:
    role = _normalize_role(role)
    champion_features, _, lookup_by_norm = get_meraki_context()
    lookup = get_pro_winrate_lookup()
    volume_ctx = get_role_pro_volume_context(role)
    prior_games = max(30.0, volume_ctx["max_games"] * PRO_WINRATE_PRIOR_RATIO)

    rows: list[ChampionMetaRow] = []
    for (champion, slot_role), (winrate, games) in lookup.items():
        if slot_role != role or games < MIN_GAMES_PRO_FORCE:
            continue

        volume_norm = pro_volume_norm(games, role)
        shrunk = shrink_pro_winrate(winrate, games, role)
        fitness = pro_role_fitness(champion, role, champion_features, lookup_by_norm)
        raw_meta = PRO_VOLUME_WEIGHT * volume_norm + PRO_WINRATE_WEIGHT * shrunk
        meta_score = raw_meta * (0.35 + 0.65 * fitness)

        rows.append(
            ChampionMetaRow(
                champion=champion,
                games=games,
                raw_winrate=winrate,
                shrunk_winrate=shrunk,
                volume_norm=volume_norm,
                role_fitness=fitness,
                raw_meta=raw_meta,
                meta_score=meta_score,
                rank=0,
                in_bot_pool=False,
                in_top20=False,
            )
        )

    rows.sort(key=lambda r: (-r.meta_score, -r.games, r.champion.casefold()))
    for index, row in enumerate(rows, start=1):
        row.rank = index
        row.in_top20 = index <= 20

    return rows


def get_current_bot_meta_pool(
    role: str,
    patch: str,
    top_n: int,
) -> list[str]:
    """Pool bot via get_meta_pool_for_role (>= MIN_GAMES_EXCLUSION)."""
    role = _normalize_role(role)
    catalog = get_champion_role_catalog()
    champion_features, _, lookup_by_norm = get_meraki_context()
    all_playable = champions_playable_on_role(list(catalog.keys()), role, catalog)

    return get_meta_pool_for_role(
        role,
        patch,
        top_n=top_n,
        candidates=all_playable,
        champion_features=champion_features,
        lookup_by_norm=lookup_by_norm,
    )


def get_bot_candidate_pool_via_suggest(
    role: str,
    patch: str,
    limit: int,
) -> list[str]:
    """Reproduit _top_candidates_for_role(mode=pro) sur le catalogue complet."""
    from suggest_draft import _top_candidates_for_role

    catalog = get_champion_role_catalog()
    pool = list(catalog.keys())
    return _top_candidates_for_role(pool, role, catalog, patch, "pro", limit)


def _fmt_pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def print_volume_context(role: str) -> None:
    ctx = get_role_pro_volume_context(role)
    prior = max(30.0, ctx["max_games"] * PRO_WINRATE_PRIOR_RATIO)
    print(f"\nContexte volume {role}:")
    print(f"  max_games={ctx['max_games']:.0f}  median_games={ctx['median_games']:.0f}")
    print(f"  prior bayesien={prior:.1f} games (max * {PRO_WINRATE_PRIOR_RATIO})")
    print(
        f"  formule meta_score = ({PRO_VOLUME_WEIGHT}*volume_norm + "
        f"{PRO_WINRATE_WEIGHT}*shrunk_wr) * (0.35 + 0.65*role_fitness)"
    )
    print(f"  seuil inclusion actuel MIN_GAMES_PRO_FORCE={MIN_GAMES_PRO_FORCE}")
    print(f"  exclusion dure bot MIN_GAMES_EXCLUSION={MIN_GAMES_EXCLUSION}")


def print_table(
    rows: list[ChampionMetaRow],
    *,
    top_n: int,
    highlight: str | None,
    bot_pool: list[str],
) -> None:
    bot_pool_set = {name.casefold() for name in bot_pool}
    for row in rows:
        row.in_bot_pool = row.champion.casefold() in bot_pool_set

    print(f"\n{'=' * 110}")
    print(f"TABLEAU COMPLET — tri par meta_score decroissant (top 20 affiche)")
    print(f"{'=' * 110}")
    header = (
        f"{'Rang':>4}  {'Champion':<18} {'Games':>6} {'WR brut':>8} {'WR lisse':>8} "
        f"{'VolNorm':>7} {'Fitness':>7} {'MetaSc':>7}  {'Pool':>5}"
    )
    print(header)
    print("-" * len(header))

    for row in rows[:20]:
        marker = ""
        if highlight and row.champion.casefold() == highlight.casefold():
            marker = " <-- HIGHLIGHT"
        pool_flag = "OUI" if row.in_bot_pool else "non"
        print(
            f"{row.rank:4d}  {row.champion:<18} {row.games:6d} "
            f"{_fmt_pct(row.raw_winrate):>8} {_fmt_pct(row.shrunk_winrate):>8} "
            f"{row.volume_norm:7.3f} {row.role_fitness:7.3f} {row.meta_score:7.3f}  "
            f"{pool_flag:>5}{marker}"
        )

    total = len(rows)
    print(f"\n({total} champions avec >= {MIN_GAMES_PRO_FORCE} games pro en {rows[0].champion and ''}{''}")

    low_volume_high_wr = [
        r for r in rows if r.games <= 30 and r.raw_winrate >= 0.65
    ]
    if low_volume_high_wr:
        print("\nChampions faible volume + WR eleve (<=30 games, WR>=65%):")
        for row in sorted(low_volume_high_wr, key=lambda r: -r.raw_winrate)[:10]:
            print(
                f"  #{row.rank:3d} {row.champion:<16} {row.games:3d}g "
                f"WR={_fmt_pct(row.raw_winrate)} meta={row.meta_score:.3f} "
                f"pool={'OUI' if row.in_bot_pool else 'non'}"
            )


def print_pool_analysis(
    role: str,
    rows: list[ChampionMetaRow],
    top_n: int,
    bot_pool: list[str],
    suggest_pool: list[str],
) -> None:
    print(f"\n{'=' * 110}")
    print("ETAPE 2 — POOL CANDIDATS BOT")
    print(f"{'=' * 110}")
    print(
        "\nPool bot via get_meta_pool_for_role() "
        f"(>= {MIN_GAMES_EXCLUSION} games, tri meta_score):"
    )
    for index, name in enumerate(bot_pool, start=1):
        row = next((r for r in rows if r.champion == name), None)
        if row:
            print(
                f"  #{index:2d} {name:<16} games={row.games:4d} "
                f"WR={_fmt_pct(row.raw_winrate)} meta={row.meta_score:.3f} rang_global=#{row.rank}"
            )
        else:
            print(f"  #{index:2d} {name:<16} (pas de donnees pro suffisantes?)")

    print(f"\nPool reel suggest_bot_pick (_top_candidates_for_role limit={BOT_CANDIDATES_PER_ROLE}):")
    if bot_pool == suggest_pool[:top_n]:
        print("  Identique au pool rank_pro top_n (pas de divergence).")
    else:
        for index, name in enumerate(suggest_pool[:top_n], start=1):
            in_rank = name in bot_pool
            print(f"  #{index:2d} {name:<16} dans rank_pro top{top_n}: {'OUI' if in_rank else 'NON'}")

    low_in_pool = [name for name in bot_pool if (r := next((x for x in rows if x.champion == name), None)) and r.games <= 30]
    if low_in_pool:
        print(
            f"\n[!] {len(low_in_pool)} champion(s) a faible volume (<=30g) DANS le pool top_{top_n}:"
        )
        for name in low_in_pool:
            row = next(r for r in rows if r.champion == name)
            print(
                f"    {name}: {row.games}g WR={_fmt_pct(row.raw_winrate)} "
                f"meta=#{row.rank} score={row.meta_score:.3f}"
            )
    else:
        print(f"\nAucun champion <=30 games dans le pool top_{top_n}.")

    high_volume_outside = [
        r for r in rows
        if r.games >= 200 and r.champion not in bot_pool
    ][:5]
    if high_volume_outside:
        print("\nChampions fort volume EXCLUS du pool top_n (meta_score trop bas vs petits echantillons?):")
        for row in high_volume_outside:
            print(
                f"  #{row.rank:3d} {row.champion:<16} {row.games:4d}g "
                f"WR={_fmt_pct(row.raw_winrate)} meta={row.meta_score:.3f}"
            )


def print_diagnosis(rows: list[ChampionMetaRow], bot_pool: list[str], top_n: int) -> None:
    print(f"\n{'=' * 110}")
    print("SYNTHESE DIAGNOSTIC (sans correction appliquee)")
    print(f"{'=' * 110}")

    issues: list[str] = []

    low_in_pool = [
        r for r in rows
        if r.champion in bot_pool and r.games <= 30
    ]
    if low_in_pool:
        issues.append(
            f"Pool top_{top_n} contient {len(low_in_pool)} champ(s) < {MIN_GAMES_EXCLUSION} games "
            f"(ex: {', '.join(f'{r.champion} {r.games}g' for r in low_in_pool[:3])}) "
            "-> bug get_meta_pool_for_role."
        )

    example_low = next((r for r in rows if 10 <= r.games <= 20 and r.raw_winrate >= 0.70), None)
    example_high = next((r for r in rows if r.games >= 250 and r.raw_winrate <= 0.58), None)
    if example_low and example_high:
        if example_low.rank < example_high.rank:
            issues.append(
                f"Biais meta_score: {example_low.champion} ({example_low.games}g, "
                f"WR={_fmt_pct(example_low.raw_winrate)}) classe #{example_low.rank} "
                f"AVANT {example_high.champion} ({example_high.games}g, "
                f"WR={_fmt_pct(example_high.raw_winrate)}) #{example_high.rank} "
                "-> volume_norm log ne penalise pas assez les petits echantillons."
            )

    if not issues:
        issues.append("Pas de signal evident sur cet echantillon — verifier le role/highlight.")

    for index, issue in enumerate(issues, start=1):
        print(f"  {index}. {issue}")

    print("\nCorrections possibles (ETAPE 3, apres confirmation):")
    print("  A) get_meta_pool_for_role: trier d'abord par volume brut, puis WR/meta")
    print("  B) MIN_GAMES_EXCLUSION (30-50): exclusion dure sous le seuil")
    print("  C) Renforcer prior bayesien si le lissage seul est insuffisant")


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug scoring meta pro")
    parser.add_argument("--role", default="JUNGLE", help="Role a analyser (defaut: JUNGLE)")
    parser.add_argument("--top-n", type=int, default=15, help="Taille pool meta (defaut: 15)")
    parser.add_argument("--highlight", default="", help="Champion a surligner")
    parser.add_argument("--patch", default="16.13")
    args = parser.parse_args()

    pd.reset_predict_state()
    role = _normalize_role(args.role)
    highlight = args.highlight.strip() or None

    print("=" * 110)
    print(f"DEBUG META SCORING — role={role} top_n={args.top_n}")
    print("=" * 110)

    print_volume_context(role)
    rows = build_all_meta_rows(role)
    if not rows:
        print(f"Aucune donnee pro pour le role {role}.")
        return

    bot_pool = get_current_bot_meta_pool(role, args.patch, args.top_n)
    suggest_pool = get_bot_candidate_pool_via_suggest(role, args.patch, BOT_CANDIDATES_PER_ROLE)

    print_table(rows, top_n=args.top_n, highlight=highlight, bot_pool=bot_pool)
    print_pool_analysis(role, rows, args.top_n, bot_pool, suggest_pool)
    print_diagnosis(rows, bot_pool, args.top_n)

    if highlight:
        match = next((r for r in rows if r.champion.casefold() == highlight.casefold()), None)
        if match:
            print(f"\nDetail {highlight}:")
            print(
                f"  rang=#{match.rank} games={match.games} WR={_fmt_pct(match.raw_winrate)} "
                f"shrunk={_fmt_pct(match.shrunk_winrate)} meta={match.meta_score:.3f} "
                f"dans pool top_{args.top_n}: {'OUI' if match.champion in bot_pool else 'NON'}"
            )


if __name__ == "__main__":
    main()
