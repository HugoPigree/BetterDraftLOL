#!/usr/bin/env python3
"""Diagnostic du poids WEIGHT_ARCHETYPE vs autres composantes du score bot."""

from __future__ import annotations

import argparse
import random
import statistics
from collections import Counter, defaultdict
from typing import Any

import predict_draft as pd
from composition_archetype import score_archetype_coherence
from diagnostic_bot_diversity import (
    PATCH,
    _available_pool,
    _random_meta_pick,
    run_diversity_simulations,
)
from suggest_draft import (
    PRO_BOT_DUO_WEIGHT,
    PRO_BOT_META_WEIGHT,
    PRO_BOT_SYNERGY_WEIGHT,
    ROLES_ORDER,
    TEMPERATURE_BOT_PICK,
    WEIGHT_ARCHETYPE,
    decompose_bot_candidate_score,
    get_champion_role_catalog,
    normalize_role,
    suggest_bot_pick,
    warmup_predict_caches,
)

EARLY_DIVE_FOUR = [
    {"champion": "Renekton", "role": "TOP"},
    {"champion": "LeeSin", "role": "JUNGLE"},
    {"champion": "Pantheon", "role": "MIDDLE"},
    {"champion": "Lucian", "role": "BOTTOM"},
]

DEFAULT_OPPONENT = [
    {"champion": "Ornn", "role": "TOP"},
    {"champion": "Vi", "role": "JUNGLE"},
    {"champion": "Azir", "role": "MIDDLE"},
]


def _full_pool() -> list[str]:
    return sorted(get_champion_role_catalog())


def _pool_excluding(*teams: list[dict[str, str]]) -> list[str]:
    used = {slot["champion"].casefold() for team in teams for slot in team}
    return [name for name in _full_pool() if name.casefold() not in used]


def _print_decomposition(title: str, row: dict[str, Any] | None, *, note: str = "") -> None:
    print(f"\n--- {title} ---")
    if note:
        print(f"Note: {note}")
    if row is None:
        print("  (évaluation impossible — rôle/champion incompatible avec le partial)")
        return
    print(f"  Candidat: {row['champion']} ({row['role']})")
    print(f"  winrate raw={row['win_probability']:.4f}  -> score_winrate={row['score_winrate']:+.2f}")
    print(
        f"  synergie ML raw={row['synergy_raw']:.4f}  "
        f"-> score_synergie_ml={row['score_synergy_ml']:+.2f}  (x{PRO_BOT_SYNERGY_WEIGHT})"
    )
    duo_raw = row["duo_raw"]
    print(
        f"  duo raw={duo_raw if duo_raw is not None else 'n/a'}  "
        f"-> score_duo={row['score_duo']:+.2f}  (x{PRO_BOT_DUO_WEIGHT})"
    )
    meta_raw = row["meta_raw"]
    print(
        f"  meta raw={meta_raw if meta_raw is not None else 'n/a'}  "
        f"-> score_meta={row['score_meta']:+.2f}  (x{PRO_BOT_META_WEIGHT})"
    )
    print(f"  duo_bonus={row['score_duo_bonus']:+.2f}")
    print(
        f"  archetype raw={row['archetype_raw']:.4f}  "
        f"-> score_archetype={row['score_archetype']:+.2f}  "
        f"(x{row['weight_archetype']})"
    )
    if row["score_synergy_penalty"]:
        print(f"  synergie_penalty=-{row['score_synergy_penalty']:.2f}")
    print(f"  TOTAL selection_score={row['selection_score']:+.2f}")


def _archetype_only_row(champion: str, team_names: list[str], weight: float) -> dict[str, Any]:
    raw = score_archetype_coherence(team_names, champion)
    weighted = raw * 100.0 * weight
    return {
        "champion": champion,
        "role": "n/a",
        "archetype_raw": raw,
        "score_archetype": round(weighted, 2),
        "weight_archetype": weight,
    }


def section_dive_decomposition(patch: str, weight: float) -> None:
    print("=" * 72)
    print("1. DÉCOMPOSITION — dive early (Renekton/Lee Sin/Pantheon/Lucian) + 5e pick")
    print("=" * 72)

    pool = _pool_excluding(EARLY_DIVE_FOUR, DEFAULT_OPPONENT)
    team_names = [slot["champion"] for slot in EARLY_DIVE_FOUR]

    lulu = decompose_bot_candidate_score(
        EARLY_DIVE_FOUR,
        DEFAULT_OPPONENT,
        "Lulu",
        "UTILITY",
        patch,
        pool,
        weight_archetype=weight,
    )
    _print_decomposition("Lulu (UTILITY — pick valide)", lulu)

    jinx_arch = _archetype_only_row("Jinx", team_names, weight)
    print("\n--- Jinx (liste champions — pas de pick UTILITY valide) ---")
    print(
        "  Note: Jinx n'est pas jouable en UTILITY. Seule la composante archétype "
        "est définie sur la même liste de champions que le test extrême."
    )
    print(
        f"  archetype raw={jinx_arch['archetype_raw']:.4f}  "
        f"-> score_archetype={jinx_arch['score_archetype']:+.2f}  (x{weight})"
    )
    print("  score_winrate / synergie / duo / meta: n/a (pick illégal sur ce partial)")

    if lulu:
        delta_arch = lulu["score_archetype"] - jinx_arch["score_archetype"]
        print(
            f"\n  Écart archétype Lulu vs Jinx (liste): {delta_arch:+.2f} pts "
            f"({lulu['archetype_raw'] - jinx_arch['archetype_raw']:+.4f} raw)"
        )
        other_lulu = (
            lulu["score_winrate"]
            + lulu["score_synergy_ml"]
            + lulu["score_duo"]
            + lulu["score_meta"]
            + lulu["score_duo_bonus"]
            - lulu["score_synergy_penalty"]
        )
        print(
            f"  Autres composantes Lulu (hors archétype): {other_lulu:+.2f} pts "
            f"| archétype Lulu: {lulu['score_archetype']:+.2f} pts "
            f"({100 * lulu['score_archetype'] / lulu['selection_score']:.1f}% du total)"
        )


