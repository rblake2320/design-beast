# Design Beast — agent operating manual

Any AI agent (Claude Code, Codex, mesh peer) working in or from this repo follows this.

## Non-negotiables
1. **Doctor first.** `python scripts/doctor.py` before any pipeline work. Report what's
   degraded — never silently skip a missing tool.
2. **Quality loop always.** `design-system/QUALITY-LOOP.md`. No one-shot generations
   presented as deliverables. Minimum 4 candidates → judge → refine → upscale/grade.
3. **Recipes over freehand.** Match the ask to a card in `design-system/recipes/`.
   Product/marketplace work routes to the purpose-built Higgsfield skills — never
   freehand those prompts.
4. **Websites are built, not generated.** frontend-design/impeccable/theme-factory own
   layout; generated art fills slots only.

## Tool access map
| Capability | How to reach it |
|---|---|
| Higgsfield (image/video/soul) | `higgsfield` CLI + higgsfield-* skills (native Skill tool) |
| Blender 5.1 | mcp__blender__* tools, bridge :9876 — Blender must be RUNNING |
| Unreal Engine | UE first-party MCP `http://127.0.0.1:8000/mcp` + VibeUE; probe via `scripts/probe_unreal.ps1` in codex skill |
| 2D/3D/game pipeline | `skills/game-content-pipeline/SKILL.md` (also installed at `~/.claude/skills/`) |
| Web components | magic MCP (21st.dev) + frontend-design/impeccable skills |
| Local vision judge | `python scripts/judge_image.py` (Ollama llava) or Read the image directly |
| Sibling repos | `repos.yml` → `scripts/sync_repos.ps1` |

## Machine facts (verified 2026-07)
- RTX 5090 = Blackwell sm_120 → CUDA deps need cu128+ builds
- Blender bridge lives INSIDE Blender; launch it if :9876 is down
- Higgsfield auth expires → user runs `higgsfield auth login` (interactive)
- UE 5.6.1 at `D:\Epic Games\UE_5.6`; VS Build Tools 2022 = C++ builds OK

## Sync rule
The canonical skill lives in `~/.claude/skills/game-content-pipeline/`. If you improve it
there, copy changes into `skills/` here (and vice versa) in the same session.
