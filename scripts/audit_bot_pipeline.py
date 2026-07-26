#!/usr/bin/env python3
"""Audit complet du pipeline suggest_bot_pick — 30 drafts simulés avec logs détaillés."""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import predict_draft as pd
import pro_force
from suggest_draft import (
    BOT_CANDIDATES_PER_ROLE,
    PRO_MIN_SYNERGY_AFTER_TWO_PICKS,
    ROLES_ORDER,
    TEMPERATURE_BOT_PICK,
    TeamSide,
    _bot_meta_pool_for_role,
    _meta_diversity_penalty,
    _presence_repetition_penalty,
    _top_candidates_for_role,
    _two_stage_weighted_bot_pick,
    decompose_bot_candidate_score,
    get_champion_role_catalog,
    normalize_role,
    suggest_bot_pick,
    warmup_predict_caches,
)
from pro_force import get_meta_pool_for_role

PATCH = "16.13"


@dataclass
class CandidateRow:
    champion: str
    role: str
    selection_score: float
    rank: int = 0
    win_prob: float = 0.0
    synergy: float = 0.0
    meta_raw: float | None = None
    score_winrate: float = 0.0
    score_synergy_ml: float = 0.0
    score_meta: float = 0.0
    score_archetype: float = 0.0
    score_duo_bonus: float = 0.0
    score_lookahead_duo: float = 0.0
    score_pair_planning: float = 0.0
    score_comp_direction: float = 0.0
    score_opponent_counter: float = 0.0
    score_meta_diversity_penalty: float = 0.0
    score_presence_penalty: float = 0.0
    synergy_filtered: bool = False


@dataclass
class BotPickAudit:
    sim_id: int
    pick_index: int
    team_side: TeamSide
    bot_partial: list[dict[str, str]]
    opponent_partial: list[dict[str, str]]
    draft_depth: int
    greedy_opponent_active: bool
    chosen: dict[str, Any]
    pool_by_role: dict[str, list[str]]
    candidates: list[CandidateRow] = field(default_factory=list)
    global_rank: int = 0
    role_rank: int = 0
    pool_size: int = 0
    is_softmax_pick: bool = False
    gap_to_best: float = 0.0
    eval_ms: float = 0.0


def _available_pool(catalog: dict[str, list[str]], used: set[str]) -> list[str]:
    return sorted(
        [name for name in catalog if name.casefold() not in used],
        key=str.casefold,
    )


def _random_opp_pick(
    pool: list[str],
    role: str,
    catalog: dict[str, list[str]],
    reserved: set[str],
    rng: random.Random,
    patch: str,
) -> str | None:
    from suggest_draft import champions_playable_on_role

    playable = [
        name
        for name in champions_playable_on_role(pool, role, catalog)
        if name.casefold() not in reserved
    ]
    if not playable:
        return None
    top = get_meta_pool_for_role(role, patch, top_n=12, candidates=playable)
    if not top:
        return None
    return rng.choice(top[: min(6, len(top))])


def _evaluate_full_pool(
    bot_partial: list[dict[str, str]],
    opponent_partial: list[dict[str, str]],
    bot_remaining: list[str],
    pool: list[str],
    catalog: dict[str, list[str]],
    team_side: TeamSide,
    patch: str,
) -> tuple[dict[str, list[str]], list[CandidateRow]]:
    pool_by_role: dict[str, list[str]] = {}
    rows: list[CandidateRow] = []
    locked_picks = len(bot_partial)
    min_synergy = PRO_MIN_SYNERGY_AFTER_TWO_PICKS if locked_picks >= 2 else 0.40

    per_role_scores: dict[str, list[float]] = defaultdict(list)
    raw_rows: list[tuple[str, CandidateRow]] = []

    for role in bot_remaining:
        candidates = _top_candidates_for_role(
            pool, role, catalog, patch, "pro", BOT_CANDIDATES_PER_ROLE
        )
        pool_by_role[role] = candidates
        for champion in candidates:
            decomp = decompose_bot_candidate_score(
                bot_partial,
                opponent_partial,
                champion,
                role,
                patch,
                pool,
                team_side=team_side,
                mode="pro",
            )
            if decomp is None:
                continue
            synergy = float(decomp["synergy_raw"])
            filtered = locked_picks >= 1 and synergy < min_synergy
            row = CandidateRow(
                champion=champion,
                role=role,
                selection_score=float(decomp["selection_score"]),
                win_prob=float(decomp["win_probability"]),
                synergy=synergy,
                meta_raw=decomp.get("meta_raw"),
                score_winrate=float(decomp["score_winrate"]),
                score_synergy_ml=float(decomp["score_synergy_ml"]),
                score_meta=float(decomp["score_meta"]),
                score_archetype=float(decomp["score_archetype"]),
                score_duo_bonus=float(decomp["score_duo_bonus"]),
                score_lookahead_duo=float(decomp["score_lookahead_duo"]),
                score_pair_planning=float(decomp["score_pair_planning"]),
                score_comp_direction=float(decomp["score_comp_direction"]),
                score_opponent_counter=float(decomp["score_opponent_counter"]),
                score_meta_diversity_penalty=float(decomp["score_meta_diversity_penalty"]),
                score_presence_penalty=float(decomp["score_presence_penalty"]),
                synergy_filtered=filtered,
            )
            raw_rows.append((role, row))
            if not filtered:
                per_role_scores[role].append(row.selection_score)

    # Re-apply batch meta diversity / presence penalties per role (mirrors bot)
    adjusted: list[CandidateRow] = []
    for role, row in raw_rows:
        role_scores = per_role_scores.get(role, [])
        penalty_meta = _meta_diversity_penalty(row.meta_raw, role_scores)
        penalty_presence = _presence_repetition_penalty(row.champion, row.role, role_scores)
        row.selection_score = round(
            row.selection_score - penalty_meta - penalty_presence, 2
        )
        row.score_meta_diversity_penalty = round(penalty_meta, 2)
        row.score_presence_penalty = round(penalty_presence, 2)
        adjusted.append(row)

    eligible = [r for r in adjusted if not r.synergy_filtered]
    sort_pool = eligible if eligible else adjusted
    sort_pool.sort(key=lambda r: (-r.selection_score, r.champion.casefold()))
    for idx, row in enumerate(sort_pool, start=1):
        row.rank = idx

    return pool_by_role, sort_pool


