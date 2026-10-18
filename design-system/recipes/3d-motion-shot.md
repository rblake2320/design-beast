# Recipe — 3D motion shot (Three.js inside HyperFrames)

**Use for:** product spins, 3D logo stings, hero objects, particle/shader plates — real
depth that CSS can only fake. GLB in, deterministic MP4 out.
**Tools:** `/hyperframes-animation` skill → `adapters/three.md` (the contract) + Three.js
vendored into the project. Models from Studio image→3D (`/api/to3d`, TRELLIS → `model.glb`),
Blender (free), or Meshy (credits — confirm first).
**Not for:** photoreal lighting (→ Blender render) or interactive worlds (→ UE).

## The contract (from the adapter — break it and frames drift)
- Render from HyperFrames time only: listen for `hf-seek`, draw `event.detail.time`;
  initial frame from `window.__hfThreeTime`. No `Date.now()`, rAF loops, or clock deltas.
- Root `[data-composition-id]` MUST carry `data-duration` — the three adapter can't infer it.
- No GSAP timeline? Add `data-no-timeline` to the root, or lint errors
  (`missing_timeline_registry`) and every render waits an extra 45 s.
- Pin `renderer.setSize(W, H, false)` + `setPixelRatio(1)`.
- Load models via `GLTFLoader` (goes through `DefaultLoadingManager`, so the runtime waits).
  Heavy CPU setup after load → register `window.__hf.buildReady[...]`.
- Lit meshes need a fill (`HemisphereLight`) or the dark side renders as a black cutout.
- Generated GLBs arrive at arbitrary scale/offset (a TRELLIS chest filled ~5% of frame
  with lights tuned for a unit Blender torus). Fit it on load: `Box3().setFromObject`
  → recenter, scale to a target size, then tune light intensity from the contact sheet.

## Local-first: vendor Three.js, never CDN at render time
```powershell
npm pack three@0.181.2; tar -xzf three-0.181.2.tgz
# copy into <project>/vendor/three/: build/three.module.js + build/three.core.js,
# examples/jsm/loaders/GLTFLoader.js + examples/jsm/utils/BufferGeometryUtils.js, LICENSE
```
```html
<script type="importmap">
  { "imports": { "three": "./vendor/three/build/three.module.js",
                 "three/addons/": "./vendor/three/examples/jsm/" } }
</script>
```
Same version everywhere. Model files go in `assets/` — never fetched from the web.

## GLB from Blender, headless
`blender -b --factory-startup -P make_model.py -- out.glb` with
`bpy.ops.export_scene.gltf(filepath=..., export_format='GLB')` — PBR Principled
material values carry over (metallic/roughness/base color).

## Order of operations
1. Model → `assets/*.glb`; vendor Three.js; write `index.html` per the contract
2. `hyperframes lint` → `hyperframes check` (0 errors)
3. `hyperframes snapshot --at <start,mid,last-frame>` → inspect contact sheet
4. `hyperframes render . -q high -o renders/shot.mp4`

## Verified on this box (2026-10-18, HyperFrames 0.8.169, three 0.181.2)
- Headless Chrome used the GPU in both snapshot and render:
  `ANGLE (NVIDIA GeForce RTX 5090 ... Direct3D11)` — not SwiftShader.
- 5 s 1080p30 GLB spin rendered in ~16 s; two renders were frame-identical
  (150/150 framemd5 match).
- A real Studio TRELLIS `model.glb` (textured, 2.2 MB) loaded and spun with textures intact.
- To re-check the GPU, temporarily print `WEBGL_debug_renderer_info`'s
  `UNMASKED_RENDERER_WEBGL` into an on-screen text clip, then remove it.

## Quality gates
- [ ] lint + check clean; no `https://` imports or assets in the composition
- [ ] Contact sheet: first frame, mid, and last frame (`(ceil(dur*fps)-1)/fps`)
- [ ] Camera cuts checked on the frame before and after each cut
- [ ] Shaders: clamp cosines before `pow(1 - c, n)` (lint: `shader_unbounded_cosine_pow`)
