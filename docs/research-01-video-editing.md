# Research: Idea 1 — self-improving video editing agent

(Research agent report, 2026-09-13 ~03:10 PDT; all claims verified via web + local checks)

## Prior art — steal from
| Project | What | Steal |
|---|---|---|
| EditDuet (SIGGRAPH'25, https://arxiv.org/html/2509.10761) | Editor agent + Critic agent; tools search_collection/add_to_timeline/remove/swap/move/DONE; critic give_feedback/RENDER; judge = GPT-4o on keyframe grid at clip midpoints scoring structure/relevance/aesthetic coherence/pacing; 80.6% human agreement | Editor/Critic tool surface, keyframe-grid judge, metrics (failure rate, time-coverage min(d,d̂)/max(d,d̂), repetition count), failure list (hallucinated files, out-of-bounds times) → validate EDL before render |
| browser-use/video-use (MIT, https://github.com/browser-use/video-use) | LLM never watches video; reads word-timestamped transcript + on-demand filmstrip/waveform PNGs. Transcribe → Pack → Reason → EDL → Render → self-eval (≤3 re-renders) | two-layer representation, EDL→ffmpeg. Does NOT learn across episodes → our differentiator |
| LAVE (IUI'24, 2402.10294) | LLM captions footage → plans edits | per-clip VLM descriptions as planning substrate |
| HKUDS/VideoAgent (EMNLP'26) | 30+ agents, needs 8GB GPU + 6 HF models | ideas only |
| VideoWeaver (Jun'26, https://github.com/JianhuiWei7/VideoWeaver) | agent-as-judge + skill evolution rewriting SKILL.md; Claude Code harness | closest precedent to "editing playbook"; cite |
| CineAgents/CineBench (2604.10456), AgenticVBench (2605.27705), CutVerse (2605.19484) | 2026 editing-agent benchmarks | cite, don't use |
| Reward models: VideoAlign, VideoScore, VBench, aesthetic-predictor-v2-5 | learned scorers | only aesthetic-predictor-v2-5 is CPU-cheap (per frame); skip others |

## Self-improvement methods
- Self-Refine / Reflexion: within-episode critique→revise + verbal failure memory. 1 hr. Necessary, not sufficient.
- ACE — Agentic Context Engineering (ICLR'26, https://arxiv.org/abs/2510.04618): Generator/Reflector/Curator; playbook = itemized bullets with IDs + helpful/harmful counters; Curator emits delta bullets merged deterministically (dedupe/prune). ~2 hrs as JSON + two prompts. Strongest cross-episode mechanism.
- GEPA (ICLR'26 oral, `pip install gepa`): each eval = render + judge (30–60s) → 100 evals ≈ 1–2h. Optional stretch on planner prompt only (max_metric_calls≈40).
- Verdict: Self-Refine inside episode + ACE playbook across episodes; GEPA optional.

## Practical stack (verified locally)
- ffmpeg 8.0.1 homebrew slim: no drawtext/subtitles/libass/freetype. Has overlay, xfade, fade, acrossfade, amix, loudnorm, concat, trim, setpts, eq, curves, vignette, zoompan, scdet, blackdetect, silencedetect, ebur128, tile. Smoke-tested PIL caption PNG → overlay + xfade + acrossfade + amix + loudnorm + contact sheet: 0.36s. PIL route is sane. `brew install ffmpeg-full` (keg-only, /opt/homebrew/opt/ffmpeg-full/bin/ffmpeg) as background insurance.
- Python: `uv venv --python 3.12`; scenedetect 0.7.1, weave 0.53.9, mlx-whisper 0.4.3 resolve.
- Transcript: OpenAI `whisper-1` with timestamp_granularities=["word"] (gpt-4o-transcribe lacks word timestamps). mlx-whisper local fallback.
- Critic: Claude (no video input) with frames: 2 fps sampled, tiled contact sheets (4×3, ≤1568px long edge ≈1.5k tokens each) + 1–2 frames either side of each cut + transcript + audio stats (ebur128, silences). 30s cut ≈ 5 sheets ≈ 8k tokens ≈ $0.04–0.10/critique. Rubric JSON via structured output: pacing, cut-motivation, continuity, caption legibility, audio, hook, overall 1–10, required defects[] with timestamps.
- Deterministic scorers (every iteration, stable gradient): duration target coverage, shot-length variance, no clip <0.6s, no black frames, loudness in range, caption on-screen ≥1s, aesthetic mean, cut-on-beat rate.
- Music: CC0 MP3s (Pixabay/Chosic), beat grid via librosa.beat.beat_track. Skip procedural generation.
- W&B Inference (https://api.inference.wandb.ai/v1, OpenAI-compatible): vision models Qwen/Qwen3.8-27B, google/gemma-4-31B-it, zai-org/GLM-5.3-Flash, moonshotai/Kimi-K2.6 (https://docs.wandb.ai/inference/models). Use as second cheaper judge once credits arrive.

## Weave — showing improvement
- `@weave.op` on plan/render/critique; `weave.Evaluation(dataset, scorers).evaluate(model, __weave={"display_name": f"iter-{n}"})` per playbook version → compare view.
- Leaderboard: `weave.flow.leaderboard.Leaderboard(columns=[LeaderboardColumn(evaluation_object_ref=..., scorer_name=..., summary_metric_path="overall.mean")])`, `weave.publish` (https://docs.wandb.ai/weave/cookbooks/leaderboard_quickstart). Rows = playbook v0…vN.
- EvaluationLogger (imperative log_prediction/log_score/log_summary) fits inner loop (https://docs.wandb.ai/weave/guides/evaluation/evaluation_logger).
- Log MP4s: return moviepy.VideoFileClip (moviepy==1.0.3) from an op → videos clickable in traces (https://docs.wandb.ai/weave/guides/tracking/video).

## Strongest loop design
clips → ingest (scenedetect, whisper words, per-clip VLM caption, beat grid)
→ PLANNER (Claude + playbook bullets) emits EDL JSON → validate deterministically
→ RENDER (ffmpeg; PIL captions)
→ CRITIC: hard scorers + VLM rubric (+ optional W&B Inference 2nd judge)
→ REVISE ≤3 rounds (Self-Refine), keep best-of
→ REFLECTOR: which bullets helped/hurt; new lessons → CURATOR: delta-merge into playbook.json (ACE counters)
→ next clip set / episode.
Demo: 3 clip sets × 3 episodes. Show (a) within-episode score climbing, (b) episode-1 score on a HELD-OUT clip set rising as playbook grows, (c) the playbook itself — human-sensible rules ("never cut mid-word; hold establishing shot ≥1.5s"). Ablation row: empty playbook vs learned playbook on held-out set.

## Top 3 risks
1. Judge noise swamps signal (VLM judges over-score, position bias: MM-JudgeBias 2604.18164). Mitigate: pairwise A/B vs previous render (swap order, average), temperature 0, hard scorers weighted ≥50%, trials=2.
2. Critic rewards wrong thing / playbook collapse (over-captioning, slow cuts). Counters, prune harmful>helpful, cap ~40 bullets, held-out set excluded from reflection.
3. Wall-clock: render+critique 45–90s → ~150 iterations overnight max. Freeze pipeline by hour 4; last hours = iterations + leaderboard. Don't touch VideoAgent/VideoScore/full GEPA.
