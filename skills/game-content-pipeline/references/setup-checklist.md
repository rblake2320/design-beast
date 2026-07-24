# Setup Checklist — install order + verification

State on 2026-07-02: Blender 5.1.2 ✅ (bridge :9876), Higgsfield CLI 0.1.35 ✅ (Plus plan), Python 3.12 ✅, Node ✅, git-lfs ✅. Missing: UE 5.8, Visual Studio, ffmpeg, ImageMagick, rembg. C: has ~358GB free — enough but tight; clean up if below 200GB before UE install.

## 1. Unreal Engine 5.8 (~120 GB — C: conservative; D: OK after SMART check, repaired 2026-06-20)

No supported CLI/silent install — Epic Games Launcher is the path:

1. Download launcher: https://store.epicgames.com/download → install to C:.
2. Launcher → Unreal Engine tab → Library → `+` → **5.8.0** → install to `C:\Program Files\Epic Games\UE_5.8`.
3. Options: keep Starter Content + Templates; symbols optional (adds ~40GB — skip unless debugging engine crashes).

Verify: `ls "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"`

Notes: UE 5.8 (GA 2026-06-17) is the final UE5 major release; UE6 EA targeted end-2027. Licensing: free until $1M gross/title. Alternative scriptable path = source build (EpicGames/UnrealEngine tag `5.8.0-release`, needs Epic↔GitHub link, ~200–250GB + 1.5–3h) — only if launcher is unacceptable.

## 2. C++ toolchain — ALREADY SATISFIED on this machine

**VS Build Tools 2022 (17.14) with MSVC 14.44 + Windows SDK 10.0.26100 is installed** — that's all UnrealBuildTool needs to compile VibeUE and C++ projects (UE bundles its own .NET). Full Visual Studio is optional (only for IDE debugging); VS Code works fine as the editor.

Verify: `ls "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Tools/MSVC"` → version dir means OK.
If ever missing: `winget install -e --id Microsoft.VisualStudio.2022.BuildTools --override "--add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.Windows11SDK.26100 --includeRecommended --passive"`

## 3. Enable native Unreal MCP (UE 5.8, Experimental)

1. Create/open a project → Edit > Plugins → enable **"Unreal MCP"** (auto-enables Toolset Registry) → restart editor.
2. Console (` key): `ModelContextProtocol.StartServer` (default port 8000, loopback-only, no auth).
3. `ModelContextProtocol.GenerateClientConfig ClaudeCode` → writes `.mcp.json` in project root.
4. Launch `claude` from the project root — tools appear as `list_toolsets` / `describe_toolset` / `call_tool`.
5. After adding toolsets: `ModelContextProtocol.RefreshTools`.

Docs: https://dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor

## 4. VibeUE (the "made it better" layer from the Stefan 3D AI video)

**Pre-cloned at `C:\Users\techai\ue-plugins\VibeUE`** — copy that folder into `<YourProject>\Plugins\` (or re-clone):
```
cd <YourProject>\Plugins
git clone https://github.com/kevinpbuckley/VibeUE.git
```
Build: open the project (editor prompts to compile) or run `Plugins\VibeUE\BuildAndLaunchGame.ps1`. Requires step 2 (VS). MIT license, UE 5.8+ only, adds ~34 toolsets (landscape sculpting, foliage, MetaSounds, AnimBP, UMG, profiling) onto the same :8000/mcp endpoint. Site: vibeue.com.

Breadth alternatives if VibeUE lacks something: `tumourlove/monolith` (1,400+ actions, native C++, supports 5.7+5.8), `db-lyon/ue-mcp` (612+ actions + YAML flows), `GenOrca/unreal-mcp` (prebuilt 5.8 zip). AVOID chongdashu/unreal-mcp and kvick-games/UnrealMCP — unmaintained, pre-5.8.

## 5. ffmpeg + ImageMagick

```
winget install -e --id Gyan.FFmpeg
winget install -e --id ImageMagick.ImageMagick
```
Verify: `ffmpeg -version` / `magick -version` (new terminal for PATH).

## 6. Python imaging + background removal (5090 = CUDA 12.8 builds!)

```
pip install pillow
pip install "rembg[gpu,cli]"          # needs onnxruntime-gpu >= 1.21 for Blackwell
```
Use model **birefnet-general** for sprites. ⚠️ BRIA RMBG-2.0 is non-commercial — do NOT use for shipped games. Best trick: render sprites from Blender with Film > Transparent (RGBA) and skip removal entirely.

Verify: `python -c "import rembg, PIL; print('ok')"`

## 7. PaperZD (2D animation for Paper2D)

v2.2.4 (2026-06-23) explicitly supports UE 5.8. Free. Prebuilt binaries 5.2–5.8:
https://github.com/heavybullets/PaperZD/releases (or install via Fab). Drop into project `Plugins\`.

Optional 2D: **Odyssey** (Praxinos) — in-editor 2D drawing, free on Fab; verify 5.8 compat on its Fab listing first.

## 8. Optional but likely needed

| Tool | Why | Install |
|---|---|---|
| Tripo3D account | Best hosted image->3D ($0.01/credit, 2000 free) — Stefan's asset source | tripo3d.ai |
| Hunyuan3D-2.1 | Local image->3D w/ PBR, ~20GB VRAM (fits 5090) | github.com/Tencent-Hunyuan/Hunyuan3D-2.1 |
| TRELLIS.2-4B | Best open-source quality, 4K PBR, ~24GB VRAM | github.com/microsoft/TRELLIS.2 |
| mocap-wrapper | One-command video->mocap (GVHMR), Blender/UE export | github.com/AClon314/mocap-wrapper |
| Cascadeur Indie $8/mo | Physics-assisted animation, FBX/USD export + UE Live Link (free tier is non-commercial, .casc only) | cascadeur.com |
| Auto-Rig Pro $40 | De-facto solo rigging standard, UE export presets | Blender Market |
| Material Maker 1.4 + StableProjectorz | Free Substance alternative (StableProjectorz open-sourced Jan 2026) | materialmaker.org / stableprojectorz.com |
| Diversion | Epic-recommended VCS, free 5 users/100GB (Git LFS only for code-light prototypes) | diversion.dev |

## Audio / music licensing (do not skip)

- UE **MetaSounds**: built-in procedural audio, ship-safe.
- SFX: ElevenLabs SFX v2 (commercial on paid tiers), or local **Stable Audio Open** on the 5090.
- Music: **do NOT use Suno/Udio output in shipped games yet** — Sony v. Suno/Udio unresolved (ruling expected summer 2026). Use local models or CC0 until licensed.

## Fab (asset store)

Fab replaced Marketplace + Quixel Bridge. Claim the **free premium asset drop every 2 weeks** (keep forever). ~800 legacy Megascans still free.