def section_weight_sensitivity(patch: str) -> None:
    print("\n" + "=" * 72)
    print("4. SENSIBILITÉ DU POIDS — cas extrême Lulu vs Jinx (composante archétype)")
    print("=" * 72)
    team_names = [slot["champion"] for slot in EARLY_DIVE_FOUR]
    lulu_raw = score_archetype_coherence(team_names, "Lulu")
    jinx_raw = score_archetype_coherence(team_names, "Jinx")
    for weight in (0.18, 0.10, 0.08):
        delta = (lulu_raw - jinx_raw) * 100.0 * weight
        print(
            f"  WEIGHT={weight:.2f}  -> écart archétype Lulu-Jinx: {delta:+.2f} pts "
            f"(Lulu={lulu_raw * 100 * weight:+.2f}, Jinx={jinx_raw * 100 * weight:+.2f})"
        )


def collect_simulation_contributions(
    n_per_seed: int,
    seeds: list[int],
    patch: str,
    weight: float,
) -> tuple[list[dict[str, Any]], list[float], list[float]]:
    rows: list[dict[str, Any]] = []
    candidate_arch_weights: list[float] = []
    decision_arch_spreads: list[float] = []
    catalog = get_champion_role_catalog()

    from composition_archetype import score_archetype_coherence
    from suggest_draft import _top_candidates_for_role, BOT_CANDIDATES_PER_ROLE

    for seed in seeds:
        rng = random.Random(seed)
        for _ in range(n_per_seed):
            used: set[str] = set()
            bot_partial: list[dict[str, str]] = []
            opponent_partial: list[dict[str, str]] = []
            team_side = rng.choice(["blue", "red"])

            for _ in range(rng.randint(0, 2)):
                pool = _available_pool(catalog, used)
                role = rng.choice(ROLES_ORDER)
                champ = _random_meta_pick(pool, role, catalog, used, rng, patch)
                if champ is None:
                    continue
                opponent_partial.append({"champion": champ, "role": role})
                used.add(champ.casefold())

            for _ in range(rng.randint(0, 2)):
                pool = _available_pool(catalog, used)
                remaining = [
                    r
                    for r in ROLES_ORDER
                    if r not in {normalize_role(s["role"]) for s in bot_partial}
                ]
                if not remaining:
                    break
                role = rng.choice(remaining)
                champ = _random_meta_pick(pool, role, catalog, used, rng, patch)
                if champ is None:
                    continue
                bot_partial.append({"champion": champ, "role": role})
                used.add(champ.casefold())

            pool = _available_pool(catalog, used)
            if not pool:
                continue

            team_names = [slot["champion"] for slot in bot_partial]
            remaining_roles = [
                r
                for r in ROLES_ORDER
                if r not in {normalize_role(s["role"]) for s in bot_partial}
            ]
            per_decision_weights: list[float] = []
            for role in remaining_roles:
                for candidate in _top_candidates_for_role(
                    pool, role, catalog, patch, "pro", BOT_CANDIDATES_PER_ROLE
                ):
                    arch = score_archetype_coherence(team_names, candidate)
                    weighted = arch * 100.0 * weight
                    candidate_arch_weights.append(weighted)
                    per_decision_weights.append(weighted)
            if per_decision_weights:
                decision_arch_spreads.append(
                    max(per_decision_weights) - min(per_decision_weights)
                )

            choice = suggest_bot_pick(
                bot_partial_picks=bot_partial,
                opponent_partial_picks=opponent_partial,
                patch=patch,
                available_champions=pool,
                team_side=team_side,
                mode="pro",
                rng=rng,
            )
            champion = choice.get("champion")
            role = choice.get("role")
            if not champion or not role:
                continue

            win_prob = float(choice.get("win_probability") or 0.0)
            synergy = float(choice.get("synergy") or 0.0)
            meta_raw = choice.get("meta_score")
            arch_raw = float(choice.get("archetype_score") or 0.0)

            rows.append(
                {
                    "seed": seed,
                    "champion": champion,
                    "role": role,
                    "bot_picks_before": len(bot_partial),
                    "selection_score": float(choice.get("selection_score") or 0.0),
                    "score_winrate": win_prob * 100.0,
                    "score_synergy_ml": synergy * 100.0 * PRO_BOT_SYNERGY_WEIGHT,
                    "score_meta": float(meta_raw or 0.0) * 100.0 * PRO_BOT_META_WEIGHT,
                    "score_archetype": arch_raw * 100.0 * weight,
                    "archetype_raw": arch_raw,
                }
            )
    return rows, candidate_arch_weights, decision_arch_spreads


