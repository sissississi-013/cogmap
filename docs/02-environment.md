# Local Environment (checked 2026-09-13 02:50 PDT)

- macOS (Darwin 25.2, Apple Silicon). Working dir: /Users/sissi/weavehacks (empty, not a git repo yet).
- Python: /opt/homebrew python3 = 3.14 (has anthropic, openai, opencv, pillow, numpy). **Python 3.12 framework** at /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 has: modal 1.3.5, torch 2.10, torchvision, anthropic 0.93, openai 2.38, openai-agents, opencv, pillow, numpy 2.0.2, OTEL instrumentation. `uv` available → use `uv venv` per project for a clean env.
- **Not installed**: wandb, weave (pip install needed). No WANDB_API_KEY in env, no ~/.netrc.
- Keys in env: ANTHROPIC_API_KEY, OPENAI_API_KEY. (W&B Inference / TypeSafe: not yet.)
- Modal: logged in as profile `sissiwang`; existing apps/volumes present; GPU available via CLI.
- ffmpeg 8.0.1 (homebrew) — has xfade/overlay/colorbalance/curves, **lacks drawtext and subtitles/libass** (no freetype). Caption overlays must be rendered with PIL to PNG and composited with `overlay`, or reinstall ffmpeg with freetype.
- gh CLI logged in as `sissississi-013`. Claude Code MCPs connected: github, vercel, neon, raindrop, linear.
- Sample raw footage on disk: ~/Movies/hoohoo.mov, ~/Movies/Vlog3-Gecko.mov, ~/Downloads/IMG_6341.MOV, IMG_3114 (1).MOV, IMG_4378.MOV, etc.
- Fonts: /System/Library/Fonts/Supplemental/Arial Bold.ttf etc.
- Ralph loop plugin installed (`/ralph-loop "<prompt>" --completion-promise X --max-iterations N`); state in .claude/ralph-loop.local.md; Stop hook re-feeds the same prompt.
