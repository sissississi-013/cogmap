# CogMap — 2-minute screen recording storyboard (and 3-minute live pitch)

Everything below is a file you open or a command you run. Record with QuickTime / Zoom share. Keep the cursor calm.

| t | say | show |
|---|---|---|
| 0:00 | "I walked through this room with my phone. That's all the robots get." | `footage/fallback/luxury_room_18s.mp4` (or the venue clip in `footage/raw/`), play 6 s |
| 0:08 | "One command turns it into a cognitive map: a metric grid plus a labeled object graph, built by VGGT on a Modal GPU and a vision model." | `python run_demo.py --video <clip> --out out/venue` starting (terminal), then `out/<run>/scan/scan_overview.png` |
| 0:25 | "Here's the 3D world model and the artifact a real robot loads: a Nav2 map.pgm / map.yaml plus named waypoints." | `out/<run>/scan/pointcloud.html` (rotate once), `out/<run>/scan/nav2/map.yaml` |
| 0:40 | "A swarm of simulated robots learns to navigate it. Every map version is a Weave evaluation on a fixed task set: v0 is the baseline. Scouts explore the frontier first, so the map grows past what the phone saw (green line)." | `out/<run>/swarm.mp4` (first segment), `curve.png` green line, Weave evaluations page |
| 0:55 | "Now someone moves the furniture. The robots fail: red X's. Success drops." | `swarm.mp4` (change segment) + `out/<run>/curve.png` red band |
| 1:10 | "Their failures are the signal. A repair agent proposes scene-graph edits, every edit is validated against what the robots actually observed, and the map version bumps. Success recovers." | Weave trace of `repair_map` → `llm_propose_ops` (applied vs rejected), then `curve.png` recovery |
| 1:30 | "Second loop: the map learns where the world is volatile. Patrol agents check those cells before tasks run, so the next change is caught before anyone fails." | `swarm.mp4` patrol segment (orange path), `out/<run>/steps_to_recover.png` |
| 1:45 | "Same loop, real scan and synthetic apartment. Leaderboard of map versions in Weave." | Weave leaderboard `cogmap-map-versions`; `marimo run dashboard.py` |
| 1:55 | "The map outlives the robot generation: it exports to the Nav2 format a Go2 or G1 stack loads today — here is a stock ROS 2 map_server publishing it." | `out/<run>/go2_walk.mp4` (Genesis Go2 walking the planned path) + `docs/proof/nav2_planner.log` ("Goal finished with status: SUCCEEDED", 143 poses) |

## Live 3-minute version
Same order; add 30 s at the start recording the venue walkthrough on the phone earlier that morning and 20 s of Q&A buffer.
One slide max: the two-loop diagram from README.md.

## If short on time
`out/<run>/reel.mp4` (made by `run_venue.sh`) is a silent 40-second B-roll of everything above; record a voice-over on it.

## Files to have open before you start
- `out/<run>/scan/scan_overview.png`, `out/<run>/scan/pointcloud.html`, `out/<run>/scan/nav2/map.yaml`
- `out/<run>/swarm.mp4`, `out/<run>/curve.png`, `out/<run>/steps_to_recover.png`, `out/<run>/go2_on_map.mp4`
- https://wandb.ai/sissiwang-maglev/cogmap/weave (evaluations, leaderboards, traces)
- `marimo run dashboard.py` in a browser tab

## Morning checklist (Sissi)
0. **API credits (do this first).** At ~04:19 the OpenAI account returned `429 You have no credits remaining`. Without credits the
   scan still works but objects are unnamed blobs and the LLM repair/post-mortem are skipped. Either add OpenAI credits
   (https://platform.openai.com/settings/organization/billing) or put a valid `ANTHROPIC_API_KEY` in `.env` and run with
   `COGMAP_LLM=anthropic`. A credit-free local detector (OWLv2, CPU) is installed and validated (12 labelled objects on the office scan in
   58 s), and it kicks in automatically when the API fails, so labels will appear either way. Without credits you only
   lose the LLM repair proposals (0 applied in all runs anyway) and the LLM post-mortem paragraph in the changelog.
1. Record the venue: 60–90 s, slow, chest height, pan gently, include furniture; AirDrop → `footage/raw/venue.mov`.
   **Optional but powerful:** move a chair/table into a walkway, then record a second 30–60 s pass of the same area →
   `footage/raw/venue_b.mov`. Run `./run_venue.sh footage/raw/venue.mov out/venue footage/raw/venue_b.mov` and the
   first world change in the loop is the *real* one (scan B registered to map A, difference → the swarm fails → repair).
   `out/venue/rescan/rescan_diff.png` shows A, B-aligned and the red/green difference. Experimental: if registration
   looks wrong, just run without the third argument.
2. `./run_venue.sh footage/raw/venue.mov out/venue`  (does everything: scan, loop, visuals, B-roll)
   (≈2 min scan + ≈3 min loop). If VGGT is cold it takes ~60 s longer.
3. Optional B-roll: `spikes/genesis_sim/.venv/bin/python cogmap/broll_genesis.py out/venue/scan/belief_v0.json out/venue/go2_on_map.mp4`
4. Fix `ANTHROPIC_API_KEY` in `~/.zshrc` if you want Claude as the repair agent (`COGMAP_LLM=anthropic`); otherwise gpt-5 is used.
5. Take two screenshots for the README/submission: the Weave **Evaluations** page (compare view of map versions) and the
   **Leaderboard** `cogmap-map-versions` at https://wandb.ai/sissiwang-maglev/cogmap/weave (save to `docs/img/weave_evals.png`,
   `docs/img/weave_leaderboard.png`, then `git add docs/img && git commit -m "weave screenshots" && git push`).
6. Record the 2-minute video, submit on AGI House by 1 PM, post on X.
