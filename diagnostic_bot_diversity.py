#!/usr/bin/env python3
"""Diagnostic diversité et scoring du bot de draft (suggest_bot_pick).

Simule des drafts variés, mesure la répétition des picks par rôle,
et compare les scores des candidats meta-filtrés sur plusieurs contextes.
"""

from __future__ import annotations

import argparse
import random
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

import predict_draft as pd
from pro_force import is_pro_viable_on_role
from suggest_draft import (
    BOT_CANDIDATES_PER_ROLE,
    PRO_MIN_SYNERGY_AFTER_TWO_PICKS,
    ROLES_ORDER,
    TeamSide,
    _bot_pick_selection_score,
    _locked_pro_duo_bonus,
    _pro_meta_score_for,
    _pro_winrate_entry,
    _rank_pro_for_role,
    _top_candidates_for_role,
    build_matchup_teams,
    build_simulated_team_with_pick,
    build_team_with_meta_fillers,
    champions_playable_on_role,
    get_champion_role_catalog,
    get_meraki_context,
    normalize_role,
    predict_draft,
    slots_to_team,
    team_side_win_probability,
    warmup_predict_caches,
)

PATCH = "16.13"
DEFAULT_SIMULATIONS = 20
CONTEXT_ROLES_TO_ANALYZE = ("JUNGLE", "UTILITY", "BOTTOM")


@dataclass
class CandidateEval:
    champion: str
    role: str
    selection_score: float
    win_prob: float
    synergy: float
    meta_score: float | None
    locked_duo_bonus: float


@dataclass
class ContextEval:
    label: str
    bot_partial: list[dict[str, str]]
    opponent_partial: list[dict[str, str]]
    target_role: str
    candidates: list[CandidateEval]


def _available_pool(
    catalog: dict[str, list[str]],
    used: set[str],
) -> list[str]:
    return sorted(
        [name for name in catalog if name.casefold() not in used],
        key=str.casefold,
    )


def _random_meta_pick(
    pool: list[str],
    role: str,
    catalog: dict[str, list[str]],
    reserved: set[str],
    rng: random.Random,
) -> str | None:
    playable = [
        name
        for name in champions_playable_on_role(pool, role, catalog)
        if name.casefold() not in reserved
    ]
    if not playable:
        return None
    ranked = _rank_pro_for_role(playable, role)
    top = [name for _, _, _, _, name in ranked[:8]]
    if not top:
        return None
    return rng.choice(top)