def _standard_pick_order(bot_side: TeamSide) -> list[str]:
    """Ordre des slots de pick (blue/red) en phase de picks classique."""
    sequence = [
        ("blue", 1),
        ("red", 1),
        ("red", 2),
        ("blue", 2),
        ("blue", 3),
        ("red", 3),
        ("red", 4),
        ("red", 5),
        ("blue", 4),
        ("blue", 5),
    ]
    return [side for side, _ in sequence if side == bot_side]


def simulate_full_draft(
    sim_id: int,
    rng: random.Random,
    catalog: dict[str, list[str]],
    patch: str,
    bot_side: TeamSide,
) -> list[BotPickAudit]:
    used: set[str] = set()
    bot_partial: list[dict[str, str]] = []
    opponent_partial: list[dict[str, str]] = []
    audits: list[BotPickAudit] = []

    # Contexte adverse initial varié (0-3 picks adverses avant le bot)
    n_pre_opp = rng.randint(0, 3)
    for _ in range(n_pre_opp):
        pool = _available_pool(catalog, used)
        role = rng.choice(ROLES_ORDER)
        champ = _random_opp_pick(pool, role, catalog, used, rng, patch)
        if champ is None:
            continue
        opponent_partial.append({"champion": champ, "role": role})
        used.add(champ.casefold())

    bot_pick_slots = _standard_pick_order(bot_side)
    opp_side: TeamSide = "red" if bot_side == "blue" else "blue"

    for pick_index, _ in enumerate(bot_pick_slots, start=1):
        # Simuler picks adverses intercalés selon ordre standard
        total_picks = len(bot_partial) + len(opponent_partial)
        while total_picks < 10 and len(bot_partial) < pick_index:
            # C'est au bot de picker
            break
        # Insérer picks adverses jusqu'à ce que ce soit le tour du bot
        draft_positions = [
            ("blue", 1),
            ("red", 1),
            ("red", 2),
            ("blue", 2),
            ("blue", 3),
            ("red", 3),
            ("red", 4),
            ("red", 5),
            ("blue", 4),
            ("blue", 5),
        ]
        current_slot = len(bot_partial) + len(opponent_partial)
        while current_slot < len(draft_positions):
            side, _ = draft_positions[current_slot]
            if side == bot_side and len(bot_partial) < pick_index:
                break
            if side != bot_side:
                pool = _available_pool(catalog, used)
                remaining_opp = [
                    r
                    for r in ROLES_ORDER
                    if r
                    not in {normalize_role(s["role"]) for s in opponent_partial}
                ]
                if not remaining_opp:
                    break
                role = rng.choice(remaining_opp)
                champ = _random_opp_pick(pool, role, catalog, used, rng, patch)
                if champ is None:
                    break
                opponent_partial.append({"champion": champ, "role": role})
                used.add(champ.casefold())
                current_slot += 1
                continue
            break

        pool = _available_pool(catalog, used)
        if not pool:
            break

        bot_remaining = [
            r
            for r in ROLES_ORDER
            if r not in {normalize_role(s["role"]) for s in bot_partial}
        ]
        if not bot_remaining:
            break

        draft_depth = len(bot_partial) + len(opponent_partial)
        greedy = draft_depth >= 3 and len(opponent_partial) >= 1

        pick_rng = random.Random(rng.randint(0, 2**31 - 1))
        t0 = time.perf_counter()
        chosen = suggest_bot_pick(
            bot_partial_picks=bot_partial,
            opponent_partial_picks=opponent_partial,
            patch=patch,
            available_champions=pool,
            team_side=bot_side,
            mode="pro",
            rng=pick_rng,
        )
        suggest_ms = (time.perf_counter() - t0) * 1000
        if not chosen.get("champion") or not chosen.get("role"):
            break

        t1 = time.perf_counter()
        pool_by_role, ranked = _evaluate_full_pool(
            bot_partial,
            opponent_partial,
            bot_remaining,
            pool,
            catalog,
            bot_side,
            patch,
        )
        eval_ms = (time.perf_counter() - t1) * 1000

        champ = chosen["champion"]
        role = normalize_role(chosen["role"])
        global_rank = next(
            (r.rank for r in ranked if r.champion == champ and r.role == role),
            -1,
        )
        role_rank = next(
            (
                idx
                for idx, r in enumerate(
                    sorted(
                        [x for x in ranked if x.role == role],
                        key=lambda x: (-x.selection_score, x.champion.casefold()),
                    ),
                    start=1,
                )
                if r.champion == champ
            ),
            -1,
        )
        best_score = ranked[0].selection_score if ranked else 0.0
        chosen_score = float(chosen.get("selection_score", 0))
        gap = best_score - chosen_score if global_rank > 1 else 0.0
        sel_prob = float(chosen.get("selection_probability", 0) or 0)

        audits.append(
            BotPickAudit(
                sim_id=sim_id,
                pick_index=pick_index,
                team_side=bot_side,
                bot_partial=list(bot_partial),
                opponent_partial=list(opponent_partial),
                draft_depth=draft_depth,
                greedy_opponent_active=greedy,
                chosen=dict(chosen),
                pool_by_role=pool_by_role,
                candidates=ranked[:20],
                global_rank=global_rank,
                role_rank=role_rank,
                pool_size=len(ranked),
                is_softmax_pick=sel_prob > 0 and sel_prob < 0.95,
                gap_to_best=round(gap, 2),
                eval_ms=round(eval_ms + suggest_ms, 1),
            )
        )

        bot_partial.append({"champion": champ, "role": role})
        used.add(champ.casefold())

    return audits


