# UE 5.8 Automation — MCP, headless, splines, rendering, packaging

## Native MCP plugin (Experimental, 5.8)

- In-process server, HTTP+SSE, **loopback only** `http://127.0.0.1:8000/mcp`, no auth, rejects non-loopback Origins.
- Enable: Edit > Plugins > "Unreal MCP" (+ auto Toolset Registry) → restart.
- Console commands:
  - `ModelContextProtocol.StartServer [port]`
  - `ModelContextProtocol.GenerateClientConfig ClaudeCode` → writes `.mcp.json` to project root
  - `ModelContextProtocol.RefreshTools`
- Claude sees 3 meta-tools: `list_toolsets`, `describe_toolset`, `call_tool` over SceneTools / ActorTools / MaterialInstanceTools / ObjectTools. Extend in C++ via `UToolsetDefinition` / `UAgentSkill` (restart needed per new tool).
- **Launch `claude` from the project root** so it picks up `.mcp.json`.

## VibeUE layer

Registers ~34 skill packs on the SAME endpoint: landscape sculpting, foliage, PCG, MetaSounds, AnimBP, UMG widgets, profiling, lighting. Clone into `<Project>\Plugins\`, compile, done. Repo: github.com/kevinpbuckley/VibeUE (MIT, 5.8+ only, branch `5-8`).

Wider-coverage alternatives: tumourlove/monolith (1,400+ actions, no Python), db-lyon/ue-mcp (612+ actions, YAML flow engine), GenOrca/unreal-mcp (prebuilt 5.8 zip).

## Headless batch jobs (no editor UI)

```
"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "C:\Proj\Proj.uproject" -run=pythonscript -script="C:\jobs\import_assets.py"
```
- Or `-ExecutePythonScript="..."` for one-liners.
- Auto-run on editor start: `Content/Python/init_unreal.py`.
- Embedded Python is **3.11.8**, editor-only (not in packaged games).

## Splines (three kinds — pick right)

1. **Landscape splines** — roads/paths carved into terrain, terrain deformation.
2. **SplineMeshComponent** — mesh deformed along a spline (rails, pipes, rivers' meshes).
3. **PCG Draw Spline mode (5.7+)** — spline as PCG input for procedural scatter/roads; GPU path, ~2x faster; 5.8 adds manual-edits-preserved-through-procedural-regen. This is the 2026 default for anything repeated along a curve.

## Rendering clips

- **Movie Render Queue (MRQ)**: high-quality deterministic frames/video from Level Sequences. Headless: MRQ jobs are scriptable via `unreal.MoviePipelineQueueSubsystem` in a pythonscript run.
- Assemble frames: `ffmpeg -framerate 30 -i frame_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 out.mp4` (5090: `-c:v h264_nvenc` or `av1_nvenc` for speed).
- Concat clips: `ffmpeg -f concat -safe 0 -i list.txt -c copy final.mp4`.
- Mix sources freely: UE MRQ shots + Blender renders + Higgsfield Seedance AI shots → ffmpeg concat.

## Packaging a game

```
"C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun ^
  -project="C:\Proj\Proj.uproject" -noP4 -platform=Win64 ^
  -clientconfig=Shipping -build -cook -stage -pak ^
  -archive -archivedirectory="C:\Builds\Proj"
```
UBA (Unreal Build Accelerator) is GA since 5.5; Horde CI ships bundled if a build farm is ever wanted.

## 5.8 features worth reaching for

- **MetaHuman Creator fully in-engine** (characters without leaving UE).
- MegaLights Production-Ready; Lumen ~2x faster than 5.6.
- PCG Production-Ready + manual-edit preservation.
- Mesh Terrain (Experimental).
- Video-to-animation built in.
- Epic Developer Assistant (in-editor AI panel) — exists, but our MCP path is more controllable.

## Version control

- **Diversion** — Epic-recommended now, UE 5.8 docs page, free 5 users/100GB. Easiest.
- Perforce Helix Core — free ≤5 users, self-hosted, the studio standard.
- Git LFS — only for code-heavy prototypes with few binary assets.

## Fab assets

Fab = former Marketplace + Quixel. Free premium drop every 2 weeks (claim = keep forever). ~800 legacy Megascans free.
