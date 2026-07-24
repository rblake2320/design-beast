# End-to-end pipelines

Every pipeline starts with `python scripts/doctor.py` and runs the quality loop
(`design-system/QUALITY-LOOP.md`) at each generation step.

## 1. Idea → shipped landing page
theme-factory (palette+type) → frontend-design (build page) → Higgsfield slot art
(palette in prompt, recipe: web-hero-and-site) → grade images to palette → impeccable
review pass → playwright screenshot → judge → iterate.

## 2. Photo/idea → 3D asset in Unreal
Higgsfield concept (recipe: cinematic-scene, pick winner) → image-to-3D (Tripo/Hunyuan3D)
→ Blender MCP cleanup (decimate, materials, Unit Scale 0.01) → `blender_export.py` FBX/GLB
→ UE import via UE MCP. Details: `skills/game-content-pipeline/references/ai-3d-assets.md`.

## 3. Character → animated presence
Canonical sheet (recipe: consistent-character) → Soul ID or Nano Banana ref edits for
expression set → Seedance image-to-video for motion clips → ffmpeg assembly. For 3D:
sheet → image-to-3D → Rigify rig → UE IK Retargeter → ACE Audio2Face for lip-sync.

## 4. Sprite game content
Higgsfield sprite gen → rembg birefnet-general → `sprite_slice.py` → Paper2D JSON →
PaperZD flipbooks. Details: `skills/game-content-pipeline/references/2d-sprites.md`.

## 5. Ad / marketing video
Product hero set (recipe: product-hero, restyle mode for variants) → Marketing Studio
(avatars, hooks) or Seedance i2v → ffmpeg cut + LUT grade → virality check
(`brain_activity` predictor in higgsfield-generate skill).

## 6. Full game
`skills/game-content-pipeline/SKILL.md` end-to-end: assets (above) → UE MCP + VibeUE
level work → splines/PCG → RunUAT packaging.
