---
version: 0.1.0
name: game-content-pipeline
description: |
  End-to-end 2D/3D content + game creation pipeline to 2026 standards.
  Orchestrates: Blender 5.1 (MCP bridge :9876), Unreal Engine 5.8
  (native MCP :8000/mcp + VibeUE), Higgsfield AI (images/video),
  AI image-to-3D (Tripo API / Hunyuan3D-2.1 / TRELLIS.2 local),
  sprites (rembg -> Paper2D/PaperZD flipbooks), splines + PCG,
  animation/mocap (Rigify, mocap-wrapper, IK Retargeter), ffmpeg clip
  assembly, and RunUAT game packaging. Use when: "make a game",
  "create a 3D model/asset", "make a sprite/flipbook/sprite sheet",
  "spline road/river", "animate a character", "render a clip/cinematic",
  "build a level", "import to Unreal", "Blender to UE", "package the
  game", "image to 3D", "mocap", or any multi-tool 2D/3D content task.
  NOT for: standalone image/video generation with no 3D/game/sprite
  context (use higgsfield-generate), brand product photos
  (higgsfield-product-photoshoot), marketplace cards
  (higgsfield-marketplace-cards), Soul training (higgsfield-soul-id).
argument-hint: "[what to create] [--2d|--3d|--game|--clip|--doctor]"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, ToolSearch, WebFetch
---

# Game & Media Content Pipeline

One skill, whole pipeline: idea -> assets -> animation -> engine -> packaged game or rendered video. Chains Blender, Unreal Engine 5.8, Higgsfield, and AI asset generators. Everything below assumes Windows 11 + RTX 5090 (32GB) + 128GB RAM.

## Step 0 — Doctor (ALWAYS run first)

```bash
python ~/.claude/skills/game-content-pipeline/scripts/doctor.py
```

It checks every dependency (Blender bridge, UE 5.8, Unreal MCP plugin config, VibeUE, Visual Studio, Higgsfield auth, ffmpeg, rembg/Pillow, disk space) and prints exact install commands for anything missing. **Do not silently skip a missing tool — tell the user what's degraded.** If UE is missing, the full install order is in `references/setup-checklist.md`.

Hard rules discovered on this machine:
- **UE install drive:** D: failed June 2026 but was chkdsk-repaired 2026-06-20 and verified clean 2026-07-02. C: (383GB free) is the conservative pick; D: (2.3TB free) is acceptable once a SMART check passes. If NTFS event ID 50/140 ever reappear for D:, stop using it and check the runbook in Owner's Inbox.
- Blender MCP tools only respond while **Blender is running** (bridge lives inside it, port 9876). Launch it if down: `powershell -Command "Start-Process 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe'"` — if PowerShell is denied, `cmd //c start "" "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"`.
- Higgsfield auth expires; `higgsfield account status` -> if expired, user must run `! higgsfield auth login` themselves (interactive browser flow).
- RTX 5090 is Blackwell **sm_120**: any CUDA Python dep needs **CUDA 12.8+ builds** (PyTorch cu128 index, onnxruntime-gpu >= 1.21) or it fails with "no kernel image".

## Routing table

| Ask | Pipeline | Reference |
|---|---|---|
| Concept art, textures, 2D images | Higgsfield (GPT Image 2 / Nano Banana) via `higgsfield-generate` skill | — |
| Sprite / sprite sheet / flipbook | Higgsfield -> rembg -> `sprite_slice.py` -> Paper2D JSON import -> PaperZD | `references/2d-sprites.md` |
| 3D prop / environment asset | AI image->3D (Tripo API or Hunyuan3D local) -> Blender cleanup -> UE | `references/ai-3d-assets.md` |
| Precise / hard-surface 3D model | Blender MCP tools directly (procedural modeling, modifiers, geo nodes) | `references/blender-ue-export.md` |
| Character + rig | Blender Rigify or Auto-Rig Pro -> FBX -> UE IK Rig/Retargeter | `references/blender-ue-export.md` |
| Animation from video | mocap-wrapper (GVHMR) -> Blender -> UE | `references/ai-3d-assets.md` |
| Roads / rivers / fences / rails | UE splines: PCG Draw Spline mode (5.7+), SplineMeshComponent, landscape splines | `references/ue-automation.md` |
| Level / world building | UE 5.8 native MCP + VibeUE toolsets (landscape, foliage, PCG, lighting) | `references/ue-automation.md` |
| Cinematic clip / video | Blender render OR UE Movie Render Queue -> frames -> ffmpeg; or Higgsfield Seedance for AI shots | `references/ue-automation.md` |
| 3D / 2.5D game | UE 5.8 project + MCP-driven editing + RunUAT package | `references/ue-automation.md` |
| Pure 2D game | UE Paper2D+PaperZD works; **say honestly**: pure-2D is often better served by Godot — UE wins at 2.5D (sprites inside Lumen/Nanite worlds) | `references/2d-sprites.md` |
| Game audio | UE MetaSounds (built-in); local Stable Audio Open on the 5090. **No Suno/Udio for shipped games** until the Sony lawsuit resolves | `references/setup-checklist.md` |