def _evaluate_role_candidates(
    bot_partial: list[dict[str, str]],
    opponent_partial: list[dict[str, str]],
    role: str,
    pool: list[str],
    catalog: dict[str, list[str]],
    team_side: TeamSide,
    patch: str,
    champion_features: dict[str, Any],
    lookup_by_norm: dict[str, str],
    *,
    candidates_per_role: int = BOT_CANDIDATES_PER_ROLE,
) -> list[CandidateEval]:
    bot_partial = slots_to_team(bot_partial)
    opponent_partial = slots_to_team(opponent_partial)
    role = normalize_role(role)

    reserved = {
        slot["champion"].casefold()
        for slot in bot_partial + opponent_partial
    }
    bot_remaining = [
        r
        for r in ROLES_ORDER
        if r not in {normalize_role(s["role"]) for s in bot_partial}
    ]
    if role not in bot_remaining:
        return []

    opponent_remaining = [
        r
        for r in ROLES_ORDER
        if r not in {normalize_role(s["role"]) for s in opponent_partial}
    ] or ROLES_ORDER.copy()

    locked_picks = len(bot_partial)
    candidates = _top_candidates_for_role(
        pool, role, catalog, patch, "pro", candidates_per_role
    )
    candidates = [
        name
        for name in candidates
        if is_pro_viable_on_role(name, role, champion_features, lookup_by_norm)
    ] or candidates[:3]

    results: list[CandidateEval] = []
    for candidate in candidates:
        meta_scored = _pro_meta_score_for(candidate, role)
        candidate_meta = meta_scored[0] if meta_scored else None
        locked_duo_bonus = _locked_pro_duo_bonus(bot_partial, candidate, role)

        trial_reserved = reserved | {candidate.casefold()}
        bot_full = build_simulated_team_with_pick(
            partial_picks=bot_partial,
            candidate=candidate,
            candidate_role=role,
            remaining_roles=bot_remaining,
            catalog=catalog,
            available_champions=pool,
            reserved=trial_reserved,
            patch=patch,
            mode="pro",
        )
        if bot_full is None:
            continue

        used_for_opp = trial_reserved | {
            slot["champion"].casefold() for slot in bot_full
        }
        opponent_full = build_team_with_meta_fillers(
            partial_picks=opponent_partial,
            remaining_roles=opponent_remaining,
            catalog=catalog,
            available_champions=pool,
            reserved=used_for_opp,
            patch=patch,
            mode="pro",
        )
        if opponent_full is None:
            continue

        mod_blue, mod_red = build_matchup_teams(bot_full, opponent_full, team_side)
        result = predict_draft(mod_blue, mod_red, patch=patch, mode="pro")
        win_prob = team_side_win_probability(result, team_side)
        detail = result["blue"] if team_side == "blue" else result["red"]
        synergy = float(detail["score_synergie"])

        min_synergy = PRO_MIN_SYNERGY_AFTER_TWO_PICKS if locked_picks >= 2 else 0.40
        if locked_picks >= 1 and synergy < min_synergy:
            continue

        selection_score = _bot_pick_selection_score(
            result,
            team_side,
            "pro",
            locked_picks,
            candidate_meta=candidate_meta,
            locked_duo_bonus=locked_duo_bonus,
        )
        results.append(
            CandidateEval(
                champion=candidate,
                role=role,
                selection_score=selection_score,
                win_prob=win_prob,
                synergy=synergy,
                meta_score=candidate_meta,
                locked_duo_bonus=locked_duo_bonus,
            )
        )

    results.sort(key=lambda item: (-item.selection_score, item.champion.casefold()))
    return results


def _simulate_bot_pick_turn(
    bot_partial: list[dict[str, str]],
    opponent_partial: list[dict[str, str]],
    pool: list[str],
    catalog: dict[str, list[str]],
    team_side: TeamSide,
    patch: str,
) -> dict[str, Any]:
    from suggest_draft import suggest_bot_pick

    return suggest_bot_pick(
        bot_partial_picks=bot_partial,
        opponent_partial_picks=opponent_partial,
        patch=patch,
        available_champions=pool,
        team_side=team_side,
        mode="pro",
    )


def run_diversity_simulations(
    n_simulations: int,
    seed: int,
    patch: str,
) -> tuple[dict[str, Counter[str]], list[dict[str, Any]]]:
    rng = random.Random(seed)
    catalog = get_champion_role_catalog()
    picks_by_role: dict[str, Counter[str]] = defaultdict(Counter)
    simulation_log: list[dict[str, Any]] = []

    for sim_index in range(1, n_simulations + 1):
        used: set[str] = set()
        bot_partial: list[dict[str, str]] = []
        opponent_partial: list[dict[str, str]] = []
        team_side: TeamSide = rng.choice(["blue", "red"])

        n_opp_starts = rng.randint(0, 2)
        for _ in range(n_opp_starts):
            pool = _available_pool(catalog, used)
            role = rng.choice(ROLES_ORDER)
            champ = _random_meta_pick(pool, role, catalog, used, rng)
            if champ is None:
                continue
            opponent_partial.append({"champion": champ, "role": role})
            used.add(champ.casefold())

        n_bot_starts = rng.randint(0, 2)
        for _ in range(n_bot_starts):
            pool = _available_pool(catalog, used)
            remaining = [
                r
                for r in ROLES_ORDER
                if r not in {normalize_role(s["role"]) for s in bot_partial}
            ]
            if not remaining:
                break
            role = rng.choice(remaining)
            champ = _random_meta_pick(pool, role, catalog, used, rng)
            if champ is None:
                continue
            bot_partial.append({"champion": champ, "role": role})
            used.add(champ.casefold())

        pool = _available_pool(catalog, used)
        if not pool:
            continue

        choice = _simulate_bot_pick_turn(
            bot_partial, opponent_partial, pool, catalog, team_side, patch
        )
        champion = choice.get("champion")
        role = choice.get("role")
        if not champion or not role:
            continue

        picks_by_role[normalize_role(role)][champion] += 1
        simulation_log.append(
            {
                "sim": sim_index,
                "team_side": team_side,
                "bot_partial": list(bot_partial),
                "opponent_partial": list(opponent_partial),
                "pick": champion,
                "role": normalize_role(role),
                "selection_score": choice.get("selection_score"),
                "synergy": choice.get("synergy"),
            }
        )

    return picks_by_role, simulation_log


