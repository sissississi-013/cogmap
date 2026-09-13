# PROGRESS (Ralph loop state) — CogMap

## Iteration 1 — started 03:04 PDT
- Repo: https://github.com/sissississi-013/cogmap (main). Weave entity sissiwang-maglev, project `cogmap`.
- Spike results: VGGT on Modal works (A10G, ~90s end-to-end, 9.4GB VRAM); see spikes/vggt_modal/REPORT.md. A100 refused (no payment method) → use A10G. Genesis spike still running (spikes/genesis_sim/).
- Fallback footage: footage/fallback/apt_tour_61s.mp4. Sissi records the venue ~09:00.
- Phase 1 in progress: package skeleton.

## 03:30 PDT — Phase 1 + 2 DONE (iteration 1)
- `cogmap/world.py` (TrueWorld, BeliefMap w/ confidence+volatility, synthetic apartment, scripted 4-round perturbations), `cogmap/agents.py` (A*, NavAgent w/ mission budget 1.5x optimal, Swarm, patrol), `cogmap/repair.py` (rule_repair: consensus flips, orphan removal, blob→unknown_obstacle, re-identification rename; llm_propose_ops + validate_and_apply_ops; patrol_targets; search_targets; reflect), `cogmap/evals.py` (weave.Evaluation per map version, MapNavModel, scorers success/spl/collisions/failures, leaderboard), `cogmap/loop.py` (CogMapLoop: patrol → eval → swarm → search sweep → repair → re-eval), `cogmap/viz.py` (curve.png, steps_to_recover.png, snapshots, swarm.mp4), `run_demo.py`.
- Evidence (no-LLM, no-patrol run, out/synth_nollm/log.txt): v0 100% → change1 (collisions 12) → v1 100%/0 → change2 75% → search sweep finds couch blob in hallway, renamed → v2 100% → change3 (stale obstacle) 94%/SPL .88 → change4 62% → v3 94%. Weave leaderboard published: https://wandb.ai/sissiwang-maglev/cogmap/weave/leaderboards/cogmap-map-versions
- 5 tests green. Visuals verified by eye: out/synth_nollm/curve.png, snapshot_03.png, swarm.mp4 (15s).
- Running now: full variant with LLM repair + patrols → out/synth_full/log.txt (Phase 3).
- NEXT: check synth_full log; make sure LLM ops get applied (Weave traces); steps-to-recover should drop with patrols; then Phase 4 real scan (spikes/vggt_modal → cogmap/scan/).

## 03:45 PDT — Phases 3 + 4 DONE, 5 in progress (iteration 1 continues)
- LLM repair: ANTHROPIC_API_KEY in ~/.zshrc is INVALID (401). Added provider fallback → OpenAI gpt-5 (json mode) works; also the VLM detector uses gpt-5 vision. Tell Sissi to fix the Anthropic key in the morning if she wants Claude in the loop (COGMAP_LLM=anthropic).
- Full synthetic run with LLM + patrols: out/synth_full (v0 100% → ch1 → v1 100% → ch2 75% → search sweep + rename → v2 100% → ch3 patrol pre-emptively repaired stale obstacle → 100% (no task failed) → ch4 81% → v4 94%). Viz rendered.
- Real scan pipeline works: footage/fallback/luxury_room_18s.mp4 (18s continuous living-room clip) → 48 frames → VGGT on Modal (deployed app `cogmap-vggt`, A10G, ~35–55s wall incl. cold start, 6–8s GPU) → 116x129 grid @0.15m → gpt-5 detections (24 frames, ~50s) → 12 anchored objects (couches, armchairs, coffee tables, dining table, kitchen island, plant) → nav2 export. Total ~110s. Overview: out/lux/scan/scan_overview.png. Also TUM freiburg1_room (office, footage/tum/tum_room.mp4) → 12 objects (desks, bookshelves, chairs) in 81s.
- Fallback apartment tour (apt_tour_61s) is a montage with cuts → fragmented reconstruction; not used for demo.
- Running: `run_demo.py --video luxury_room_18s.mp4 --out out/lux` (full loop on real map; stdout is buffered under nohup — use `python -u` next time).
- Written: dashboard.py (marimo), README.md draft, requirements.txt, docs/img/.
- NEXT: verify out/lux loop result + curve; Genesis Go2 B-roll on the scanned heightfield (optional); SUBMISSION.md; final clean run; push.

