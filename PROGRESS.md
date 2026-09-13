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
