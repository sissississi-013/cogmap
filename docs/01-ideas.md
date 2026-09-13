# Project Ideas (from Sissi, Sat night 2026-09-13)

Central theme: build the best **loop** — recursively self-improving agents on something interesting and visual. GPU training, if any, runs on **Modal** (already set up, CLI-based) since W&B credits weren't granted yet.

## Idea 1 — Self-improving video editing agent (Sissi's strongest interest)
- Long-standing interest: RL in a multimodal / vision setting.
- Goal: agents get better at editing videos and at understanding what the user wants from a seed video. Turn random raw phone clips into a well-edited short, or something more film-like.
- Multimodal capabilities to benchmark/evaluate: captions; identifying the subject; separating subject from background; background treatment; layer ordering (e.g. text *behind* the subject vs on top); filters; visual effects; music; cuts.
- Wants RL-style environments that make agents better at understanding and editing video.

## Idea 2 — Robots navigating any space from a phone scan
- Buy a Unitree (G1/Go2); it knows nothing about your home. How does it build a cognitive map?
- Walk around with a phone, scan the space, build a world model, simulate a swarm of agents wandering it; move objects and check they still navigate; on detecting a change, RL recursively updates understanding of the space.
- Publicly shareable world models of spaces as digital assets / training environments for robots; multiple terrains (snow, fields, greenhouses) — friends in ag-tech robotics struggle with non-flat domains. Scan a field with a phone → simulate → transfer to robots.

## Idea 3 — Manufacturing loop (most underdeveloped)
- Given a BOM + 2D/3D files, visualize the part, decompose it, find the best manufacturer. Seen posts on X about AI-native heat exchanger / valve / piping / hydraulics manufacturers — is there a loop there? Relevant to what Sissi is building company-wise. Visual is better for a competition.

## Constraints / preferences
- Sissi is going to sleep; Claude runs a Ralph loop overnight to complete the project. Submission 1 PM Sunday.
- Open to running two directories/projects in parallel if two ideas are both strong.
- Claude should do extensive research (GitHub, arXiv, blogs) per idea, then pick (or propose better), and list any sign-ups/auth Sissi must do before sleeping.
