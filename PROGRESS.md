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
