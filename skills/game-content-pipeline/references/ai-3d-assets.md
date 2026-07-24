# AI Asset Generation — image→3D, mocap, textures

## Image → 3D model

### Local (RTX 5090 32GB is ideal)

| Tool | VRAM | Output | Notes |
|---|---|---|---|
| **Hunyuan3D-2.1** | ~20GB (texturing) | mesh + full PBR | github.com/Tencent-Hunyuan/Hunyuan3D-2.1, open weights. 3.0/3.1 are API-only (no confirmed open weights) |
| **TRELLIS.2-4B** | ~24GB | best OSS quality, 4K PBR | github.com/microsoft/TRELLIS.2 |
| TripoSR / SPAR3D | low | fast but subpar | legacy, prototyping only |

⚠️ Blackwell sm_120: install PyTorch from cu128 index (`pip install torch --index-url https://download.pytorch.org/whl/cu128`) or kernels won't load.

### Hosted API

| Service | Cost | Strength |
|---|---|---|
| **Tripo3D** (Stefan's sponsor/source) | $0.01/credit, 2,000 free | v3.1 PBR default, H3.1 quad-mesh HD |
| Meshy-6 | free ~200 credits/mo | weak: GLB/albedo-only export on free |
| Rodin/Hyper3D Gen-2 (via fal.ai) | pay-per-use | best topology control |

### Reality check

AI-generated **props are game-ready**; **hero characters are not** — plan Blender retopo + manual UVs for anything that deforms. Pipeline: generate → import GLB into Blender → decimate/retopo → fix scale (0.01 scene) → export per `blender-ue-export.md`.

## Video → mocap (free/local first)

1. **mocap-wrapper** (github.com/AClon314/mocap-wrapper): one command, GVHMR+TRAM+WiLoR, exports to Blender/UE. Best 2026 on-ramp.
2. Rokoko Vision: free tier, browser-based.
3. Mixamo: alive, free, frozen — still fine for stock cycles; retarget via UE IK Retargeter.
4. **Cascadeur** for cleanup/physics polish: Free tier = non-commercial + .casc only; **Indie $8/mo = FBX/USD export + UE Live Link**; Pro $49/mo.
5. UE 5.8 also ships video-to-animation natively — try it before adding tools.

## Text → texture / materials

- Meshy text-to-texture (free tier), Hunyuan3D-2.1 paint stage standalone (local).
- **StableProjectorz** — SD projection painting, open-sourced Jan 2026 (AGPL), free.
- Material Maker 1.4 — free procedural Substance alternative.
- Paid: Substance Texturing $24.99/mo or Painter 2026 perpetual ~$149 (Steam).

## Rigging

- Rigify (free, in Blender 5.1) — fine with practice.
- **Auto-Rig Pro $40** — solo-dev standard, UE export presets, worth it at first character.
- Meshy/Tripo auto-rig — prototype quality only.
- UE-side: IK Rig + IK Retargeter (near one-click since 5.4), Control Rig Physics (5.8 Beta).