def build_fixed_contexts(
    catalog: dict[str, list[str]],
    rng: random.Random,
) -> list[ContextEval]:
    """3 contextes distincts pour comparer les top candidats sur un même rôle."""
    champion_features, _, lookup_by_norm = get_meraki_context()
    contexts: list[ContextEval] = []

    presets: list[tuple[str, list[dict[str, str]], list[dict[str, str]], str]] = [
        # JUNGLE x3
        (
            "jg_engage",
            [{"champion": "Renekton", "role": "TOP"}, {"champion": "Nautilus", "role": "UTILITY"}],
            [{"champion": "Azir", "role": "MIDDLE"}, {"champion": "Caitlyn", "role": "BOTTOM"}],
            "JUNGLE",
        ),
        (
            "jg_scaling",
            [{"champion": "K'Sante", "role": "TOP"}, {"champion": "Orianna", "role": "MIDDLE"}],
            [{"champion": "Gnar", "role": "TOP"}, {"champion": "Ahri", "role": "MIDDLE"}],
            "JUNGLE",
        ),
        (
            "jg_skirmish",
            [{"champion": "Rumble", "role": "TOP"}, {"champion": "Taliyah", "role": "MIDDLE"}],
            [{"champion": "Renekton", "role": "TOP"}, {"champion": "Syndra", "role": "MIDDLE"}],
            "JUNGLE",
        ),
        # UTILITY x3
        (
            "sup_engage",
            [{"champion": "Renekton", "role": "TOP"}, {"champion": "Vi", "role": "JUNGLE"}],
            [{"champion": "Azir", "role": "MIDDLE"}, {"champion": "Caitlyn", "role": "BOTTOM"}],
            "UTILITY",
        ),
        (
            "sup_protect",
            [{"champion": "K'Sante", "role": "TOP"}, {"champion": "Orianna", "role": "MIDDLE"}, {"champion": "Jinx", "role": "BOTTOM"}],
            [{"champion": "Gnar", "role": "TOP"}],
            "UTILITY",
        ),
        (
            "sup_bot_lane",
            [{"champion": "Rumble", "role": "TOP"}, {"champion": "Nocturne", "role": "JUNGLE"}],
            [{"champion": "Ahri", "role": "MIDDLE"}, {"champion": "Ashe", "role": "BOTTOM"}],
            "UTILITY",
        ),
        # BOTTOM x3
        (
            "adc_engage",
            [{"champion": "Renekton", "role": "TOP"}, {"champion": "Vi", "role": "JUNGLE"}, {"champion": "Nautilus", "role": "UTILITY"}],
            [{"champion": "Syndra", "role": "MIDDLE"}],
            "BOTTOM",
        ),
        (
            "adc_scaling",
            [{"champion": "K'Sante", "role": "TOP"}, {"champion": "Orianna", "role": "MIDDLE"}, {"champion": "Karma", "role": "UTILITY"}],
            [{"champion": "Ahri", "role": "MIDDLE"}],
            "BOTTOM",
        ),
        (
            "adc_skirmish",
            [{"champion": "Rumble", "role": "TOP"}, {"champion": "Taliyah", "role": "MIDDLE"}],
            [{"champion": "Renekton", "role": "TOP"}, {"champion": "Syndra", "role": "MIDDLE"}],
            "BOTTOM",
        ),
    ]

    for label, bot_partial, opponent_partial, target_role in presets:
        used = {
            slot["champion"].casefold()
            for slot in bot_partial + opponent_partial
        }
        pool = _available_pool(catalog, used)
        candidates = _evaluate_role_candidates(
            bot_partial,
            opponent_partial,
            target_role,
            pool,
            catalog,
            team_side="red",
            patch=PATCH,
            champion_features=champion_features,
            lookup_by_norm=lookup_by_norm,
        )
        contexts.append(
            ContextEval(
                label=label,
                bot_partial=bot_partial,
                opponent_partial=opponent_partial,
                target_role=target_role,
                candidates=candidates,
            )
        )

    return contexts


