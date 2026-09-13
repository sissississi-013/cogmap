# Loop Design Draft — "CutLoop" (working name): a self-improving video editing agent team

Status: DRAFT written before research results landed; to be revised in 04-decision.md.

## One-liner
Drop in raw phone clips + a one-line brief ("make a 30s upbeat travel short with captions"). A team of agents edits it, a multimodal critic grades the render against the brief and a rubric, the editor revises, and across episodes the system distills what worked into an **editing playbook** that measurably raises first-pass scores. Every plan, render, score and playbook update is traced and evaluated in W&B Weave.

## Why this loop is legible to judges
- The artifact is a video: the "before/after" and the iteration ladder are visible in seconds.
- Two nested loops, both measurable:
  1. **Inner loop (per video)**: Director → Editor (emits an Edit Decision List, EDL) → Renderer (ffmpeg) → Critic (VLM on sampled frames + audio/transcript features) → scores + concrete notes → Editor revises. Stops on score ≥ threshold or N rounds.
  2. **Outer loop (across videos / episodes)**: a Reflector agent reads the Weave traces of the inner loop (what notes recurred, which fixes raised which rubric dimension) and rewrites the **playbook** (a versioned Weave object of editing heuristics). Next episode's Editor is conditioned on the playbook. Metric: first-pass critic score and rounds-to-threshold, per episode, on a fixed held-out clip set → trend line in Weave.
- Multi-agent, self-correcting, and the improvement is a number that goes up.

## Components
- `ingest/`: ffprobe metadata, scene detection (PySceneDetect or ffmpeg scdet), keyframe extraction (1 fps grid), Whisper transcript (optional; OpenAI API), simple audio energy curve, VLM shot descriptions (Claude on frame grids) → `ShotLibrary` JSON.
- `edl/`: typed EDL schema (clips[in,out,speed], transitions, captions[text,t0,t1,style,layer], color preset, music track + ducking, aspect). Validator catches impossible plans before rendering.
- `render/`: EDL → ffmpeg filtergraph. Captions rendered with PIL → PNG → `overlay` (local ffmpeg has no drawtext). xfade transitions, `eq`/`curves` color presets, `amix` music with sidechain-ish ducking, 9:16 or 16:9 crop.
- `critic/`: rubric dimensions (brief adherence, pacing/rhythm, shot variety, caption readability/timing, color consistency, hook in first 2s, ending) each 1–10 + structured notes. Uses Claude/GPT vision on a contact sheet + per-cut frames; also deterministic checks (caption overlaps, cut on speech, black frames, duration vs brief). Both are Weave Scorers.
- `playbook/`: versioned markdown/JSON heuristics; Reflector updates it from traces (ACE/Reflexion-style). Published as a Weave object each version so the diff is inspectable.
- `loop.py`: orchestrates episodes; `weave.Evaluation` over a fixed clip-set for each playbook version → leaderboard.
- `demo/`: tiny local web page or marimo notebook showing episode ladder: v0 → v1 → v2 renders side-by-side with scores, plus Weave links.

## Stretch (only if time)
- Subject/background separation for text-behind-subject captions (rembg / SAM on keyframes) — the "layers" capability Sissi mentioned.
- RL-ish: preference pairs (render A vs B + critic verdict) logged as a dataset → could fine-tune later on Modal; for the hackathon, log it and show the dataset growing.
- Serve the Editor via W&B Inference / TypeSafe model for sponsor prizes if keys arrive.

## Risks
- Render time per iteration (keep clips ≤ 45s, 720p during loop, 1080p final).
- VLM critic noise → use fixed rubric, temperature 0, average 2 samples, add deterministic checks.
- ffmpeg filtergraph bugs → validator + unit tests on tiny synthetic clips.
