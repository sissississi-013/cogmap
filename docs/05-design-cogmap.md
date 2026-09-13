# CogMap — design (approved by Sissi: "GO", 2026-09-13 ~03:55 PDT)

## One-liner
Walk through any space with a phone. CogMap turns the video into a cognitive map (metric occupancy grid + semantic object graph), lets a swarm of simulated agents learn to navigate it, and when the world changes (someone moves the couch) the swarm's failures drive an automatic map repair, so navigation success recovers. Over repeated changes the swarm learns *where* the world tends to change and heals faster each time. The map is exported as the artifact a Nav2 robot (Unitree Go2/G1 stacks) actually loads.

## The loops (what judges are scoring)
1. **Self-correcting map (inner loop):** belief map v_k → N agents plan A* on belief, execute on the true world with a local sensor → expected≠observed → failure events → Repair agent (rule-based ops + Claude proposing scene-graph ops over JSON, validated against geometry) → map v_{k+1} → re-evaluate fixed (start, goal) task set in Weave. Curve: v0 90% → perturb → 40% → v1 85% → v2 92%.
2. **Self-improving swarm (outer loop):** each perturbation round updates a per-cell **volatility prior** learned from the repair history; patrol/verification agents are dispatched to high-volatility + low-confidence cells before tasks run. Metric: *steps-to-recover* (agent steps between perturbation and success ≥ threshold) decreases across rounds 1→2→3. A Reflector op summarizes what changed and why into a human-readable `map_changelog.md`.
3. Everything is a `@weave.op`; each map version is a `weave.Evaluation` run (model name `map_v{k}`) → compare view + Leaderboard.

## Components (Python package `cogmap/`, venv `.venv` py3.12)
- `world.py` — `TrueWorld` (grid + objects), `BeliefMap` (grid, confidence, objects, version, volatility), perturbations (move/add/remove object), synthetic apartment generator.
- `agents.py` — `NavAgent` (A* on belief; executes on true world; 3×3 sensor; emits `FailureEvent`), `Swarm` runner, task set, patrol policy (volatility × uncertainty).
- `repair.py` — rule-based repair (k-conflict flips, object centroid relocate, dilation), `llm_repair` (Claude, structured ops: relocate/add/remove/mark_blocked/mark_free), `validate_ops` gate, `reflect` changelog.
- `evals.py` — Weave dataset of (start, goal), scorers `success`, `spl`, `collisions`; `evaluate_map(belief, version)`; leaderboard publish.
- `scan/` — `frames.py` (ffmpeg keyframes), `vggt_modal.py` (Modal GPU: VGGT-1B → points, conf, poses; from spike), `grid_from_points.py` (floor fit → occupancy), `objects.py` (Claude vision labels per keyframe + point-map median → cell), `export_nav2.py` (map.pgm + map.yaml + waypoints.json).
- `viz.py` — matplotlib animation MP4 (belief | true, agents, failure X's), plotly 3D point cloud HTML, curve plots.
- `loop.py` — orchestrator for N perturbation rounds; `run_demo.py` CLI (`--video` real scan | `--synthetic`).
- `dashboard.py` — marimo notebook: videos, curves, playbook/changelog, Weave links.
- `tests/` — pytest for world, A*, repair, exporter.

## Sponsor usage
Weave (traces, Evaluations, Leaderboard, video/image logging), W&B MCP server (registered; the coding agent inspects traces), Modal (VGGT GPU), marimo (dashboard). W&B Inference / TypeSafe: add as second repair model if keys arrive.

## Hard cutoffs (PDT)
04:30 skeleton+synthetic swarm+tests · 05:15 failure→rule repair→Weave curve · 06:00 LLM repair + volatility loop · 07:15 real scan end-to-end ≤10 min per video · 08:00 viz + dashboard · 08:30 README/submission/push · 09:00+ Sissi records venue → rerun → record demo.