def section_simulation_distribution(
    rows: list[dict[str, Any]],
    candidate_arch_weights: list[float],
    decision_arch_spreads: list[float],
    weight: float,
) -> None:
    print("\n" + "=" * 72)
    print(f"3. DISTRIBUTION — {len(rows)} picks bot (diagnostic diversité, T={TEMPERATURE_BOT_PICK})")
    print("=" * 72)

    if not rows:
        print("Aucune simulation enregistrée.")
        return

    def stats(values: list[float]) -> str:
        return (
            f"moy={statistics.mean(values):+.2f}  "
            f"std={statistics.pstdev(values):.2f}  "
            f"min={min(values):+.2f}  max={max(values):+.2f}"
        )

    arch = [row["score_archetype"] for row in rows]
    meta = [row["score_meta"] for row in rows]
    syn = [row["score_synergy_ml"] for row in rows]
    win = [row["score_winrate"] for row in rows]
    total = [row["selection_score"] for row in rows]

    print(f"  score_archetype (x{weight}): {stats(arch)}")
    print(f"  score_meta (x{PRO_BOT_META_WEIGHT}):     {stats(meta)}")
    print(f"  score_synergie_ml (x{PRO_BOT_SYNERGY_WEIGHT}): {stats(syn)}")
    print(f"  score_winrate:              {stats(win)}")
    print(f"  selection_score total:      {stats(total)}")

    mean_arch = statistics.mean(arch)
    mean_meta = statistics.mean(meta)
    print(
        f"\n  Contribution moyenne archétype (pick choisi): {mean_arch:+.2f} pts "
        f"({100 * mean_arch / statistics.mean(total):.1f}% du score total moyen)"
    )
    print(
        f"  std meta={statistics.pstdev(meta):.2f}  std synergie={statistics.pstdev(syn):.2f}  "
        f"std archetype (choisi)={statistics.pstdev(arch):.2f}"
    )

    if candidate_arch_weights:
        print(
            f"\n  Pool candidats (tous roles/picks evalues): "
            f"moy={statistics.mean(candidate_arch_weights):+.2f}  "
            f"std={statistics.pstdev(candidate_arch_weights):.2f}  "
            f"min={min(candidate_arch_weights):+.2f}  max={max(candidate_arch_weights):+.2f}"
        )
    if decision_arch_spreads:
        print(
            f"  Ecart archétype max-min par decision: "
            f"moy={statistics.mean(decision_arch_spreads):+.2f}  "
            f"std={statistics.pstdev(decision_arch_spreads):.2f}  "
            f"max={max(decision_arch_spreads):+.2f}"
        )

    mean_spread = statistics.mean(decision_arch_spreads) if decision_arch_spreads else 0.0
    print(
        "\n  Interpretation: la moyenne sur picks choisis peut etre haute (+18) "
        "tout en etant un offset commun (souvent archetype_raw=1.0 sur partials courts). "
        "L'ecart discriminant reel est max-min par decision."
    )

    if mean_spread < 5.0:
        print(
            f"  -> Ecart moyen {mean_spread:.2f} pts (< 5): en draft typique l'archétype "
            "ne domine pas le classement. Le cas extrême reste un outlier."
        )
        if mean_arch >= 5.0:
            print(
                "  -> Poids 0.18 acceptable: penalite forte sur comps polarisees, "
                "neutre sur la plupart des tours."
            )
    elif mean_spread >= statistics.pstdev(meta) * 0.8:
        print(
            "\n  -> Ecart archétype comparable au meta: risque d'ecraser le signal meta "
            "— envisager 0.08-0.10."
        )
    else:
        print("\n  -> Contribution archétype non négligeable; vérifier cas extrêmes.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostic WEIGHT_ARCHETYPE")
    parser.add_argument("--patch", default=PATCH)
    parser.add_argument("--weight", type=float, default=WEIGHT_ARCHETYPE)
    parser.add_argument("--simulations", type=int, default=30)
    parser.add_argument("--seeds", default="42,123,999")
    args = parser.parse_args()

    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()
    warmup_predict_caches(args.patch)

    section_dive_decomposition(args.patch, args.weight)

    seed_list = [int(part.strip()) for part in args.seeds.split(",") if part.strip()]
    rows, candidate_arch, spreads = collect_simulation_contributions(
        args.simulations, seed_list, args.patch, args.weight
    )
    section_simulation_distribution(rows, candidate_arch, spreads, args.weight)
    section_weight_sensitivity(args.patch)


if __name__ == "__main__":
    main()