## 03:50 PDT — fixes after first real-map loop (iteration 1 continues)
- Bugs fixed: (1) agents planned through UNKNOWN cells → collisions at v0; now plan through known-FREE first (`NavAgent._plan`) and goal cells prefer FREE neighbours; (2) run_demo video path used random `default_tasks` (unreachable starts) → now `scan_to_world` returns reachability-checked tasks; (3) LLM repair undid rule-repair (removed a re-identified couch) → strict evidence-based validation for add/remove/relocate + prompt tells the LLM what rule repair already did; (4) perturbations on scanned maps now use the largest object as blocker and the most-targeted goal as mover; (5) recovery criterion relative to v0 baseline, stop when a repair makes no progress.
- 10 tests green. Genesis Go2 B-roll on the scanned map: out/lux/go2_on_map.mp4 (re-rendering with 30 cm blocks).
- docs/demo-storyboard.md written (morning checklist for Sissi).
- Running: out/lux (real map, relaunched with fixes), out/synth_full2 (regression).

## 04:00 PDT — robustness + ablation (iteration 1 continues)
- Portrait 9:16 clip scan works (out/portrait: 12 objects, 12 tasks, 127 s). VGGT retry + task fallbacks + clear errors added.
- Synthetic ablation done: rule-only recovers all rounds too; LLM ops are evidence-gated (README table added).
- Real-map issue found: when the blocker cut the only known route, agents probed unknown cells which the simulated truth treated as walls → persistent collisions. Fix: simulated truth extends floor 3 cells beyond seen floor; unknown-traversal cost raised to 4. Relaunched out/lux and out/tum loops with the fix (pending).
- Per-evaluation Weave call URLs now recorded in loop_result.json and shown in the dashboard.

## 03:50 PDT — real-map loops clean (iteration 3)
- out/lux (living room): 100% → armchair blocks corridor 88%/14 coll → 88%/0 → plant moved 69% → 94% → stale obstacle round: 94% (no drop). out/tum (TUM office): 100% → desk blocks corridor 75%/21 coll → 100% → desk_5 moved: patrol pre-empted → 94% → desk put back: patrol pre-empted → 94%. Viz rendered for both; images published to Weave; README real-scan tables added; docs/img/{lux,tum}_curve.png.
- Perturbation blocker now = largest non-goal object (applies to future runs incl. the venue scan).
- NEXT: Weave UI screenshots (Chrome) for docs; final clean end-to-end run; keep improving until 10:00.

## 03:50 PDT (iteration 3, cont.)
- Outer-loop evidence chart (failures at change: TUM 25 → 2 → 1) added to viz/README/SUBMISSION. Chrome extension not connected → Weave UI screenshots are on Sissi's morning checklist (docs/demo-storyboard.md).
- Final from-scratch run in progress: out/final_lux (one command, fresh dir).

## 03:55 PDT (iteration 3, cont.)
- From-scratch run out/final_lux exposed a v0-collisions regression caused by the floor-margin change (tasks were reachability-checked on the truth, which now has more floor than the belief knows). Fixed: reachable_tasks uses the belief's known-free cells. Grid builder: inclusive floor-candidate selection (flat-floor edge case). New unit test tests/test_scan_grid.py (synthetic point cloud). 11 tests green.
- run_venue.sh (one-shot morning script) under test on TUM → out/venue_test.

## 03:56 PDT — morning script validated end-to-end (iteration 5)
- `./run_venue.sh footage/tum/tum_room.mp4 out/venue_test` from a clean dir (all fixes): scan ≈2 min + loop ≈4 min + Go2 B-roll; v0 100% → desk blocks corridor 75%/31 coll → 100%/0 → desk moved: patrol pre-empted → 100% → stale obstacle: patrol pre-empted → 100%. Curve, swarm.mp4, Weave images, leaderboard all produced.
- Loop results now record rule/LLM op counts per round. Viz crops to the known region on scanned maps.