## Non-negotiable conventions (Blender -> UE)

1. Blender scene: Metric, **Unit Scale 0.01**, Apply All Transforms before export. (Default scale imports skeletons with 0.01-scale bones — this is the classic face-plant.)
2. **FBX for skeletal** meshes/anims/morphs: Scale 1.0, Apply Scalings = FBX All, -Z Forward / Y Up, Smoothing = Face, Tangent Space ON, `add_leaf_bones=False`.
3. **GLB for static** meshes with PBR materials (Interchange maps metallic-roughness to Material Instances automatically).
4. Export headless: `blender -b file.blend -P scripts/blender_export.py -- --out asset.fbx --skeletal` — do NOT depend on the Send-to-Unreal addon (untested on Blender 5.1/UE 5.8).
5. Nanite: opaque/masked materials only, no LODs needed. Lumen: no lightmap UVs needed.

## UE 5.8 control — two modes

- **Interactive (editor open):** native MCP at `http://127.0.0.1:8000/mcp`. In-editor console: `ModelContextProtocol.StartServer` then `ModelContextProtocol.GenerateClientConfig ClaudeCode` (writes `.mcp.json` into project root — launch `claude` from there). VibeUE adds ~34 toolsets on the same endpoint. `ModelContextProtocol.RefreshTools` after changes.
- **Headless (batch):** `"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "Proj.uproject" -run=pythonscript -script="job.py"` — imports, builds, renders without UI. Auto-run scripts: `Content/Python/init_unreal.py`.

Package a game: `RunUAT.bat BuildCookRun -project=<.uproject> -noP4 -platform=Win64 -clientconfig=Shipping -build -cook -stage -pak -archive -archivedirectory=<out>`.

## Workflow skeleton (any request)

1. Doctor. Report degraded capabilities up front.
2. Classify the ask via the routing table; state the plan in one short paragraph.
3. Generate/author assets (Higgsfield / AI-3D / Blender MCP).
4. Normalize + export (conventions above; scripts in `scripts/`).
5. Import to UE (MCP interactive or headless python) / assemble with ffmpeg.
6. Verify: screenshot (`take_screenshot` in Blender, viewport shot in UE) or play the output file. Never claim done without looking at the result.
7. Ship: rendered file to `C:\Users\techai\PKA testing\Owner's Inbox\`, or packaged build path.

## Scripts

- `scripts/doctor.py` — full environment check with fix commands.
- `scripts/blender_export.py` — headless bpy exporter (FBX skeletal / GLB static, correct scale+axis flags).
- `scripts/sprite_slice.py` — sprite-sheet slicer -> per-frame PNGs + TexturePacker-style JSON that Paper2D imports natively.

## References (read the one you need)

- `references/setup-checklist.md` — full install order UE 5.8 + VibeUE + everything, with verify commands. **Read before any install work.**
- `references/blender-ue-export.md` — bpy export snippets, Interchange notes, rigging paths.
- `references/2d-sprites.md` — Higgsfield -> sprite -> flipbook, PaperZD, Odyssey.
- `references/ai-3d-assets.md` — image->3D (local + API), mocap, retopo caveats.
- `references/ue-automation.md` — MCP setup detail, headless jobs, splines/PCG, Movie Render Queue, packaging, VCS.
