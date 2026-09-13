import marimo

__generated_with = "0.14.0"
app = marimo.App(width="full", app_title="CogMap dashboard")


@app.cell
def _():
    import marimo as mo
    import os, json, glob, base64
    return base64, glob, json, mo, os


@app.cell
def _(glob, mo, os):
    runs = sorted([d for d in glob.glob("out/*") if os.path.exists(os.path.join(d, "loop_result.json"))],
                  key=os.path.getmtime, reverse=True)
    run_sel = mo.ui.dropdown(options=runs, value=runs[0] if runs else None, label="run")
    mo.vstack([mo.md("# CogMap — self-repairing cognitive maps for robots"),
               mo.md("Phone walkthrough → world model → simulated swarm learns to navigate → the world changes → "
                     "the swarm's failures repair the map → success recovers. Every map version is a W&B Weave evaluation."),
               run_sel])
    return run_sel, runs


@app.cell
def _(json, mo, os, run_sel):
    run = run_sel.value
    res = json.load(open(os.path.join(run, "loop_result.json"))) if run else {"timeline": [], "rounds": []}
    tl = res["timeline"]
    rows = [{"map version": f"v{m['version']}", "label": m["label"], "success": f"{m['success_rate']:.0%}",
             "SPL": f"{m['spl']:.2f}", "collisions": int(m["collisions"]), "story": m.get("story", ""),
             "weave trace": m.get("weave_call_url", "")} for m in tl]
    rounds = [{"round": r["round"], "story": r["story"], "patrol caught it first": "yes" if r.get("patrol_preempted") else "no",
               "repairs": r["repairs"], "rule ops": r.get("rule_ops", ""), "LLM ops applied / rejected": f"{r.get('llm_ops_applied', '')} / {r.get('llm_ops_rejected', '')}",
               "steps to recover": r["steps_to_recover"], "final success": f"{r['final_success']:.0%}"} for r in res["rounds"]]
    lb = res.get("leaderboard")
    wv = res.get("weave", {"project": "https://wandb.ai/sissiwang-maglev/cogmap/weave"})
    links = "  ·  ".join(f"[Weave {k}]({v})" for k, v in wv.items())
    mo.vstack([
        mo.md(f"## Run: `{run}`  ·  {links}"),
        mo.md(f"leaderboard object: `{lb}`  ·  tasks per evaluation: {res.get('n_tasks', '?')}  ·  loop wall time: {res.get('elapsed_s', '?')} s"),
        mo.hstack([mo.image(os.path.join(run, "curve.png")) if os.path.exists(os.path.join(run, "curve.png")) else mo.md("no curve yet"),
                   mo.image(os.path.join(run, "steps_to_recover.png")) if os.path.exists(os.path.join(run, "steps_to_recover.png")) else mo.md("")]),
        mo.md("### Timeline (one Weave Evaluation per row)"), mo.ui.table(rows, selection=None),
        mo.md("### Rounds (outer loop)"), mo.ui.table(rounds, selection=None),
    ])
    return res, run


@app.cell
def _(mo, os, run):
    scan = os.path.join(run, "scan") if run else ""
    items = []
    if os.path.exists(os.path.join(scan, "scan_overview.png")):
        items.append(mo.md("### The world model from the phone scan"))
        items.append(mo.hstack([mo.image(os.path.join(scan, "scan_overview.png"), width=520),
                                mo.image(os.path.join(scan, "contact_sheet.jpg"), width=520) if os.path.exists(os.path.join(scan, "contact_sheet.jpg")) else mo.md("")]))
        if os.path.exists(os.path.join(scan, "pointcloud.html")):
            items.append(mo.md(f"3D point cloud: `{os.path.join(scan, 'pointcloud.html')}` (open in a browser)"))
        if os.path.exists(os.path.join(scan, "nav2", "map.yaml")):
            items.append(mo.md("### Exported for a real robot (ROS 2 Nav2 map_server)"))
            items.append(mo.md("```yaml\n" + open(os.path.join(scan, "nav2", "map.yaml")).read() + "```"))
    mo.vstack(items) if items else mo.md("_synthetic run (no scan)_")
    return


@app.cell
def _(mo, os, run):
    vid = os.path.join(run, "swarm.mp4") if run else ""
    parts = [mo.md("### Swarm animation (belief map | true world)")]
    if os.path.exists(vid):
        parts.append(mo.video(vid, controls=True, width=1000))
    else:
        parts.append(mo.md("no animation rendered yet"))
    go2 = os.path.join(run, "go2_on_map.mp4") if run else ""
    if os.path.exists(go2):
        parts.append(mo.md("### Transfer: a Unitree Go2 (Genesis sim) dropped into the scanned map"))
        parts.append(mo.video(go2, controls=True, width=640))
    cl = os.path.join(run, "map_changelog.md") if run else ""
    if os.path.exists(cl):
        parts.append(mo.md("### Map changelog (Reflector output)"))
        parts.append(mo.md(open(cl).read()))
    mo.vstack(parts)
    return


if __name__ == "__main__":
    app.run()
