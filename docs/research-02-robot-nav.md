# Research: Idea 2 — phone scan → world model → self-repairing navigation swarm

(Research agent report, 2026-09-13 ~03:00 PDT)

## Phone video → 3D: what the 2026 stack costs
| Tool | Output | Time (1-min phone video) | Verdict |
|---|---|---|---|
| VGGT / VGGT-Omega (feed-forward; https://github.com/facebookresearch/vggt , https://github.com/facebookresearch/vggt-omega) | poses + dense point map + depth in <1s forward pass on A100; commercial-OK weights; exports COLMAP for gsplat | ~5 min Modal cold start; 100 frames@518px needs 10–20GB VRAM (A100 fine; low-VRAM fork https://github.com/harry7557558/vggt-low-vram) | Best 3D option. Point map → height threshold → 2D occupancy grid is ~30 lines numpy. |
| Nerfstudio Splatfacto / gsplat | photoreal .ply splat | COLMAP 10–30 min + train 10–20 min A100; no mesh export | Pretty, useless for nav without mesh step. Skip/hero visual only. |
| Scaniverse (free, on-device) | splat + mesh OBJ/GLB in 2–5 min on phone | 0 GPU | Cheapest 3D. Polycam free = GLTF only. |
| Apple RoomPlan | parametric walls/furniture USDZ/JSON | realtime, LiDAR iPhone, needs Swift app | only if app already exists |
| Isaac Sim 6.0 + NuRec | splat-in-USD + robots | Linux+CUDA+RTX GUI | not in 10h |

Splat→navmesh is an open problem: Habitat-GS (https://github.com/zju3dv/habitat-gs) hand-draws walkable area; EmbodiedSplat (https://arxiv.org/abs/2509.17430) uses Polycam meshes + Habitat navmesh at SLURM scale; Splat-Nav (https://arxiv.org/abs/2403.02751) plans in splats via polytope corridors.

## Simulators
- Habitat-Sim: Linux-first, arm64 macOS flaky (issue 2358). Not tonight.
- Genesis (`pip install genesis-world`, Mac Metal, mesh_to_heightfield, Go2 example): cosmetic layer only, hours 7–9 if free.
- MuJoCo: fine on Mac, but nav on scanned mesh = all glue code.
- 2D occupancy grid + A*/tabular RL pure Python: minutes to build; this is where the loop lives.
- Semantic maps: VLMaps, ConceptGraphs, osmAG-LLM (https://arxiv.org/pdf/2507.12753) all = "serialized scene graph → LLM subgoal → geometric planner"; ~200 lines with a VLM.

## Change detection / scene-graph repair papers
- DSG (Sept 2026, https://arxiv.org/html/2609.00619): Stable/Appeared/Missing via render-vs-observe SSIM + VLM; Dyn-THOR benchmark. No code.
- DynamicGSG (2502.15309), LOST-3DSG (2601.02905), Multi-Modal 3DSG Updater (2411.02938): LLM classifies moved/added/removed.
- GraphPad (2506.01174): inference-time scene-graph edits by an agent.
- KeySG (2510.01049) / GPT4Scene (2501.01428): keyframes + VLM + object IDs → scene graph. Directly copyable.
- Splatblox (2511.18525): outdoor traversability (grass passable, trees not); borrow as 2D cost layer.

## Feasibility (one Claude agent, 10h, Mac + Modal)
Doable: keyframes → VLM scene graph + coarse grid → swarm nav → perturb → detect → repair → metrics in Weave. Not doable: real 3D sim install, Habitat-GS, Isaac, navigable splat. VGGT-on-Modal = optional 1–2h upgrade for a real occupancy grid + point-cloud screenshot.

### Most demo-able loop
scan.mp4 → ffmpeg keyframes → VLM (Claude) → SceneGraph v0 {objects, rooms, adjacency, blocked cells}
→ N simulated agents (A* + noisy execution) run K tasks ("go to the chair") [weave EvaluationLogger model="map_v{i}"]
→ failures (collision / goal-not-found) with the frame the agent "saw"
→ VLM diff old node vs new keyframe → {moved, removed, added}
→ LLM proposes graph edit → re-plan → re-run → Weave compare success rate map_v0→v1→v2 → loop until success ≥ τ.
Second nested loop: prompt/policy optimizer edits the nav heuristic prompt when a failure class repeats.
Demo (3 min): 30s phone walkthrough; graph+grid appear; swarm succeeds; physically move a chair, record 10s; agents fail; detector flags "chair moved doorway→corridor"; map repairs; success curve climbs in Weave. Agri angle: traversability cost layer (VLM labels cells grass/mud/row/obstacle).

### Hour budget
0–1 keyframes + VLM scene graph JSON; 1–3 grid world, A* agents, task suite, Weave; 3–5 perturbation + VLM change detector + repair; 5–6 loop + Weave compare + plots; 6–8 optional VGGT on Modal; 8–9 optional Genesis Go2 B-roll; 9–10 rehearsal + README.

### Top 3 risks
1. VLM spatial hallucination — scene graph has no metric truth; agents may "succeed" on a fake map. Mitigate: coarse grid (20×20), per-object confidence, one hand-labeled ground-truth grid.
2. 3D rabbit hole — COLMAP/CUDA/Modal image builds eat 3h with nothing visible. Rule: VGGT only after hour 6, in a separate Modal function.
3. Loop that doesn't visibly improve — if change detection is unreliable, success curve is flat. Scripted, large perturbations; log detector P/R in Weave; deterministic replay seed for the live demo.
