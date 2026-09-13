# Research: Idea 3 — manufacturing agent loop ("ForgeLoop")

(Research agent report, 2026-09-13 ~03:05 PDT)

## Event reality check
- Luma page: https://luma.com/coreweavehacks. Prior WeaveHacks 3 finalists (https://cerebralvalley.ai/e/weave-hacks-3-self-improving-agents-hackathon-with-weights-and-biases-7014fe80/hackathon/gallery): shader agent w/ visual-validation iteration, honeypot that learns defense rules, test-time training. Winning pattern: *Weave traces → judge scores → agent edits its own rules/prompts → measurable improvement curve*.
- Already-public entries this round: https://github.com/jwalin-shah/worldloop (self-improving context compiler), https://github.com/PranavAchar01/CoreWeave-Hacks-2026 (UI agent + harness-rewriting loop). Nobody visible doing physical parts.

## "AI-native" hardware companies
- No funded company literally brands itself "AI-native heat exchanger/valve manufacturer"; the X posts are thesis posts.
- Real ones: Hadrian ($1.37B Series D Aug 2026), Isembard ($50M, 25 AI factories), Machina Labs, Divergent — factory-side loop (CAM/quoting/inspection), not generative design.
- Heat exchangers: Diabatix ColdStream (generative thermal → CFD → AM), Fabric8Labs (acq. TDK $400M Jun 2026), Conflux. Loop needs CFD + test rig — not overnight.
- YC 2026: Prototyping.io ("identifies manufacturability issues early, delivers CNC/sheet/IM parts") is literally the idea as a company; Korso (quote-to-order); VIM (CNC fault recovery). a16z AD: Emanate (AI quoting for industrial piping sales).
- Tractable version: design → DFM/physics check → cost → revise.

## Tooling (verified on this Mac)
- CadQuery 2.8.0 / build123d 0.11.1; cadquery-ocp 8.0.1 has cp312 macOS arm64 wheels. `uv venv -p 3.12 && uv pip install cadquery build123d trimesh pyvista ht` should work. No ccx/gmsh/openscad on PATH.
- Text2CAD-Bench (May 2026, https://arxiv.org/abs/2605.18430): frontier LLMs writing CadQuery have 11–20% invalid-code rates on simple parts, 54–70% on L3/L4 (sweeps/lofts/shells). Keep parts L1–L2.
- Prior gen→render→VLM critic work: CADCodeVerify (ICLR'25, 2410.05340), EvoCAD (2510.11631), CAD-Coder (https://github.com/anniedoris/CAD-Coder), CQAsk. None has a manufacturability critic → differentiation.
- DFM checkers: OC-JG/DFM (MIT; wall thickness via ray-cast, per-face draft, undercuts vs pull axis; JS+OCC WASM: https://github.com/OC-JG/DFM) — port algorithms to trimesh. Rule values: Protolabs draft (0.5–2°, 3° textured), wall uniformity (adjacent walls within 40–60%).
- Physics-lite: `ht` 1.2.0 (effectiveness-NTU). FEA/CFD: skip. Zoo.dev text-to-CAD API: baseline only.

## Quoting APIs — none hackathon-callable
Xometry API is supplier-side; JLC3DP requires business review; Fictiv/Protolabs/SendCutSend web-only. Build a transparent cost model instead ("quote estimator"). Don't promise live quotes on stage.

## Recommended loop: "ForgeLoop"
Inner loop (per part, ~5 iters): Claude writes CadQuery from NL spec + target process → subprocess exec (timeout) → STL/STEP + 4 PNG views (pyvista offscreen) → deterministic critics: validity/watertight/volume, DFM score per process (thickness histogram, draft, undercuts, min radius, overhang), physics scalar (NTU/stress ratio), cost estimate, VLM spec-adherence → weighted reward → Claude patches code.
Outer loop: reflector reads Weave traces of failures and edits a versioned `dfm_playbook.md`. Run 8–12 parts across 3 processes; plot iterations-to-pass and first-shot DFM score improving as playbook grows. Demo: 3D viewer with red undercut faces turning green + the curve. `@weave.op` everywhere, EvaluationLogger per episode, Weave Datasets for the part suite.
Judge appeal: objective scorers (rare for LLM loops), reindustrialization narrative VCs fund, matches Prototyping.io/Hadrian.

## Top 3 risks
1. CadQuery codegen failure rate → constrain to L1–L2, helper library (make_enclosure, add_draft, add_fillets), timeouts, cache successes.
2. DFM checker correctness on tessellated meshes → run draft/undercut on B-rep faces (exact normals), mesh only for thickness; unit-test 3 fixtures (undercut box, thin wall, no-draft cup).
3. Fake self-improvement → start playbook empty, held-out part set, show a learned rule you didn't seed.
Skip: manufacturer APIs, FEA/CFD, ingesting user 2D drawings.
