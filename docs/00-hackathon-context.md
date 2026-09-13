# CoreWeave Hacks (WeaveHacks) — Hackathon Context

Source: participant handbook + Luma event page + organizer announcements. Captured 2026-09-13 ~02:45 PDT (Saturday night / Sunday early morning of the hackathon).

## Key facts
- Event: CoreWeave Hacks: Agent Loops Hackathon, with Weights & Biases, AGI House, TypeSafe AI. 400 Alabama St ste 202, SF.
- Theme: **the loop**. Agents that cycle through reasoning and action, catch their own mistakes, and push toward better results at each pass. Self-improving agent iterations: observe, evaluate, track, document, self-improve.
- **Submissions due Sunday 2026-09-13 at 1:00 PM PDT** on the AGI House platform (submissions open 10 AM). Judging 1:30 PM. Presentations 3:30 PM. Awards 4:30 PM.
- Doors open Sunday 9 AM. Team must be present for finals + awards.
- 3-minute demo (strictly enforced), max 1–2 slides, heavy emphasis on live demo. Judges ask 1–2 questions. Zoom screen share (share.zoom.us).

## Eligibility
- Public GitHub repo. Entire project built at the hackathon. Commit early and often (proof of weekend work).
- **Must use W&B** (Weave — "2 lines of code"). Include the W&B project link (needn't be public).
- Any AI coding / vibecoding / ralph looping is fair game.
- Must be present in person.

## Judging criteria
1. **Best Loop.** Is the agent(s) self-correcting? How are they improving, iterating, bettering at each pass?
2. **Creativity.** Does the project meaningfully show a team of agents working well together?
3. **Utility.** Solves a real problem?
4. **Technical execution.** Does it work? Reasonable architecture?
5. **Sponsor usage.** Meaningful use of sponsor tools (Weave, ARIA, marimo/molab, TypeSafe AI, W&B Inference).
6. "2 weeks later" award: Most Production-Ready (announced at Fully Connected, Sep 29–Oct 1).

## Prizes
- Best Loop Design — robot dog ($4k) + $2k cash + stage time at Fully Connected. (All projects eligible.)
- Most Production-Ready — F1 tickets + $1k.
- Best Use of Weave — $1,000. Best Use of ARIA — $1,000. Best Use of marimo — $500.
- Best Social Media demo — $1,000. Best Use of TypeSafe AI — Hugging Face Microducks + swag.
- Track selection at submission: Best Use of Weave, Best Use of ARIA, or Best Use of marimo.

## Submission checklist (AGI House platform)
- Every team member signed in on AGI House platform + completed participant survey. One person submits.
- Unique team name; all member names; X/LinkedIn handles.
- Project name + 2–3 sentence description: what the agent does and **what makes the loop self-improving**.
- Public GitHub repo link.
- Track selection.
- Demo link or short screen-recording video (< 2 min); "make the loop easy to see fast".
- Thorough description: summary; what it's useful for; how it's built (RL environments, orchestration protocols like A2A/MCP, agent frameworks); **list of every sponsor tool/protocol and how used** (critical for sponsor + grand prizes).
- Post on social media right after.

## Sponsor resources
- W&B Weave docs: https://weave-docs.wandb.ai/ ; Weave + MCP: https://weave-docs.wandb.ai/guides/integrations/mcp/ ; example agent w/ MCP & OTEL: https://github.com/altryne/mcp-otel
- Weavify skill: `npx add-skill altryne/weavify-skill`
- W&B MCP server (hosted): https://mcp.withwandb.com/mcp with `Authorization: Bearer <WANDB_API_KEY>`. Claude Code: `claude mcp add --transport http wandb https://mcp.withwandb.com/mcp --header "Authorization: Bearer <key>"`. Lets the coding agent inspect runs/traces/evals and auto-improve.
- W&B Inference: wandb.me/inference ($100 credits via form; user has requested, not yet granted as of Sat night).
- ARIA docs: https://docs.wandb.ai/aria/overview (W&B in-app coding agent, Models Workspaces).
- marimo / molab: https://molab.marimo.io/ (free cloud GPU notebooks).
- TypeSafe AI: new lab, "machine-native intelligence" models; API access via request form.
- Discord: https://discord.com/invite/8sEeJuhV5. WiFi: W&B Guest / Gumption.

## Judges (for pitching angle)
Weave eng director (agent observability), ARIA PM (ex self-driving ML), marimo DevRel, TypeSafe COO (ex-FAIR), GDM researcher (personalization, AI for math), Okta principal eng (agent identity/security, production-ready agentic systems), Salesforce security eng, VCs/founders (YC, RL-environment data company Perit.ai, BenchFlow, Stably AI), Meta MLE (recsys), NVIDIA agentic AI DevRel, Rox applied AI (agent reliability), AGI House rep.
Takeaways: they care about observability, evals, measurable improvement, reliability, and a demo that makes the loop visible fast.
