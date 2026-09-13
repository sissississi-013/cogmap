# Ralph loop prompt — CogMap (CoreWeave Hacks 2026)

You are building **CogMap** autonomously overnight in /Users/sissi/weavehacks. Read, in order, `docs/05-design-cogmap.md` (the approved design), `PROGRESS.md` (state from previous iterations; create it if missing), then `docs/research-02-robot-nav.md` and `docs/research-04-robot-nav-deep.md` for references. `docs/00-hackathon-context.md` has judging criteria and submission requirements. Spike outputs live in `spikes/vggt_modal/` (VGGT on Modal; read its REPORT.md if present) and `spikes/genesis_sim/` (Go2 sim B-roll; optional).

## Non-negotiables
- Submission deadline is 13:00 PDT today. Sissi arrives at the venue ~09:00 and will record a venue walkthrough; `python run_demo.py --video <path>` must then work end-to-end in ≤10 minutes. Run `date` at the start of every iteration and respect the cutoffs in the design doc. If a phase blows its cutoff, ship the fallback described there and move on.
- Environment: `source .venv/bin/activate` (Python 3.12; weave/wandb installed) and `set -a; source .env; set +a` for WANDB_API_KEY (never print, commit, or delete `.env`). ANTHROPIC_API_KEY and OPENAI_API_KEY are in the shell env. Modal CLI: `/Library/Frameworks/Python.framework/Versions/3.12/bin/modal` (profile sissiwang). ffmpeg 9.0.1 at /opt/homebrew/bin/ffmpeg (no drawtext); /opt/homebrew/opt/ffmpeg-full/bin/ffmpeg has drawtext.
- Weave project name: `cogmap` (entity sissiwang-maglev). Every meaningful function is a `@weave.op`. One `weave.Evaluation` per map version named `map_v{k}`; publish a Leaderboard.
- Fallback scan footage: `footage/fallback/apt_tour_61s.mp4` (real-estate tour with cuts; VGGT handles unordered views). Sissi's own footage may appear later in `footage/raw/`.
- Work in small verified steps: write tests where cheap (pytest), run them, run the real thing, look at the output image/video (Read tool) before claiming it works. Commit after every working step with a descriptive message ending in the attribution lines below; `git push origin main` after every phase.
- Keep `PROGRESS.md` current at the end of EVERY iteration: what is done (with evidence: test output, file paths, Weave URLs), what is next, known issues, time-stamped. The next iteration only sees files, not your memory.
- Use subagents for independent parallel work (e.g. viz while the loop runs) but keep integration in the main package.
- Don't rabbit-hole: max 20 minutes on any single blocker before taking the fallback and recording it in PROGRESS.md.

## Phases (each phase = at least one commit + PROGRESS.md update)
1. **Skeleton + synthetic world (by 04:30):** package `cogmap/`, `TrueWorld`/`BeliefMap`, synthetic apartment (rooms, doors, furniture objects with names), A* `NavAgent` with 3×3 sensor, `Swarm` running a fixed task set of (start, goal-object) pairs, success/SPL/collision metrics, pytest green, `weave.init("cogmap")` smoke op.
2. **Self-correcting map (by 05:15):** failure events (expected≠observed), perturbation (move a large object into a corridor/doorway), rule-based repair ops, `evaluate_map` as `weave.Evaluation` per version, run v0 → perturb → v1 → v2 and print the success curve; publish Leaderboard; save `out/curve.png`. Loop must show recovery WITHOUT the LLM.
3. **LLM repair + self-improving swarm (by 06:00):** Claude repair agent proposing structured scene-graph ops from the failure log (validated before commit), volatility prior + patrol policy, Reflector writing `out/map_changelog.md`; run 3 perturbation rounds and show steps-to-recover decreasing; all traced in Weave.
4. **Real scan (by 07:15):** `cogmap/scan/`: keyframes → VGGT on Modal (reuse spike) → occupancy grid + floor fit → Claude-vision object labels anchored via point-map median → `BeliefMap` → same loop runs on the real map → `export_nav2` (map.pgm, map.yaml, waypoints.json). `python run_demo.py --video footage/fallback/apt_tour_61s.mp4` works end-to-end. Fallback if VGGT fails: VLM-estimated coarse grid from keyframes, clearly labeled as such.
5. **Viz + dashboard (by 08:00):** `out/swarm.mp4` animation (belief | true grid, agents, failure X's, version banner), `out/pointcloud.html`, curve plots, marimo `dashboard.py` showing videos/curves/changelog/Weave links; include Genesis Go2 clip if the spike produced one.
6. **Ship (by 08:30):** README.md (what/why, architecture diagram in mermaid, the two loops, how to run, every sponsor tool and how it's used, Weave project link, honest limitations), `SUBMISSION.md` (2–3 sentence description, track: Best Use of Weave, sponsor list, 3-minute demo script, social post draft), final push. Then run one full clean `run_demo.py` from scratch to prove it, paste evidence in PROGRESS.md.

When ALL six phases are done, verified end-to-end (fresh `run_demo.py` run succeeded, tests green, pushed to GitHub, Weave leaderboard URL recorded in PROGRESS.md), output exactly: <promise>COGMAP COMPLETE</promise>
If time passes 08:45 and phases remain, finish the highest-value remaining item, document precisely what is missing in PROGRESS.md and README, push, and output the promise anyway.

Commit attribution (append to every commit message):
Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PVyCnTjrk1sHNvSkmBmnwN
