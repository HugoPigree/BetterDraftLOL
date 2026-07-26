#!/usr/bin/env python3
"""Profile suggest_bot_pick() sur 5 appels consécutifs (diagnostic latence bot)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from draft_profiling import begin_profile, end_profile, log_batch_summary, log_report
from predict_draft import (
    initialize_blue_side_winrate,
    reset_predict_state,
    setup_logging,
    warmup_all_server_caches,
)
from suggest_draft import get_champion_role_catalog, suggest_bot_pick

PATCH = "16.13"
CALLS = 5

# Draft partielle réaliste : bot red, 2 picks de chaque côté
BOT_PARTIAL = [
    {"champion": "Renekton", "role": "TOP"},
    {"champion": "Vi", "role": "JUNGLE"},
]
OPPONENT_PARTIAL = [
    {"champion": "Gnar", "role": "TOP"},
    {"champion": "Sejuani", "role": "JUNGLE"},
]


def simulate_api_startup() -> None:
    """Reproduit le lifespan FastAPI : reset + blue side WR + warmup complet."""
    reset_predict_state()
    initialize_blue_side_winrate()
    warmup_ms = warmup_all_server_caches(PATCH)
    print(f"Warmup serveur simulé : {warmup_ms:.1f} ms\n")


def main() -> None:
    setup_logging(verbose=False)
    logging.getLogger("draft_profiling").setLevel(logging.INFO)
    logging.getLogger("suggest_draft").setLevel(logging.WARNING)
    logging.getLogger("champion_catalog").setLevel(logging.WARNING)

    print("\n=== Profiling bot pick — 5 appels consécutifs ===")
    print("Simulation lifespan FastAPI (reset + warmup complet) puis 5 picks bot.\n")

    simulate_api_startup()
    available = sorted(get_champion_role_catalog().keys(), key=str.casefold)

    reports = []
    picks = []

    for index in range(1, CALLS + 1):
        label = f"suggest_bot_pick #{index} (bot_partial={len(BOT_PARTIAL)} picks)"
        begin_profile(label)
        choice = suggest_bot_pick(
            bot_partial_picks=BOT_PARTIAL,
            opponent_partial_picks=OPPONENT_PARTIAL,
            patch=PATCH,
            available_champions=available,
            team_side="red",
            mode="pro",
            rng_seed=1000 + index,
        )
        report = end_profile()
        if report is None:
            raise RuntimeError("Profil manquant après suggest_bot_pick")
        reports.append(report)
        picks.append(choice)
        log_report(report, header=f"--- Appel {index}/{CALLS} ---")

    log_batch_summary(
        reports,
        title="SYNTHÈSE — 5 appels consécutifs suggest_bot_pick()",
    )

    print("\nPicks choisis :")
    for index, choice in enumerate(picks, start=1):
        champion = choice.get("champion")
        role = choice.get("role")
        print(f"  #{index}: {champion} ({role})")


if __name__ == "__main__":
    main()
