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
5. **Games get judged by their screenshots.** Every game/UE work session ends with a
   PIE/viewport screenshot → vision judge → fix-list cycle against the game's art bible
   (`design-system/recipes/game-look-pass.md`). "It compiles and plays" is a blockout,
   not a deliverable; an on-screen engine error in a frame is an automatic fail.
6. **Doors get logged, claims get receipts.** If implementation or research makes a
   previously unavailable capability possible, follow `docs/OPPORTUNITY-LEDGER.md`
   before moving on — preserve the triggering evidence, research prior art, assess
   value inside AND outside the current project, and route it deliberately (even
   when it doesn't serve the current task). No hype, no mockups presented as
   working: every capability statement carries the ledger's evidence language
   (observed/reproduced/measured/verified/generalized), and "novel" requires
   documented prior-art research.

## Tool access map
| Capability | How to reach it |
|---|---|
| Higgsfield (image/video/soul) | `higgsfield` CLI + higgsfield-* skills (native Skill tool) |
| Blender 5.1 | mcp__blender__* tools, bridge :9876 — Blender must be RUNNING |
| Unreal Engine | UE 5.8 first-party MCP `http://127.0.0.1:8000/mcp` (headless BeastLab; start via Studio Backends panel "unreal-mcp"); `/api/to_ue` imports go to UE 5.6 RouteRush — separate installs, both current |
| 2D/3D/game pipeline | `skills/game-content-pipeline/SKILL.md` (also installed at `~/.claude/skills/`) |
| Web components | magic MCP (21st.dev) + frontend-design/impeccable skills + ui-ux-pro-max plugin |
| Motion-graphic / HTML video | `/hyperframes` skill router + `npx hyperframes` CLI — recipe: `design-system/recipes/motion-graphic-video.md` |
| Faceless content pipeline | `D:\content\ai-content-engine` (topic → YouTube + shorts + thread + blog) |
| Local vision judge | `python scripts/judge_image.py` (Ollama llava) or Read the image directly |
| Real-time detection / QA | `D:\content\yolo-vision` venv — YOLO11 + YOLO-Face, 5.2 ms/frame GPU |
| Live library docs | context7 MCP (user scope) — use before writing framework code |
| Sibling repos | `repos.yml` → `scripts/sync_repos.ps1` |

## Machine facts (verified 2026-07)
- **UE 5.8 is the REQUIRED target for all new UE proofs and skill compilation**
  (user decision 2026-08-01, OPP-20260801-01): 5.8 docs only, disposable 5.8 GUI
  projects, record "5.8" in every manifest/skill, stop if a project opens under
  another version. UE 5.6 exists ONLY for the legacy /api/to_ue → RouteRush path;
  its findings are version-drift evidence, never implementation guidance.
- RTX 5090 = Blackwell sm_120 → CUDA deps need cu128+ builds
- Blender bridge lives INSIDE Blender; launch it if :9876 is down
- Higgsfield auth expires → user runs `higgsfield auth login` (interactive)
- UE 5.6.1 at `D:\Epic Games\UE_5.6` (used by /api/to_ue → RouteRush); UE 5.8 at
  `D:\DEpic GamesUE_5.8\UE_5.8` (garbled folder name, working install — do NOT move
  it) hosts the MCP via BeastLab; VS Build Tools 2022 = C++ builds OK

## Sync rule
The canonical skill lives in `~/.claude/skills/game-content-pipeline/`. If you improve it
there, copy changes into `skills/` here (and vice versa) in the same session.
