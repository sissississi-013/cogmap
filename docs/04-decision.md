# Decision — what to build tonight

Written 2026-09-13 03:15 PDT. ~9.5 hours to submission (1 PM). Sissi must be at the venue by 9 AM, so the working demo must exist by ~08:30, leaving 3–4 hours for recording, README, submission text.

## Recommendation: build ONE project — Idea 1, "CutLoop" (self-improving video editing agent team)

Ranking (Best Loop Design first, then demo legibility, then risk):

| | Video editing (CutLoop) | Manufacturing (ForgeLoop) | Robot nav from phone scan |
|---|---|---|---|
| Loop legibility in 3 min | Best: before/after video + score ladder + readable playbook | Good: red undercut faces → green + curve | Good but the "map" is a VLM guess; success curve can be flat |
| Scorers | VLM rubric (noisy) + deterministic checks | **Objective** geometry/DFM scorers | success rate in a toy grid-world |
| Overnight risk | Medium: ffmpeg pipeline verified locally in 0.36s; judge noise is the main risk | Medium-high: CadQuery codegen 11–20% invalid on simple parts, worse on real parts; DFM on meshes is noisy | High: 3D reconstruction rabbit hole; sims don't run on Mac; degraded version is a gridworld |
| Fit to Sissi | Strongest personal interest; real footage on disk (Gecko vlog, IMG_*.MOV) | Closest to company thesis; no domain files on disk | Cool but least buildable tonight |
| Sponsor angle | Weave evals/leaderboard/video traces; W&B Inference vision model as 2nd judge; marimo notebook for the results dashboard | same | same |

Why not two directories: one person, one 3-minute slot, one submission. A second autonomous loop halves the iteration budget and the polish of the one that gets demoed. The research also shows the winning pattern at prior WeaveHacks is "traces → judge → agent rewrites its own rules → curve goes up", which CutLoop hits squarely. If Sissi still wants a second, ForgeLoop (not robot nav) is the one, started only after CutLoop's pipeline is frozen.

## CutLoop loop design (final)
Inner loop (per brief): ingest → Planner (Claude + playbook) emits validated EDL → Render (ffmpeg, PIL captions) → Critic (deterministic scorers ≥50% weight + Claude VLM rubric on contact sheets, pairwise vs previous render) → Reviser ≤3 rounds, keep best.
Outer loop (across episodes): Reflector tags playbook bullets helpful/harmful and proposes new lessons → Curator delta-merges into a versioned playbook.json (ACE style, capped ~40 bullets) → next episode's Planner is conditioned on it.
Evidence of improvement: held-out clip set evaluated with an empty playbook vs each playbook version → Weave Evaluation per version → Weave Leaderboard; first-pass score and rounds-to-threshold trend up. Ablation row is the money shot.
Agents: Ingest, Planner, Renderer (tool), Critic, Reflector, Curator — a team, each a @weave.op.

## Build order (freeze pipeline by ~06:30)
1. Repo, venv, weave init smoke test, footage prep (clips ≤45s, 720p working proxies).
2. Ingest: scenes, keyframes, contact sheets, transcript (whisper-1), per-shot VLM descriptions → shots.json.
3. EDL schema + validator + ffmpeg renderer (cuts, xfade, captions via PIL overlay, music amix+loudnorm, 9:16/16:9). Unit test on synthetic clips.
4. Deterministic scorers + VLM critic with rubric JSON. Weave scorers.
5. Planner/Reviser inner loop on one brief. Log to Weave.
6. Playbook + Reflector/Curator outer loop. Run episodes on 3 clip sets; held-out eval; Leaderboard.
7. Demo page (marimo notebook or simple HTML) showing ladder v0→vN with videos + scores + playbook diff. README, submission text, 2-min screen recording script.
Stretch: W&B Inference second judge; subject/background text-behind-subject captions; GEPA on planner prompt.

## What Sissi must do before sleeping
1. W&B API key (hard blocker for Weave): https://wandb.ai/authorize → put it in /Users/sissi/weavehacks/.env as `WANDB_API_KEY=...` (file is gitignored). Also `WANDB_ENTITY=<your wandb username>` if different from the default.
2. Say yes to CutLoop (or pick differently) so the Ralph loop can start.
3. AGI House platform: sign in + complete the participant survey tonight (submission can't complete without it).
4. Optional: drop preferred raw clips into /Users/sissi/weavehacks/footage/raw/ and 3–5 royalty-free MP3s into footage/music/. Otherwise Claude uses ~/Movies/hoohoo.mov, Vlog3-Gecko.mov, ~/Downloads/IMG_*.MOV and downloads CC0 music.
5. Nothing needed for Modal (already authenticated) or Anthropic/OpenAI (keys present).