def _diversity_stats(all_audits: list[BotPickAudit]) -> dict[str, Any]:
    by_role: dict[str, Counter[str]] = defaultdict(Counter)
    for audit in all_audits:
        by_role[audit.chosen["role"]][audit.chosen["champion"]] += 1

    stats: dict[str, Any] = {}
    for role in ROLES_ORDER:
        counter = by_role.get(role, Counter())
        if not counter:
            continue
        total = sum(counter.values())
        stats[role] = {
            "total_picks": total,
            "unique_champions": len(counter),
            "top3": counter.most_common(3),
            "dominant_pct": round(100 * counter.most_common(1)[0][1] / total, 1),
        }
    return stats


def _flag_incoherent(audit: BotPickAudit) -> list[str]:
    flags: list[str] = []
    chosen = audit.chosen
    champ = chosen["champion"]
    role = normalize_role(chosen["role"])
    meta = chosen.get("meta_score")
    pro_games = chosen.get("pro_games")
    synergy = float(chosen.get("synergy", 0))

    if audit.global_rank > 1 and audit.gap_to_best >= 3.0:
        flags.append(f"not_rank1_large_gap(rank={audit.global_rank},gap={audit.gap_to_best})")

    if audit.is_softmax_pick and audit.global_rank > 3:
        flags.append(f"softmax_low_rank(rank={audit.global_rank},prob={chosen.get('selection_probability')})")

    if meta is not None and meta < 0.35:
        flags.append(f"low_meta_score({meta})")

    if pro_games is not None and pro_games < pro_force.MIN_GAMES_EXCLUSION:
        flags.append(f"below_pool_threshold_games({pro_games})")

    if audit.global_rank == 1 and audit.is_softmax_pick:
        flags.append("rank1_but_softmax_not_deterministic")

    # Off-role in pro data
    fitness = chosen.get("role_fitness")
    if fitness is not None and fitness < 0.25:
        flags.append(f"off_role_fitness({fitness})")

    # Opponent has clear engage comp but bot picks another engage without counter
    opp_champs = [s["champion"] for s in audit.opponent_partial]
    engage_opp = {"Vi", "Nautilus", "Leona", "Alistar", "Renekton", "JarvanIV", "Sejuani"}
    if len(set(opp_champs) & engage_opp) >= 2:
        if champ in engage_opp and audit.chosen.get("opponent_counter_bonus", 0) == 0:
            flags.append("mirrors_engage_comp_no_counter_bonus")

    # Synergy gate bypass (fallback pool)
    if synergy < 0.44 and len(audit.bot_partial) >= 2:
        flags.append(f"low_synergy_pick({synergy:.3f})")

    return flags


