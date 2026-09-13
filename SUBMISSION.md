# CogMap — submission notes (AGI House platform)

**Team name:** CogMap
**Members:** Sissi Wang (solo) — built with Claude Code running a Ralph loop overnight
**Track:** Best Use of Weave (also eligible: Best Loop Design, Best Use of marimo)
**Repo:** https://github.com/sissississi-013/cogmap
**Weave project:** https://wandb.ai/sissiwang-maglev/cogmap/weave
**Modal app:** cogmap-vggt (VGGT-1B on A10G)

## 2–3 sentence description
CogMap turns a phone walkthrough of any space into a cognitive map (metric occupancy grid + semantic object graph) that a
swarm of simulated robots learns to navigate. When the world changes, the swarm's navigation failures drive an automatic
map repair (deterministic ops + LLM scene-graph edits validated against observations), so success recovers; across
changes the swarm learns where the world is volatile and heals faster. Every map version is a W&B Weave evaluation, and the
map is exported as the ROS 2 Nav2 artifact real robots (Unitree Go2/G1 stacks) load — verified: a stock ROS 2 Humble
`nav2_map_server` publishes it and Nav2's NavFn planner plans a path on it (`docs/proof/`).

## What makes the loop self-improving
- **Inner loop (self-correcting map):** plan on belief → execute in truth → failure events → repair → new map version →
  re-evaluate on a fixed task set. Real office scan (TUM): a desk dragged into the busiest corridor takes success from
  100% to 75% with 21 collisions; one repair pass brings it back to 100% with 0 collisions. Synthetic apartment: couch
  moved 75% → 100%, doorway blocked 62% → 94%.
- **Outer loop (self-improving swarm):** repairs feed a per-cell volatility prior; patrol agents verify volatile cells
  before tasks run. On the office map the hard failures the swarm hits right after each change go 25 → 2 → 1 across
  three changes, because rounds 2 and 3 were caught by patrols before the task swarm ran. A search sweep finds objects
  that went missing and re-identifies them by footprint.
- **Exploration loop:** scouts push the frontier between changes; the map grows past what the phone saw (2125 → 2595 known cells).
- **Real changes:** `--rescan` registers a second walkthrough (after furniture moved) to the first map and makes the
  difference the world change the loop repairs (19 collisions → 2 repairs → 100%).
- **Observable:** every step is a `@weave.op`; each map version is a `weave.Evaluation` (`map_v{k}`); Weave Leaderboards rank
  versions and policies; map versions are published Weave objects.

## Sponsor tools & how they're used
- **W&B Weave:** tracing of every agent step (swarm runs, patrols, rule/LLM repair, validation, scan stages), per-map-version
  Evaluations with custom scorers (success, SPL, collisions, failures), Leaderboard, published map objects; W&B MCP server
  registered in the coding agent.
- **Modal:** GPU 3D reconstruction (VGGT-1B) as a deployed app with warm containers (~6 s GPU time per scan).
- **marimo:** `dashboard.py` results dashboard (curves, tables, scan overview, swarm video, changelog, Nav2 export).
- **OpenAI gpt-5 (and Claude when a key is available):** VLM object detector for the scan, evidence-gated scene-graph
  repair proposals (0 applied in the reported runs: the deterministic repair covered every case; proposals without
  observation support are rejected), and the Reflector post-mortem written into the map changelog. A local OWLv2
  detector is the automatic fallback when no API credits are available.
- **ROS 2 Nav2 (Docker):** the exported map loads in a stock `nav2_map_server` and NavFn plans a 143-pose path on it.
- Protocols/frameworks: no A2A/MCP at runtime; MCP used at build time (W&B MCP server in Claude Code).

## Reproduce in one command
`./run_venue.sh <phone_clip.mov> out/venue` → scan (VGGT on Modal + VLM objects) → loop (3 auto-generated world changes) →
curve, swarm video, Nav2 export, Weave evaluations/leaderboard, Go2 B-roll. ~6 minutes. `marimo run dashboard.py` for the dashboard
(a static export is in `out/dashboard.html`).

## 3-minute demo script
0:00 Phone walkthrough clip (15 s) → "this is all the robot gets".
0:20 `scan_overview.png` + 3D point cloud: grid, labeled furniture, phone path; `map.yaml` export on screen.
0:50 `swarm.mp4`: agents navigate the scanned room (map v0, Weave eval 100%).
1:10 "Someone moved the couch": agents fail (red X), success drops; failure log in Weave trace.
1:35 Repair trace: rule ops + LLM ops (applied/rejected) → map v1; success climbs; leaderboard.
2:10 Round 3: volatility prior → patrol catches the stale obstacle before any task fails; steps-to-recover chart.
2:35 Same loop on the synthetic apartment (4 changes) + Nav2 artifact → "the map outlives the robot generation".
2:50 One slide: two loops, Weave, Modal, marimo.

## Social post draft
Built CogMap at @weights_biases CoreWeave Hacks: walk through a room with your phone → a swarm of sim robots learns the map →
move the couch → their failures repair the map → success recovers, tracked as Weave evaluations. Exports the Nav2 map a
Unitree Go2 loads. Repo: github.com/sissississi-013/cogmap #WeaveHacks #CoreWeaveHacks
