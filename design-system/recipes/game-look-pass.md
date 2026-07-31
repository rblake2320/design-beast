# Recipe — Game look pass (the anti-Roblox loop)

**Use for:** any UE/game work. This is the missing half of game building: logic passes
tests, but ONLY a screenshot judge can pass the *look*. A game that runs is not done —
it's a blockout.
**Tools:** UE MCP (screenshot + edit) · `scripts/judge_image.py` (qwen3-vl judge) ·
image→3D pipeline for hero assets · Fab/Quixel for commodity assets · HyperFrames or
Higgsfield for concept frames · 21st.dev (magic MCP) for HUD/menu UI design only.

## The iron rule
**Every game work session ends with a screenshot → judge → fix-list cycle.** The agent
must capture the actual viewport/PIE frame, run the judge with the art bible as rubric,
and treat a score < 8 exactly like a failing test. "It compiles and plays" is the
halfway point, not the finish line. An on-screen engine error (e.g. "LIGHTING NEEDS TO
BE REBUILT") in a screenshot is an automatic FAIL regardless of aesthetics.

## Why games rot while images shine
The image pipeline has enforced multi-candidate + judge. Game pipelines verify logic
(compiles, spawns, scores) — nothing looks at the screen. Result (RouteRush, 2026-07-31):
unbuilt-lighting error burned into every frame, untextured blockout boxes shipped as
art, zero post-processing, capsule player. The AI reported success because every check
it ran actually passed. Vision is the missing check.

## Order of operations
1. **Art bible BEFORE assets** — one page in the game repo: named look ("cel-shaded dawn
   suburbia"), 5-hex palette, lighting scenario (sun angle, sky gradient), 3 reference
   images (generate concept frames with Higgsfield using the cinematic-scene recipe —
   the target screenshot, not the current one). No bible → no asset work.
2. **Lighting + post FIRST, meshes second** — Lumen GI + directional sun with real angle
   + PostProcessVolume (filmic tonemap, bloom, AO, slight vignette, color grade to the
   palette). This upgrades every future asset for free. Kill all on-screen build errors.
3. **Materials pass** — a small library (6-10) of palette-locked stylized materials
   replaces per-face colors. Blockout boxes with good materials + good light already
   read as "indie stylized", not Roblox.
4. **Hero assets via the pipeline** — player character, vehicles, key props through
   image→3D (recipe: game-asset) or Fab/Quixel; commodity filler stays simple but
   materialed. LODs + collision on import (ROADMAP P3 has the validation checklist).
5. **HUD/UI pass** — design the HUD as real UI (magic MCP / 21st.dev patterns, one font,
   palette-locked, safe margins), then rebuild in UMG. Debug text is not a HUD.
6. **Judge loop** — PIE screenshot at 3 gameplay moments → judge_image.py with the art
   bible as rubric → fix list → iterate until ≥ 8. Save scored screenshots to the game
   repo so progress is visible.

## Judge rubric (pass to judge_image.py with the screenshot)
- Any engine warnings/errors visible on screen? (auto-fail)
- Does lighting have direction and mood, or is it default-noon flat?
- Do surfaces have materials, or flat per-face colors?
- Post-processing present? (crushed blacks/bloom/grade vs raw linear look)
- Would a stranger guess "shipped indie game" or "engine tutorial"?
- Does the frame match the art bible palette + references?

## Quality gates
- [ ] Art bible exists in the game repo and names the target look
- [ ] Zero on-screen engine errors in any captured frame
- [ ] Judge ≥ 8 on three distinct gameplay screenshots against the bible
- [ ] Side-by-side: current frame vs concept frame — a stranger sees the same game
