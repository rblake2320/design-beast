# Setup — rebuild the whole beast from zero

Ordered so each step is verifiable before the next. After ANY step, `beast doctor`
(= `python scripts/doctor.py`) tells you exactly what's live and what's missing —
it is the source of truth, not this file. Optional lanes can be skipped; the stack
degrades cleanly (doctor shows them as `warn`, never `FAIL`).

Target shape: Windows 11, NVIDIA GPU (Blackwell needs cu128+ torch everywhere),
Python 3.12, ~200 GB free for models.

## 0. Core tools (required)

```powershell
winget install Git.Git Python.Python.3.12 OpenJS.NodeJS.LTS Gyan.FFmpeg
pip install yt-dlp
# add ffmpeg's winget bin dir to PATH (doctor prints the expected location)
git clone https://github.com/rblake2320/design-beast.git; cd design-beast
python scripts/doctor.py        # baseline: expect many warns, no core FAILs
```

## 1. Beast Studio (required)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest studio/tests -q    # offline suites must pass
.\.venv\Scripts\python.exe studio\server.py             # → http://localhost:8787
```

## 2. Local image/video lane — ComfyUI (recommended)

```powershell
git clone https://github.com/comfyanonymous/ComfyUI D:\ai\comfyui
cd D:\ai\comfyui; python -m venv venv
.\venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128   # BEFORE requirements — Blackwell rule
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Models (into `models/<subdir>/` — doctor names any missing file):
| File | Subdir | Source |
|---|---|---|
| flux1-schnell-fp8.safetensors | checkpoints | HF: Comfy-Org/flux1-schnell |
| ltx-2.3-22b-dev-nvfp4.safetensors | checkpoints | HF: Lightricks LTX-2.3 |
| gemma_3_12B_it_fp4_mixed.safetensors | text_encoders | LTX text encoder |
| wan2.2_ti2v_5B_fp16.safetensors | diffusion_models | HF: Wan-AI Wan2.2 |
| wan2.2_vae.safetensors | vae | Wan2.2 VAE |
| umt5_xxl_fp8_e4m3fn_scaled.safetensors | text_encoders | Wan text encoder |

Studio auto-starts ComfyUI on :8188 on demand. After first render:
`beast replay --save-baseline` to pin the environment, then `beast ledger` any time.

## 3. Judge lane — Ollama (recommended; the quality loop needs eyes)

```powershell
winget install Ollama.Ollama
ollama pull qwen3-vl:8b      # judge_model in studio/config.py
```

## 4. Audio lane (optional)

```powershell
# Chatterbox voice cloning — own venv; torch pin override is DELIBERATE (no Blackwell build at 2.6)
mkdir D:\AI\tts; cd D:\AI\tts; python -m venv chatterbox-venv
.\chatterbox-venv\Scripts\python.exe -m pip install chatterbox-tts soundfile
.\chatterbox-venv\Scripts\python.exe -m pip install --force-reinstall torch torchaudio --index-url https://download.pytorch.org/whl/cu128
# save output via soundfile, not torchaudio (torchaudio 2.11 wants torchcodec)

# ACE-Step music (Apache 2.0, ship-safe BGM)
cd D:\AI; git clone https://github.com/ace-step/ACE-Step-1.5.git; cd ACE-Step-1.5
$env:UV_HTTP_TIMEOUT=600; uv sync; uv run acestep   # models auto-download first run

# Kokoro fixed-voice TTS: drop kokoro-v1.0.onnx + voices-v1.0.bin in D:\ai\tools\kokoro
```

## 5. Vision/QA lane (optional)

```powershell
mkdir D:\content\yolo-vision; cd D:\content\yolo-vision; python -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe -m pip install ultralytics jupyterlab
# YOLO-Face: gh release download -R akanametov/yolo-face -p yolov11n-face.pt -D models
# SAM 2.1 auto-downloads; SAM 3 requires Meta access (HF facebook/sam3)
```

## 6. Motion graphics — HyperFrames (optional)

```powershell
npx hyperframes skills update       # installs the agent skill set (core)
```

## 7. Game lane (optional)

Blender 5.x (MCP bridge inside Blender, :9876) · UE 5.8 + BeastLab project hosts the
first-party MCP on :8000/mcp · UE 5.6 for `/api/to_ue`. Paths live in
`studio/config.py` (override with `BEAST_*` env vars). VibeUE staged per repos.yml.

## 8. Cloud parity (optional — BYOK)

Set the env keys named in `studio/model_registry.json` (`key_env` fields) or log in
provider CLIs (`higgsfield auth login`). `GET /api/registry` then shows those
backends as available — same pipeline, the provider's terms.

## Verify everything

```powershell
python scripts/doctor.py     # exit code == number of hard failures
```
