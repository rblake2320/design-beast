# 2D Pipeline — AI images → Sprites → Flipbooks → Game

## Full chain

```
Higgsfield (Nano Banana 2/Pro for characters, GPT Image 2 for tiles/UI)
  → rembg birefnet-general (skip if generated on solid bg you can key, or...)
  → sprite_slice.py (grid slice + Paper2D JSON)
  → UE: Paper2D JSON sprite-sheet import → Create Flipbook
  → PaperZD AnimBP (state machines, notifies, directional anims)
```

## 1. Generate frames (Higgsfield)

Use the `higgsfield-generate` skill. For animation frames, generate a **sprite sheet in one image** (consistent character across cells) — prompt for "sprite sheet, N frames, walk cycle, side view, uniform grid, plain white background". Nano Banana Pro handles reference-driven consistency; pass the character reference image for every sheet so all animations match.

Better consistency trick: generate ONE character turnaround, then image-to-image each pose.

## 2. Background removal

```bash
rembg i -m birefnet-general input.png output.png       # single
rembg p -m birefnet-general in_dir/ out_dir/           # batch
```
- birefnet-general = practical winner for sprites.
- ⚠️ BRIA RMBG-2.0 slightly better on hair but **non-commercial license** — never in shipped games.
- If frames come from Blender renders: Film > Transparent gives clean RGBA, skip rembg.

## 3. Slice + descriptor

```bash
python scripts/sprite_slice.py sheet.png --cols 8 --rows 4 --out-dir sprites/ --json sheet.paper2d.json
```
Produces per-frame PNGs plus a TexturePacker-style JSON **that Paper2D imports natively** (right-click JSON in Content Browser → import creates textures, sprites, and optionally flipbooks).

Manual editor route (small jobs): import PNG → right-click → Sprite Actions → Apply Paper2D Texture Settings → Extract Sprites (grid or island detect) → select sprites → Create Flipbook.

Python-in-editor route: `unreal.PaperSpriteFactory` — works, thinly documented, keep as fallback.

## 4. Paper2D texture settings

Apply to every sprite texture: Filter = Nearest (pixel art) or Bilinear (HD), Compression = UserInterface2D or Masked, Mip Gen = NoMipmaps, sRGB on.

## 5. PaperZD (REQUIRED for real 2D animation)

Paper2D alone has no anim state machines. PaperZD v2.2.4 (2026-06-23, supports UE 5.8, free): AnimBP for flipbooks, state machines, anim notifies, directional (8-way) sequences. Prebuilt: https://github.com/heavybullets/PaperZD/releases → project `Plugins\`.

## 6. Splines in 2D/2.5D

- SplineMeshComponent: deform meshes along spline (pipes, vines, rails).
- Landscape splines: roads carved into terrain.
- PCG Draw Spline mode (5.7+): spline-driven procedural scattering — the 2026 way (GPU path, ~2x faster).

## Honesty rule

Pure-2D game with no 3D elements? Say it: **Godot is the better pure-2D engine.** UE earns its weight at **2.5D** — sprites/flipbooks living inside Lumen-lit, Nanite, PCG-built 3D worlds — and when the team already lives in UE. Paper2D is frozen (no feature dev since ~2018) but ships and works in 5.8; PaperZD fills the gap.

## Odyssey (optional)

Praxinos Odyssey: draw/animate 2D frame-by-frame inside the UE editor. Free on Fab since June 2025. ⚠️ Verify UE 5.8 compat on the Fab listing before recommending.
