"""Summarize final success / failures-at-change across seed runs.  Usage: python scripts/seed_summary.py out/sweep_0 out/sweep_1 ..."""
import json, sys
import numpy as np
runs = [json.load(open(p.rstrip("/") + "/loop_result.json")) for p in sys.argv[1:]]
n_rounds = max(len(r["rounds"]) for r in runs)
print(f"| round | success right after the change (mean ± sd, n={len(runs)}) | success after repair | repairs |")
print("|---|---|---|---|")
for i in range(n_rounds):
    after = [next(m["success_rate"] for m in r["timeline"] if m.get("round") == i + 1 and m.get("phase") == "after_change") for r in runs if len(r["rounds"]) > i]
    final = [r["rounds"][i]["final_success"] for r in runs if len(r["rounds"]) > i]
    reps = [r["rounds"][i]["repairs"] for r in runs if len(r["rounds"]) > i]
    print(f"| {i+1} | {np.mean(after):.0%} ± {np.std(after):.0%} | {np.mean(final):.0%} ± {np.std(final):.0%} | {np.mean(reps):.1f} |")