## 04:00 PDT — polish (iteration 5, cont.)
- Weave ops now carry agent names (navigator_swarm, scout_patrol, scout_search_sweep, cartographer_rule_repair, reasoner_propose_ops, verifier_apply_ops, reflector_changelog, reflector_llm_postmortem); task set published as a Weave Dataset per run; LLM post-mortem appended to map_changelog.md (gpt-5); rounds record rule/LLM op counts + patrol pre-emption.
- README: swarm GIF (docs/img/swarm.gif), office snapshot; SUBMISSION: one-command reproduction; out/dashboard.html static export.
- Docker daemon not running → Nav2 map_server load test not possible here (format verified by unit test).
- Validation run with all polish: out/synth_final (running).

## 04:05 PDT — exploration loop (iteration 6)
- Added frontier exploration (scout_frontier_targets → patrol → rule_repair) before each round + `known_cells` coverage metric per map version (green line on curve). Office map: +140 known cells in 353 steps on the first sweep. Full office run with exploration: out/office (running). synth_final validated (named ops, Weave Dataset, LLM post-mortem in map_changelog.md).

## 04:03 PDT (iteration 8)
- Go2 now walks an A* path from the CogMap belief on the scanned map (Genesis, kinematic base + trot): out/venue_test/go2_walk.mp4 (9.6 s); wired into run_venue.sh + dashboard.
- Office ablation (rule-only, no patrols/explore/LLM) done: out/office_ablation. Full office run with exploration: out/office (finishing). scripts/ablation_table.py prints the README table.

## 04:05 PDT (iteration 9)
- Office run with exploration finished: v0 100% → explored (+140 cells, SPL .89→.95) → change1 88%/24c → 100% → change2 75%/9c → 100% → change3 caught by patrol (100%/7c) → 100%; known cells 2125 → 2595. Real-map ablation table (full vs rule-only) added to README; docs/img refreshed from out/office.
- LLM ops applied: 0 across office/synthetic runs (1 rejected). README/SUBMISSION state this honestly; the LLM's contribution is the scan labels + post-mortem memory.

## 04:08 PDT (iteration 9, cont.)
- Weave leaderboard `cogmap-policies` (final maps: full loop vs rule-only, office + living room). GitHub Actions CI (pytest) + Dockerfile. scripts/make_reel.sh → out/office/reel.mp4 (40 s B-roll), wired into run_venue.sh; storyboard mentions it.
- 04:06 CI green on GitHub Actions (pytest, 11 tests). README badge added.
- 04:08 Map versions published as Weave objects (map-<name>); README renders on GitHub (mermaid, GIF, images verified via API). Verifying with out/synth_check; Go2 walk re-render (lower blocks, calmer camera) for the office reel.
- 04:10 Go2 walk re-rendered (20 cm blocks, calmer camera) → out/office/reel.mp4 rebuilt. tests/test_explore.py added (12 tests). Portrait clip full loop running (out/portrait).
- 04:09 synth_check confirms end-to-end after latest changes (100/100/100/94%; patrol pre-empt in round 3); map versions published as Weave objects.
- 04:14 Portrait 9:16 clip full loop OK (out/portrait): v0 94% → explored 100% → changes 75%/9c, 81%/3c (patrol pre-empted), stale → all recover to ≥94%; 3 rounds.
- Docker (OrbStack) started to load the exported map in a real ROS 2 Nav2 map_server (anonymous pull; user's stale Docker Hub token bypassed via --config). Running.
- 04:13 PROOF: exported map loads in real ROS 2 Humble nav2_map_server (Docker via public.ecr.aws mirror): "Read map /maps/map.pgm: 112 X 109 map @ 0.15 m/cell", /map published. scripts/nav2_check.sh + docs/proof/nav2_map_server.log; README + SUBMISSION updated.
- 04:16 Experiment running: Nav2 planner_server (NavFn) + static costmap on the exported map, asking /compute_path_to_pose from task t0's start to the bookshelf_2 waypoint (out/nav2_check/plan_log.txt).
- 04:17 PROOF 2: Nav2 NavFn planner_server + static costmap plan a 178-pose path on the exported office map (Docker, cached image cogmap-nav2). scripts/nav2_plan.sh, docs/proof/nav2_planner.log. README/SUBMISSION/storyboard updated.
- 04:18 Nav2 path captured (178 poses) and drawn on the map: docs/img/nav2_path.png, docs/proof/nav2_path.yaml.
- 04:20 scripts/draw_nav2_path.py (path image per run), nav2_plan.sh draws it, run_venue.sh runs the Nav2 proof when Docker is up, dashboard shows it.
