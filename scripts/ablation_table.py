"""Print a Markdown ablation table from two or more loop_result.json runs.  Usage: python scripts/ablation_table.py name=out/dir ..."""
import json, sys

def load(path):
    return json.load(open(path.rstrip("/") + "/loop_result.json"))

runs = [a.split("=", 1) for a in sys.argv[1:]]
print("| variant | " + " | ".join(f"round {i+1}" for i in range(max(len(load(p)['rounds']) for _, p in runs))) + " | final map | known cells v0 → end |")
print("|---|" + "---|" * (max(len(load(p)['rounds']) for _, p in runs)) + "---|---|")
for name, p in runs:
    r = load(p)
    cells = []
    for x in r["rounds"]:
        m = next((m for m in r["timeline"] if m.get("round") == x["round"] and m.get("phase") == "after_change"), {})
        drop = f"{m.get('success_rate', 0):.0%}/{int(m.get('collisions', 0))}c"
        pre = " (patrol caught it)" if x.get("patrol_preempted") else ""
        cells.append(f"{drop}{pre} → {x['final_success']:.0%} in {x['repairs']} repair{'s' if x['repairs'] != 1 else ''}")
    tl = r["timeline"]
    known = f"{tl[0].get('known_cells', '?')} → {tl[-1].get('known_cells', '?')}"
    print(f"| {name} | " + " | ".join(cells) + f" | v{r['rounds'][-1]['map_version']} | {known} |")
