# Stack inventory — what this machine can build and run

One line per capability; re-verify dates when checked. Machine: Windows 11, RTX 5090
32GB, 128GB RAM, Python 3.12.

## Create
| Tool | Access | Status |
|---|---|---|
| Higgsfield CLI | `higgsfield` — GPT Image 2, Nano Banana 2/Pro, Seedance 2.0, Kling 3.0, Marketing Studio, Soul ID | ✅ 2026-07-19 |
| Blender 5.1.2 | MCP bridge :9876 (~50 tools) — model, geo nodes, physics, animate, render | ✅ 2026-07 |
| Unreal Engine 5.6.1 | `D:\Epic Games\UE_5.6`; first-party MCP :8000/mcp; VibeUE staged at `~\ue-plugins\VibeUE` | ✅ 2026-07-19 |
| NVIDIA ACE | Audio2Face-3D lip-sync + Claire/James/Mark models, staged `~\nvidia-blueprints\` | ✅ 2026-07-19 |
| Image-to-3D | Tripo API / Hunyuan3D-2.1 / TRELLIS.2 (both fit on 5090) | per pipeline skill |
| ffmpeg 8.1.2 / ImageMagick 7.1.2 / rembg[gpu] | CLI — assembly, grading, background removal | ✅ 2026-07-02 |

## Design skills (native Skill tool)
frontend-design · impeccable · theme-factory · dataviz · algorithmic-art ·
game-content-pipeline · higgsfield-generate / -product-photoshoot / -marketplace-cards /
-soul-id · web-artifacts-builder · magic MCP (21st.dev components)

## Local AI (free)
Ollama :11434 — gemma3 (instant), qwen3.6:27b, nemotron-cascade-2:30b, llama4:scout,
**llava:7b (vision — powers judge_image.py)**, bge-m3 (embeddings)

## Automation
playwright-cli + claude-in-chrome (screenshots of built sites for judging) ·
Win32/SelfConnect desktop control · gh CLI

## Known constraints
- sm_120 (Blackwell): CUDA Python deps need cu128 builds or "no kernel image"
- BRIA RMBG-2.0 is non-commercial — use birefnet-general for shippable work
- AI music (Suno/Udio) not ship-safe until Sony suit resolves
- UE 5.8 not yet installed (5.6.1 is); ~120GB if/when — see skill setup-checklist
