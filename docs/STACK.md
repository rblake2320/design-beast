# Stack inventory — what this machine can build and run

One line per capability; re-verify dates when checked. Machine: Windows 11, RTX 5090
32GB, 128GB RAM, Python 3.12.

## Create
| Tool | Access | Status |
|---|---|---|
| Higgsfield CLI | `higgsfield` — GPT Image 2, Nano Banana 2/Pro, Seedance 2.0, Kling 3.0, Marketing Studio, Soul ID | ✅ 2026-07-19 |
| Blender 5.1.2 | MCP bridge :9876 (~50 tools) — model, geo nodes, physics, animate, render | ✅ 2026-07 |
| Unreal Engine 5.8 | `D:\DEpic GamesUE_5.8\UE_5.8` (folder name is garbled but the install works — do not move it); hosts first-party MCP :8000/mcp via headless BeastLab project (`D:\Epic Games\Projects\BeastLab`); toggled from the Studio Backends panel | ✅ 2026-07-26 |
| Unreal Engine 5.6.1 | `D:\Epic Games\UE_5.6`; used by `/api/to_ue` to import into the RouteRush project (`C:\Users\techai\route-rush-unreal`); VibeUE staged at `~\ue-plugins\VibeUE` (not compiled into either engine) | ✅ 2026-07-19 |
| NVIDIA ACE | Audio2Face-3D lip-sync + Claire/James/Mark models, staged `~\nvidia-blueprints\` | ✅ 2026-07-19 |
| Image-to-3D | Tripo API / Hunyuan3D-2.1 / TRELLIS.2 (both fit on 5090) | per pipeline skill |
| ffmpeg 8.1.2 / ImageMagick 7.1.2 / rembg[gpu] | CLI — assembly, grading, background removal | ✅ 2026-07-02 |
| HyperFrames 0.7.86 | `npx hyperframes` — HTML/CSS/GSAP → deterministic MP4/WebM; 27 agent skills (`/hyperframes` router + 10 workflows); Studio preview; renders ~15s/8s-clip local | ✅ 2026-07-31 |
| ai-content-engine | `D:\content\ai-content-engine` — faceless long-form YouTube + shorts + thread + blog from one topic (Claude script → ElevenLabs → ffmpeg) | cloned 2026-07-31, needs .env keys |

## Design skills (native Skill tool)
frontend-design · impeccable · theme-factory · dataviz · algorithmic-art ·
game-content-pipeline · higgsfield-generate / -product-photoshoot / -marketplace-cards /
-soul-id · web-artifacts-builder · magic MCP (21st.dev components) ·
**hyperframes family** (router + motion-graphics, product-launch-video,
faceless-explainer, pr-to-video, talking-head-recut, embedded-captions, music-to-video,
slideshow, general-video + core/animation/keyframes/creative/registry/cli/media-use) ·
**ui-ux-pro-max** plugin (240+ styles, 127 font pairings, 99 UX rules) ·
**context7 MCP** (live library docs — kills API hallucination in frontend code)

## Local AI (free)
Ollama :11434 — gemma3 (instant), qwen3.6:27b, nemotron-cascade-2:30b, llama4:scout,
**llava:7b (vision — powers judge_image.py)**, bge-m3 (embeddings)

## Automation
playwright-cli + claude-in-chrome (screenshots of built sites for judging) ·
Win32/SelfConnect desktop control · gh CLI

## Vision / detection (real-time QA eyes)
`D:\content\yolo-vision` venv — torch 2.11+cu128, OpenCV 5.0, Ultralytics 8.4 YOLO11 +
community YOLO-Face (`models/yolov11n-face.pt`); 5.2 ms/frame on the 5090. ✅ 2026-07-31.
Use cases here: auto-QA renders (faces/objects where expected), webcam-reactive demos,
counting/detection overlays for content.

## Known constraints
- sm_120 (Blackwell): CUDA Python deps need cu128 builds or "no kernel image" — this
  includes PyTorch: `pip install torch --index-url .../whl/cu128` BEFORE ultralytics
- HyperFrames gotchas live in `design-system/recipes/motion-graphic-video.md` (root
  index.html, init silent-fail on nested paths, radial-gradient squares, ffmpeg PATH)
- BRIA RMBG-2.0 is non-commercial — use birefnet-general for shippable work
- AI music (Suno/Udio) not ship-safe until Sony suit resolves
- Two UE installs coexist on purpose: 5.8 serves the MCP (BeastLab), 5.6.1 serves
  `/api/to_ue` (RouteRush). Migrating to_ue to 5.8 is future work — do not assume
  one engine does both.