def _analyze_context_scores(contexts: list[ContextEval]) -> None:
    print("\n=== Comparaison top-3 candidats sur 3 contextes fixes ===\n")

    by_role: dict[str, list[ContextEval]] = defaultdict(list)
    for ctx in contexts:
        by_role[ctx.target_role].append(ctx)

    for role in CONTEXT_ROLES_TO_ANALYZE:
        role_contexts = by_role.get(role, [])
        if not role_contexts:
            continue

        print(f"--- Rôle {role} ---")
        winners: list[str] = []
        for ctx in role_contexts:
            top3 = ctx.candidates[:3]
            if not top3:
                print(f"  [{ctx.label}] aucun candidat évaluable")
                continue

            winner = top3[0].champion
            winners.append(winner)
            gap = top3[0].selection_score - top3[1].selection_score if len(top3) > 1 else 999.0
            spread = top3[0].selection_score - top3[-1].selection_score

            print(f"  [{ctx.label}] bot={len(ctx.bot_partial)} picks adverses={len(ctx.opponent_partial)}")
            for rank, cand in enumerate(top3, start=1):
                meta_label = f"{cand.meta_score:.3f}" if cand.meta_score is not None else "n/a"
                print(
                    f"    #{rank} {cand.champion}: score={cand.selection_score:.2f} "
                    f"(win={cand.win_prob:.1%}, syn={cand.synergy:.3f}, "
                    f"meta={meta_label}, duo_bonus={cand.locked_duo_bonus:.1f})"
                )
            print(f"    -> gagnant={winner}, ecart #1-#2={gap:.2f} pt, spread top3={spread:.2f} pt")

        if len(set(winners)) == 1 and len(winners) >= 2:
            avg_gap = statistics.mean([
                ctx.candidates[0].selection_score - ctx.candidates[1].selection_score
                for ctx in role_contexts
                if len(ctx.candidates) >= 2
            ]) if role_contexts else 0.0
            if avg_gap < 1.0:
                print(
                    f"  [!] Meme gagnant ({winners[0]}) sur {len(winners)} contextes "
                    f"avec ecarts moyens serres ({avg_gap:.2f} pt) "
                    "-> probleme de selection deterministe (argmax), pas biais meta fort."
                )
            else:
                print(
                    f"  [!] Meme gagnant ({winners[0]}) sur {len(winners)} contextes "
                    f"avec ecarts moyens larges ({avg_gap:.2f} pt) "
                    "-> biais structurel du modele (meta domine)."
                )
        elif winners:
            print(f"  Gagnants variés: {', '.join(winners)}")

        synergy_by_champion: dict[str, list[float]] = defaultdict(list)
        for ctx in role_contexts:
            for cand in ctx.candidates[:5]:
                synergy_by_champion[cand.champion].append(cand.synergy)

        varying = [
            (champ, scores)
            for champ, scores in synergy_by_champion.items()
            if len(scores) >= 2 and (max(scores) - min(scores)) >= 0.005
        ]
        if varying:
            print("  Synergie contextuelle (même champion, contextes différents):")
            for champ, scores in sorted(varying, key=lambda x: -max(x[1]) - min(x[1]))[:5]:
                print(
                    f"    {champ}: min={min(scores):.4f} max={max(scores):.4f} "
                    f"d={max(scores)-min(scores):.4f}"
                )
        else:
            print(
                "  [!] Peu ou pas de variation de synergie entre contextes "
                "(synergie quasi absolue par champion ?)."
            )
        print()