def run_audit(n_sims: int, seed: int, patch: str) -> dict[str, Any]:
    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()
    warmup_predict_caches(patch)

    rng = random.Random(seed)
    catalog = get_champion_role_catalog()
    all_audits: list[BotPickAudit] = []
    started = time.perf_counter()

    for sim_id in range(1, n_sims + 1):
        bot_side: TeamSide = rng.choice(["blue", "red"])
        sim_audits = simulate_full_draft(sim_id, rng, catalog, patch, bot_side)
        all_audits.extend(sim_audits)
        if sim_id % 5 == 0:
            print(f"  [{sim_id}/{n_sims}] picks logged: {len(all_audits)}", flush=True)

    elapsed = time.perf_counter() - started
    flagged: list[dict[str, Any]] = []
    rank_distribution = Counter(a.global_rank for a in all_audits)
    softmax_picks = sum(1 for a in all_audits if a.is_softmax_pick)

    for audit in all_audits:
        flags = _flag_incoherent(audit)
        if flags:
            flagged.append(
                {
                    "sim_id": audit.sim_id,
                    "pick_index": audit.pick_index,
                    "flags": flags,
                    "bot_partial": audit.bot_partial,
                    "opponent_partial": audit.opponent_partial,
                    "chosen": audit.chosen,
                    "global_rank": audit.global_rank,
                    "role_rank": audit.role_rank,
                    "gap_to_best": audit.gap_to_best,
                    "top3_candidates": [
                        {
                            "champion": c.champion,
                            "role": c.role,
                            "selection_score": c.selection_score,
                            "win_prob": c.win_prob,
                            "meta_raw": c.meta_raw,
                            "score_opponent_counter": c.score_opponent_counter,
                        }
                        for c in audit.candidates[:3]
                    ],
                }
            )

    low_prob_picks = sum(
        1
        for row in all_audits
        if float(row.chosen.get("selection_probability") or 1) < 0.05
    )

    return {
        "meta": {
            "n_simulations": n_sims,
            "seed": seed,
            "patch": patch,
            "temperature": TEMPERATURE_BOT_PICK,
            "total_bot_picks": len(all_audits),
            "elapsed_seconds": round(elapsed, 1),
            "avg_pick_total_ms": round(
                statistics.mean(a.eval_ms for a in all_audits) if all_audits else 0, 1
            ),
            "low_prob_pick_count": low_prob_picks,
        },
        "diversity": _diversity_stats(all_audits),
        "rank_distribution": dict(sorted(rank_distribution.items())),
        "softmax_pick_count": softmax_picks,
        "softmax_pick_pct": round(
            100 * softmax_picks / len(all_audits) if all_audits else 0, 1
        ),
        "flagged_picks": flagged,
        "all_picks_summary": [
            {
                "sim_id": a.sim_id,
                "pick_index": a.pick_index,
                "chosen": f"{a.chosen['champion']} ({a.chosen['role']})",
                "global_rank": a.global_rank,
                "selection_score": a.chosen.get("selection_score"),
                "selection_probability": a.chosen.get("selection_probability"),
                "win_prob": a.chosen.get("win_probability"),
                "opponent_counter_bonus": a.chosen.get("opponent_counter_bonus"),
                "greedy_opp": a.greedy_opponent_active,
            }
            for a in all_audits
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit pipeline bot draft")
    parser.add_argument("-n", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260726)
    parser.add_argument("--patch", type=str, default=PATCH)
    parser.add_argument(
        "--output",
        type=str,
        default=str(ROOT / "audit_bot_pipeline_output.json"),
    )
    args = parser.parse_args()

    print("=" * 72)
    print(f"AUDIT BOT PIPELINE — {args.n} drafts complets | seed={args.seed}")
    print("=" * 72)

    report = run_audit(args.n, args.seed, args.patch)
    out_path = Path(args.output)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nTerminé en {report['meta']['elapsed_seconds']}s")
    print(f"Picks bot: {report['meta']['total_bot_picks']}")
    print(f"Picks flaggés: {len(report['flagged_picks'])}")
    print(f"Distribution rang: {report['rank_distribution']}")
    print(f"Softmax non-déterministe: {report['softmax_pick_pct']}%")
    print(f"Rapport JSON: {out_path}")


if __name__ == "__main__":
    main()
