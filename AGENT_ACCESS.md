# Beast Studio — Agent Access Card

Paste this whole file into any AI agent running on this machine. It is the complete
contract for using the Studio. Base URL: `http://127.0.0.1:8787` (local only).

## What this is
A local AI production pipeline on the RTX 5090. Everything runs on-box and free:
image generation (FLUX schnell / FLUX.2 klein), prompt-based image editing (FLUX
Kontext), vision judging (qwen3-vl), auto-upscale (Real-ESRGAN, validated), video
(Wan 2.2 fast · LTX-2.3 cinema WITH generated audio), image→3D (TRELLIS), TTS
(Kokoro), and a bridge into Unreal Engine (RouteRush project).

## Endpoints

| Method | Path | Body | Purpose |
|---|---|---|---|
| GET | `/api/recipes` | — | List prompt recipe cards |
| POST | `/api/expand` | `{brief, recipe}` | Vague idea → structured prompt + 4 variations (local LLM, free) |
| POST | `/api/upload` | `{name, data}` (data = dataURL or base64) | Upload an image; returns `{file}` |
| POST | `/api/judge` | `{file, brief}` | Score any image 1-10 + kill flag + fix note (free) |
| POST | `/api/run` | `{brief, prompt, variations[], model, aspect_ratio, reference}` | Full loop: N candidates → judge → upscale → grade |
| POST | `/api/refine` | `{file, instruction, brief}` | Prompt-based edit, identity-preserving (Kontext) |
| POST | `/api/animate` | `{file, motion, duration(3\|5), quality("fast"\|"cinema")}` | Image → video. cinema = LTX-2.3 with generated audio, ~25 min |
| POST | `/api/to3d` | `{file}` | Image → textured GLB mesh (TRELLIS, auto-starts) |
| POST | `/api/to_ue` | `{file: "runs/<id>/model.glb"}` | GLB → StaticMesh inside the RouteRush UE project |
| POST | `/api/tts` | `{text, voice?}` | Kokoro speech; returns wav URL |
| GET | `/api/run/{id}` | — | Poll a run. Terminal phases: `done` \| `failed` |
| GET | `/api/runs` | — | Recent runs |
| GET | `/api/backends` | — | GPU services + ready state |
| POST | `/api/backend` | `{name, action:"start"\|"stop"}` | Toggle a GPU backend |

## Models for /api/run
- `local:flux.1-schnell` — default, free, ~7s/image
- `local:flux.2-klein` — newest FLUX, free
- `gpt_image_2`, `nano_banana_2`, `z_image` — Higgsfield (needs account credits)

`file` fields accept an uploads filename (from /api/upload) or `runs/<id>/<file>`.

## Rules (do not skip)
1. **Poll, don't assume.** POST returns `{id}` immediately; poll `/api/run/{id}` every
   5–10 s until phase is `done` or `failed`. `failed` always carries an `error` string —
   read it, it's specific.
2. **Never one-shot for deliverables.** Use `/api/expand` first, pass 4 one-axis
   variations to `/api/run`, let the judge pick. That's the whole point of this system.
3. **VRAM etiquette.** Backends auto-start when needed, but don't launch a `cinema`
   render while also generating images — the 22B model needs most of the card. Check
   `/api/backends`; stop things you started if the human is gaming.
4. **Judge verdicts are law.** kill=true or score ≤3 means the image is bad or was
   censored (NVIDIA safety filter returns black frames on dark/occult content — the
   error message will say so). Don't retry the identical input expecting different luck.
5. **Outputs live in** `C:\Users\techai\design-beast\studio\runs\<id>\` —
   `final.png` (2048², judged+upscaled+graded), `clip.mp4`, `model.glb`.
6. **First call to a cold backend takes minutes** (model load). The run card streams
   warmup status; be patient before declaring failure.

## Smoke test (run this first)
```bash
curl -s http://127.0.0.1:8787/api/recipes | head -c 200   # expect JSON recipe list
```
If connection refused: `cd C:\Users\techai\design-beast && python studio/server.py`