def _analyze_synergy_contextuality(
    catalog: dict[str, list[str]],
    champion_features: dict[str, Any],
    lookup_by_norm: dict[str, str],
) -> None:
    """Test explicite : un candidat a-t-il des scores de synergie différents selon la comp ?"""
    print("\n=== Test synergie contextuelle (même candidat, 2 comps partielles) ===\n")

    test_cases = [
        (
            "Nautilus UTILITY",
            "Nautilus",
            "UTILITY",
            [{"champion": "Vi", "role": "JUNGLE"}, {"champion": "Caitlyn", "role": "BOTTOM"}],
            [{"champion": "Azir", "role": "MIDDLE"}, {"champion": "Jhin", "role": "BOTTOM"}],
            [],
            [{"champion": "Renekton", "role": "TOP"}],
        ),
        (
            "Vi JUNGLE",
            "Vi",
            "JUNGLE",
            [{"champion": "Renekton", "role": "TOP"}, {"champion": "Nautilus", "role": "UTILITY"}],
            [{"champion": "K'Sante", "role": "TOP"}, {"champion": "Karma", "role": "UTILITY"}],
            [{"champion": "Ahri", "role": "MIDDLE"}],
            [{"champion": "Syndra", "role": "MIDDLE"}],
        ),
    ]

    for label, champion, role, bot_a, bot_b, opp_a, opp_b in test_cases:
        used_a = {s["champion"].casefold() for s in bot_a + opp_a}
        used_b = {s["champion"].casefold() for s in bot_b + opp_b}
        pool_a = _available_pool(catalog, used_a)
        pool_b = _available_pool(catalog, used_b)

        eval_a = _evaluate_role_candidates(
            bot_a, opp_a, role, pool_a, catalog, "blue", PATCH,
            champion_features, lookup_by_norm,
        )
        eval_b = _evaluate_role_candidates(
            bot_b, opp_b, role, pool_b, catalog, "blue", PATCH,
            champion_features, lookup_by_norm,
        )

        syn_a = next((c.synergy for c in eval_a if c.champion == champion), None)
        syn_b = next((c.synergy for c in eval_b if c.champion == champion), None)

        if syn_a is None or syn_b is None:
            print(f"  {label}: données insuffisantes")
            continue

        delta = abs(syn_a - syn_b)
        print(
            f"  {label}: synergie comp A={syn_a:.4f}, comp B={syn_b:.4f}, "
            f"d={delta:.4f} {'OK contextuel' if delta >= 0.01 else '[!] quasi identique'}"
        )


def _print_frequency_report(picks_by_role: dict[str, Counter[str]], n_simulations: int) -> None:
    print(f"\n=== Fréquence des picks bot ({n_simulations} simulations) ===\n")

    for role in ROLES_ORDER:
        counter = picks_by_role.get(role, Counter())
        if not counter:
            print(f"  {role}: aucun pick enregistré")
            continue

        total = sum(counter.values())
        unique = len(counter)
        top = counter.most_common(5)
        dominant, dominant_count = top[0]
        dominant_pct = 100.0 * dominant_count / total

        print(f"  {role} ({total} picks, {unique} champions uniques):")
        for champ, count in top:
            bar = "#" * int(20 * count / total)
            print(f"    {champ:18s} {count:2d} ({100*count/total:5.1f}%) {bar}")

        if dominant_pct >= 60:
            print(
                f"    [!] Dominance forte: {dominant} = {dominant_pct:.0f}% "
                "(repetition systematique probable)"
            )
        elif unique <= 2:
            print(f"    [!] Faible diversite: seulement {unique} champions differents")
        print()


