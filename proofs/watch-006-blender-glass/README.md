# watch-006 — Blender glass tutorial → compiled procedure → executed → judged → deterministic explainer

First end-to-end run of the whole Beast loop on one demonstration, 2026-10-25. Every
number below is in `replay-log.json` / `visual-validation.json`; nothing here is a claim
without a file behind it.

| Stage | Tool | Result |
|---|---|---|
| Watch | `beast watch` (timeline v3) | 80 frames, 2 reinspections (`watch-seek`), 43 transcript lines |
| Compile | `compile_visual_evidence.py` | 14 typed values **answered**; 4 never spoken; 2 negative controls refused |
| Gate | `validate_watch_procedure.py` | ok, 4 visual-only facts linked to frames |
| Execute | `execute_glass.py`, Blender 5.2.2 `-b`, OPTIX | socket readback == typed-state (3 runs) |
| Judge | `judge_image.py`, qwen3-vl:8b | 7 / 6 / 8 of 10 (material only; scene was never shown) |
| Export | GLB with KHR_materials_transmission + ior | `run3/tinted_glass.glb` |
| Explainer | HyperFrames + vendored Three.js/GSAP + Kokoro | 42 s; **two renders → identical MP4 (SHA-256)** |
| Replay elsewhere | spark1 (GB10, arm64) | GPU render, PNG-deterministic; **not** identical to the 5090 (fonts + driver) |

## Reproduce

```powershell
# evidence bundle is under evidence/ (frames cited by observations + timeline.json)
python scripts/compile_visual_evidence.py proofs/watch-006-blender-glass/evidence/typed-target.json `
  proofs/watch-006-blender-glass/evidence/typed-observations.json `
  proofs/watch-006-blender-glass/evidence/timeline.json out/typed-state.json
# expect status "answered", fingerprint 6ebd400a332d6d0c…
blender -b --factory-startup -P proofs/watch-006-blender-glass/execute_glass.py -- out/typed-state.json out/run
cd proofs/watch-006-blender-glass/explainer; hyperframes check; hyperframes render . -o ../out.mp4 -q high
```

## What this does and does not show

- Shows: on-screen values a transcript cannot supply can be recovered, bound to frames,
  type-checked, executed without a human, and judged locally — and the resulting video
  can be re-rendered bit-exactly on the same machine.
- Does not show: general tutorial-to-skill reliability (one tutorial, one app), a scene
  match (the tutorial's set was built off-camera), or cross-machine bit identity.
- Version gap handled explicitly: tutorial UI is Principled BSDF v1; execution mapped to
  v2 socket names (`procedure.json` → `uncertainties`).

## Incidents (kept, not hidden)

- First reference crops for transparent/frosted were swapped; the wrong judge scores (7/4)
  were discarded and the files kept in `superseded/`.
- Run 1 wrote renders to `C:\run1` (relative path resolved by Blender); fixed with `.resolve()`.
- yt-dlp 2026.07 got HTTP 403 from YouTube; upgrading fixed it. `beast update` does not
  cover yt-dlp yet.
- Spark needed the arm64 `chrome-headless-shell`; HyperFrames' auto-install picked x64.
