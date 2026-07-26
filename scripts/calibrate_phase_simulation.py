"""Calibration empirique des constantes de simulation par phases."""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from match_simulator import (  # noqa: E402
    DRAFT_WEIGHT,
    ENGAGE_BONUS,
    ENGAGE_CAPITALIZE,
    NOISE_WEIGHT,
    PHASE_ADVANTAGE_WEIGHT,
    ROSTER_WEIGHT,
    adjust_phase_probability,
    compute_final_win_probability,
    determine_match_winner,
    pts_to_phase_advantage,
)


def compute_base_player_prob(
    *,
    draft_blue_win_prob: float,
    player_side: str = "blue",
    player_roster_power: float = 0.5,
    opponent_roster_power: float = 0.55,
    noise: float = 0.5,
) -> float:
    return compute_final_win_probability(
        player_side=player_side,  # type: ignore[arg-type]
        draft_blue_win_prob=draft_blue_win_prob,
        player_roster_power=player_roster_power,
        opponent_roster_power=opponent_roster_power,
        noise=noise,
    )


def resolve_phase(*, base: float, phase_advantage: float, choice: str, rng: random.Random) -> bool:
    noise = rng.random()
    prob = adjust_phase_probability(
        base=base,
        phase_advantage=phase_advantage,
        choice=choice,  # type: ignore[arg-type]
        noise=noise,
    )
    return rng.random() < prob


def resolve_match_phases(
    *,
    base: float,
    early_adv: float,
    mid_adv: float,
    late_adv: float,
    early_choice: str,
    mid_choice: str,
    rng: random.Random,
) -> bool:
    early_won = resolve_phase(base=base, phase_advantage=early_adv, choice=early_choice, rng=rng)
    mid_won = resolve_phase(base=base, phase_advantage=mid_adv, choice=mid_choice, rng=rng)
    late_won = resolve_phase(base=base, phase_advantage=late_adv, choice="engage", rng=rng)
    return determine_match_winner(
        phase_results={"early": early_won, "mid": mid_won, "late": late_won},
        base=base,
        rng=rng,
    )


@dataclass
class Scenario:
    name: str
    draft_blue_win_prob: float
    early_pts: float
    mid_pts: float
    late_pts: float


def run_scenario(scenario: Scenario, *, runs: int = 100) -> dict[str, float]:
    early_adv = pts_to_phase_advantage(scenario.early_pts)
    mid_adv = pts_to_phase_advantage(scenario.mid_pts)
    late_adv = pts_to_phase_advantage(scenario.late_pts)
    base = compute_base_player_prob(draft_blue_win_prob=scenario.draft_blue_win_prob)

    combos = {
        "engage_engage": ("engage", "engage"),
        "temporize_temporize": ("temporize", "temporize"),
        "engage_temporize": ("engage", "temporize"),
        "temporize_engage": ("temporize", "engage"),
    }
    rates: dict[str, float] = {"base_player_prob": base}
    for label, (early_choice, mid_choice) in combos.items():
        wins = 0
        for seed in range(runs):
            rng = random.Random(seed)
            if resolve_match_phases(
                base=base,
                early_adv=early_adv,
                mid_adv=mid_adv,
                late_adv=late_adv,
                early_choice=early_choice,
                mid_choice=mid_choice,
                rng=rng,
            ):
                wins += 1
        rates[label] = wins / runs
    return rates


def main() -> None:
    runs = 500
    scenarios = [
        Scenario(
            name="Draft favorable (65%) + bot lane +15 pts",
            draft_blue_win_prob=0.65,
            early_pts=15,
            mid_pts=5,
            late_pts=5,
        ),
        Scenario(
            name="Draft defavorable (35%) + early +15 seulement (mid/late neutres)",
            draft_blue_win_prob=0.35,
            early_pts=15,
            mid_pts=0,
            late_pts=0,
        ),
        Scenario(
            name="Draft defavorable (35%) sans avantage phase",
            draft_blue_win_prob=0.35,
            early_pts=0,
            mid_pts=0,
            late_pts=0,
        ),
        Scenario(
            name="Draft tres defavorable (28%) + engage early seulement",
            draft_blue_win_prob=0.28,
            early_pts=15,
            mid_pts=-10,
            late_pts=-10,
        ),
    ]

    print("=== Calibration simulation par phases ===")
    print(f"DRAFT_WEIGHT={DRAFT_WEIGHT}, ROSTER_WEIGHT={ROSTER_WEIGHT}, NOISE_WEIGHT={NOISE_WEIGHT}")
    print(
        f"PHASE_ADVANTAGE_WEIGHT={PHASE_ADVANTAGE_WEIGHT}, "
        f"ENGAGE_BONUS={ENGAGE_BONUS}, ENGAGE_CAPITALIZE={ENGAGE_CAPITALIZE}"
    )
    print(f"Runs par combinaison: {runs}\n")

    for scenario in scenarios:
        rates = run_scenario(scenario, runs=runs)
        engage_both = rates["engage_engage"]
        tempo_both = rates["temporize_temporize"]
        delta = engage_both - tempo_both
        print(f"--- {scenario.name} ---")
        print(f"  base (player_draft_prob blend): {rates['base_player_prob']:.1%}")
        print(f"  engage + engage:       {engage_both:.1%}")
        print(f"  temporize + temporize: {tempo_both:.1%}")
        print(f"  delta (engage - tempo): {delta:+.1%}")
        print(f"  engage + temporize:    {rates['engage_temporize']:.1%}")
        print(f"  temporize + engage:    {rates['temporize_engage']:.1%}")
        print()


if __name__ == "__main__":
    main()