def _print_diagnosis_summary(
    picks_by_role: dict[str, Counter[str]],
    contexts: list[ContextEval],
    n_simulations: int,
) -> None:
    print("\n" + "=" * 72)
    print("SYNTHÈSE DIAGNOSTIC")
    print("=" * 72)

    issues: list[str] = []

    for role in ROLES_ORDER:
        counter = picks_by_role.get(role, Counter())
        if not counter:
            continue
        total = sum(counter.values())
        dominant_pct = 100.0 * counter.most_common(1)[0][1] / total
        if dominant_pct >= 50:
            issues.append(
                f"Repetition: {role} -> {counter.most_common(1)[0][0]} "
                f"dans {dominant_pct:.0f}% des cas"
            )

    large_gaps = 0
    tight_same_winner = 0
    for ctx in contexts:
        top3 = ctx.candidates[:3]
        if len(top3) < 2:
            continue
        gap = top3[0].selection_score - top3[1].selection_score
        if gap >= 3.0:
            large_gaps += 1
        elif gap < 1.0:
            tight_same_winner += 1

    if large_gaps >= 2:
        issues.append(
            f"Biais structurel meta: ecart #1-#2 >= 3 pt sur {large_gaps} contextes "
            "(le meta score domine probablement la selection)"
        )
    if tight_same_winner >= 2:
        issues.append(
            f"Selection deterministe: scores serres (<1 pt) mais argmax strict "
            f"sur {tight_same_winner} contextes -> softmax recommande"
        )

    synergy_flat = True
    for ctx in contexts:
        for cand in ctx.candidates[:3]:
            if cand.synergy and abs(cand.synergy - 0.5) > 0.02:
                synergy_flat = False
    if synergy_flat:
        issues.append(
            "Synergie ML peu discriminante entre candidats top "
            "(fillers meta identiques par role -> score comp quasi constant ?)"
        )

    filler_dominance = any(
        ctx.candidates
        and ctx.candidates[0].meta_score
        and ctx.candidates[0].meta_score > 0.7
        and (len(ctx.candidates) < 2 or ctx.candidates[0].selection_score - ctx.candidates[1].selection_score > 2)
        for ctx in contexts
    )
    if filler_dominance:
        issues.append(
            "Les fillers meta pour completer la simulation ecrasent peut-etre "
            "les differences de synergie entre candidats"
        )

    if not issues:
        print("Aucun signal d'alarme majeur détecté sur cet échantillon.")
    else:
        print("Causes probables identifiées:")
        for index, issue in enumerate(issues, start=1):
            print(f"  {index}. {issue}")

    print("\nRecommandations (Parties 2-5 du plan):")
    print("  • Partie 2: pool meta strict get_meta_pool_for_role()")
    print("  • Partie 3: synergie sur comp partielle reelle + archetype de comp")
    print("  • Partie 4: softmax TEMPERATURE_BOT_PICK si scores serres")
    print("  • Partie 5: justifications holistiques meta -> archetype -> duo -> stats")
    print("=" * 72)


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostic diversité bot draft")
    parser.add_argument("-n", "--simulations", type=int, default=DEFAULT_SIMULATIONS)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--patch", type=str, default=PATCH)
    args = parser.parse_args()

    pd.reset_predict_state()
    pd.initialize_blue_side_winrate()
    warmup_predict_caches(args.patch)

    print("=" * 72)
    print("DIAGNOSTIC BOT DRAFT — suggest_bot_pick()")
    print(f"Simulations: {args.simulations} | Seed: {args.seed} | Patch: {args.patch}")
    print("=" * 72)

    picks_by_role, sim_log = run_diversity_simulations(
        args.simulations, args.seed, args.patch
    )
    _print_frequency_report(picks_by_role, args.simulations)

    catalog = get_champion_role_catalog()
    rng = random.Random(args.seed + 999)
    contexts = build_fixed_contexts(catalog, rng)
    _analyze_context_scores(contexts)

    champion_features, _, lookup_by_norm = get_meraki_context()
    _analyze_synergy_contextuality(catalog, champion_features, lookup_by_norm)

    _print_diagnosis_summary(picks_by_role, contexts, args.simulations)

    print(f"\n({len(sim_log)} décisions bot enregistrées sur {args.simulations} simulations)")


if __name__ == "__main__":
    main()
