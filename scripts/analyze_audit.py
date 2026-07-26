#!/usr/bin/env python3
import json
import sys
from collections import Counter
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else "audit_bot_pipeline_output.json")
data = json.loads(path.read_text(encoding="utf-8"))
flags = data["flagged_picks"]
print(f"=== AUDIT: {path.name} ===")
print("=== FLAG COUNTS ===")
fc = Counter()
for f in flags:
    for flag in f["flags"]:
        fc[flag.split("(")[0]] += 1
for k, v in fc.most_common():
    print(f"  {k}: {v}")

print("\n=== RANK STATS ===")
ranks = [p["global_rank"] for p in data["all_picks_summary"]]
valid = [r for r in ranks if r > 0]
print(
    f"rank1: {sum(1 for r in valid if r == 1)}/{len(valid)} "
    f"({100 * sum(1 for r in valid if r == 1) / len(valid):.1f}%)"
)
print(f"rank>3: {sum(1 for r in valid if r > 3)}")
print(f"rank=-1: {sum(1 for r in ranks if r == -1)}")

low_prob_picks = sum(
    1
    for p in data["all_picks_summary"]
    if (p.get("selection_probability") or 1) < 0.05
)
print(f"\n=== LOW PROB PICKS (<5%): {low_prob_picks} ===")
print("\n=== GREEDY OPP ===")
print(Counter(p["greedy_opp"] for p in data["all_picks_summary"]))

print("\n=== DIVERSITY ===")
for role, stats in data.get("diversity", {}).items():
    print(
        f"  {role}: {stats['unique_champions']} uniques, "
        f"dominant={stats['top3'][0][0]} ({stats['dominant_pct']}%)"
    )

print("\n=== WORST PICKS (top 10) ===")
for p in sorted(
    data["flagged_picks"],
    key=lambda x: (-x["global_rank"], x["chosen"].get("selection_probability") or 1),
)[:10]:
    c = p["chosen"]
    prob = c.get("selection_probability") or 1
    bot = [x["champion"] for x in p["bot_partial"]]
    opp = [x["champion"] for x in p["opponent_partial"]]
    print(
        f"sim{p['sim_id']}#{p['pick_index']}: {c['champion']} ({c['role']}) "
        f"rank={p['global_rank']} prob={prob:.3f} gap={p['gap_to_best']}"
    )
    print(f"  bot={bot} | opp={opp}")
