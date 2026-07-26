#!/usr/bin/env python3
"""Beast Studio — local web UI for the design-beast quality loop.

Run:  python studio/server.py   →  http://localhost:8787
Create: brief → expand → N candidates → judge → graded winner.
Plus: upload/drop any image → judge (free) / refine (ref edit) / animate (i2v).
"""
import base64
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
RUNS = ROOT / "runs"
UPLOADS = ROOT / "uploads"
RUNS.mkdir(exist_ok=True)
UPLOADS.mkdir(exist_ok=True)
sys.path.insert(0, str(REPO / "scripts"))
from judge_image import judge  # noqa: E402

OLLAMA = "http://localhost:11434/api/generate"
TRELLIS_LOCAL = "http://localhost:8017/v1/infer"   # docker -p 8017:8000
FLUX_LOCAL = "http://localhost:8018/v1/infer"      # docker -p 8018:8000
BACKENDS = {"nim-trellis": 8017, "nim-flux": 8018, "nim-kontext": 8019}
KONTEXT_LOCAL = "http://localhost:8019/v1/infer"
ESRGAN = Path(r"D:\ai\tools\realesrgan\realesrgan-ncnn-vulkan.exe")
KOKORO_DIR = Path(r"D:\ai\tools\kokoro")
_kokoro = None
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe")
UE_CMD = Path(r"D:\Epic Games\UE_5.6\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
UE_PROJECT = Path(r"C:\Users\techai\route-rush-unreal\RouteRush.uproject")
BRIDGE = ROOT / "bridge"
NIM_SIZES = {"1:1": (1024, 1024), "16:9": (1344, 768), "9:16": (768, 1344),
             "4:3": (1152, 896), "3:4": (896, 1152)}


def _nim_key() -> str:
    for line in (Path.home() / ".nvidia.env").read_text().splitlines():
        if line.startswith("NVIDIA_API_KEY="):
            return line.split("=", 1)[1].strip()
    return ""
app = FastAPI(title="Beast Studio")
app.mount("/runs", StaticFiles(directory=RUNS), name="runs")
app.mount("/uploads", StaticFiles(directory=UPLOADS), name="uploads")
LOCK = threading.Lock()


def friendly(err: str) -> str:
    if "grace_daily_limit_reached" in err or "unlock_full_access" in err:
        return ("Higgsfield account notice: daily limit / 'unlock full access'. "
                "Open higgsfield.ai, clear the notice on your plan, then retry. "
                "Credits alone don't bypass this.")
    if "Session expired" in err or "Not authenticated" in err:
        return "Higgsfield login expired — run `higgsfield auth login` in a terminal."
    return err[-300:] if err else "unknown error (empty CLI output)"


def hf_generate(model: str, prompt: str, out_file: Path, extra: list = None) -> dict:
    """Run one Higgsfield job, download result. Returns {url,file} or {error}."""
    cmd = [shutil.which("higgsfield") or "higgsfield", "generate", "create", model,
           "--prompt", prompt, "--wait", "--wait-timeout", "15m", "--json"] + (extra or [])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1000)
    urls = re.findall(r'https://[^"\s]+\.(?:png|jpe?g|webp|mp4)[^"\s]*', proc.stdout)
    if not urls:
        return {"error": friendly(proc.stderr or proc.stdout)}
    urllib.request.urlretrieve(urls[0], out_file)
    return {"url": urls[0], "file": out_file.name}


def _nim_invoke(url: str, payload: dict, headers: dict, timeout: int = 600) -> dict:
    """POST to a NIM endpoint; follow the NVCF 202-polling pattern if used."""
    r = requests.post(url, headers=headers, json=payload, timeout=(15, timeout))
    while r.status_code == 202:
        rid = r.headers.get("NVCF-REQID")
        time.sleep(3)
        r = requests.get(f"https://api.nvcf.nvidia.com/v2/nvcf/pexec/status/{rid}",
                         headers=headers, timeout=(15, 120))
    r.raise_for_status()
    return r.json()


def nim_flux(slug: str, prompt: str, out_file: Path, ar: str) -> dict:
    """Generate via hosted NVIDIA NIM (free with API key). slug: flux.1-schnell|flux.1-dev"""
    w, h = NIM_SIZES.get(ar, (1024, 1024))
    payload = {"prompt": prompt, "width": w, "height": h,
               "steps": 4 if "schnell" in slug else 40, "seed": int(time.time()) % 100000}
    if "dev" in slug:
        payload["cfg_scale"] = 3.5
    try:
        out = _nim_invoke(f"https://ai.api.nvidia.com/v1/genai/black-forest-labs/{slug}",
                          payload, {"Authorization": f"Bearer {_nim_key()}",
                                    "Accept": "application/json"})
        arts = out.get("artifacts") or []
        if not arts:
            return {"error": f"NIM returned no image: {str(out)[:200]}"}
        out_file.write_bytes(base64.b64decode(arts[0]["base64"]))
        return {"file": out_file.name, "url": ""}
    except requests.Timeout:
        return {"error": "NVIDIA hosted NIM timed out (trial queue is busy) — "
                         "try again, or use the local RTX NIM when it's running."}
    except Exception as e:  # noqa: BLE001 — surface API failure in UI
        return {"error": f"NIM error: {str(e)[:250]}"}


def flux_local(prompt: str, out_file: Path, ar: str) -> dict:
    """FLUX schnell on the local RTX NIM — free, unlimited, no cloud."""
    w, h = NIM_SIZES.get(ar, (1024, 1024))
    try:
        out = _nim_invoke(FLUX_LOCAL, {"prompt": prompt, "width": w, "height": h,
                                       "steps": 4, "seed": int(time.time()) % 100000},
                          {"Accept": "application/json"}, timeout=600)
    except Exception as e:  # noqa: BLE001 — container down or busy
        return {"error": "Local FLUX NIM not answering on :8018 — start it from the "
                         f"Backends panel and wait for warmup. ({str(e)[:120]})"}
    arts = out.get("artifacts") or []
    if not arts:
        return {"error": f"local FLUX returned no image: {str(out)[:200]}"}
    out_file.write_bytes(base64.b64decode(arts[0]["base64"]))
    return {"file": out_file.name, "url": ""}


def kontext_local(image_path: Path, instruction: str, out_file: Path) -> dict:
    """Prompt-based image EDIT via local FLUX.1 Kontext NIM."""
    img_b64 = base64.b64encode(image_path.read_bytes()).decode()
    try:
        out = _nim_invoke(KONTEXT_LOCAL,
                          {"prompt": instruction,
                           "image": f"data:image/png;base64,{img_b64}",
                           "seed": int(time.time()) % 100000},
                          {"Accept": "application/json"}, timeout=600)
    except Exception as e:  # noqa: BLE001 — container down
        return {"error": f"local Kontext not answering on :8019 ({str(e)[:120]})"}
    arts = out.get("artifacts") or []
    if not arts:
        return {"error": f"Kontext returned no image: {str(out)[:200]}"}
    out_file.write_bytes(base64.b64decode(arts[0]["base64"]))
    return {"file": out_file.name}


def upscale(src: Path, dst: Path) -> bool:
    """2x Real-ESRGAN if installed; returns False (skipped) when absent."""
    if not ESRGAN.exists():
        return False
    r = subprocess.run([str(ESRGAN), "-i", str(src), "-o", str(dst),
                        "-s", "2", "-n", "realesrgan-x4plus"],
                       capture_output=True, timeout=300)
    return r.returncode == 0 and dst.exists()


def trellis_3d(image_path: Path, out_glb: Path) -> dict:
    """Image → 3D GLB. Local RTX NIM first (:8017), hosted NIM fallback."""
    img_b64 = base64.b64encode(image_path.read_bytes()).decode()
    payload = {"image": f"data:image/png;base64,{img_b64}", "slat_cfg_scale": 3,
               "ss_cfg_scale": 7.5, "slat_sampling_steps": 25,
               "ss_sampling_steps": 25, "seed": 1}
    try:
        out = _nim_invoke(TRELLIS_LOCAL, payload, {"Accept": "application/json"},
                          timeout=900)
        src = "local RTX NIM"
    except Exception:  # noqa: BLE001 — local NIM not running, try hosted
        try:
            out = _nim_invoke("https://ai.api.nvidia.com/v1/genai/microsoft/trellis",
                              payload, {"Authorization": f"Bearer {_nim_key()}",
                                        "Accept": "application/json"})
            src = "hosted NIM"
        except Exception as e:  # noqa: BLE001
            return {"error": "TRELLIS unavailable: local NIM not running on :8017 and "
                             f"hosted NIM failed ({str(e)[:150]})"}
    arts = out.get("artifacts") or []
    if not arts:
        return {"error": f"TRELLIS returned no mesh: {str(out)[:200]}"}
    out_glb.write_bytes(base64.b64decode(arts[0]["base64"]))
    return {"file": out_glb.name, "source": src}


def safe_judge(img: Path, brief: str) -> dict:
    try:
        return judge(str(img), brief, "qwen3-vl:8b")
    except Exception:  # noqa: BLE001 — one retry covers vision-model cold load
        return judge(str(img), brief, "qwen3-vl:8b")


def grade(src: Path, dst: Path):
    subprocess.run([shutil.which("magick") or "magick", str(src),
                    "-modulate", "100,93", "-level", "1%,99.5%", str(dst)],
                   capture_output=True, timeout=120)


def ollama_json(model: str, prompt: str, timeout: int = 240) -> dict:
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "format": "json", "think": False}).encode()
    req = urllib.request.Request(OLLAMA, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read())
    return json.loads(out["response"] or out.get("thinking", ""))


def _status(run_dir: Path, **updates):
    with LOCK:
        f = run_dir / "status.json"
        s = json.loads(f.read_text()) if f.exists() else {}
        s.update(updates)
        f.write_text(json.dumps(s, indent=1))


def _new_run(brief: str, model: str, kind: str) -> Path:
    run_dir = RUNS / time.strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir()
    _status(run_dir, id=run_dir.name, brief=brief, model=model, kind=kind,
            phase="queued")
    return run_dir


# ---------- create loop ----------

class RunReq(BaseModel):
    brief: str
    prompt: str = ""            # expanded prompt; falls back to brief
    variations: list[str] = []
    model: str = "gpt_image_2"
    aspect_ratio: str = "1:1"
    reference: str = ""         # filename in uploads/


def _generate_one(run_dir: Path, i: int, prompt: str, req: RunReq) -> dict:
    cand = {"i": i, "prompt": prompt, "state": "generating"}
    if req.model.startswith("local:"):
        r = flux_local(prompt, run_dir / f"cand{i}.png", req.aspect_ratio)
    elif req.model.startswith("nim:"):
        r = nim_flux(req.model[4:], prompt, run_dir / f"cand{i}.png", req.aspect_ratio)
    else:
        extra = ["--aspect_ratio", req.aspect_ratio]
        if req.model == "gpt_image_2":
            extra += ["--resolution", "2k"]
        if req.reference:
            extra += ["--image", str(UPLOADS / req.reference)]
        r = hf_generate(req.model, prompt, run_dir / f"cand{i}.png", extra)
    if "error" in r:
        cand.update(state="failed", error=r["error"])
        return cand
    cand.update(state="judging", **r)
    v = safe_judge(run_dir / r["file"], json.loads((run_dir / "status.json").read_text())["brief"])
    cand.update(state="done", score=v.get("score", 0), kill=v.get("kill", False),
                fix=v.get("fix", ""))
    return cand


def _run_loop(run_dir: Path, req: RunReq):
    base = req.prompt.strip() or req.brief
    n = max(len(req.variations), 1) if req.variations else 4
    prompts = [f"{base}; {v}" if v else base for v in (req.variations or [""] * n)]
    _status(run_dir, phase="generating", candidates=[])
    with ThreadPoolExecutor(max_workers=4) as pool:
        cands = list(pool.map(lambda t: _generate_one(run_dir, t[0], t[1], req),
                              enumerate(prompts, 1)))
    done = [c for c in cands if c["state"] == "done" and not c.get("kill")]
    if not done:
        _status(run_dir, phase="failed", candidates=cands,
                error=next((c.get("error") for c in cands if c.get("error")), None))
        return
    winner = max(done, key=lambda c: c["score"])
    _status(run_dir, phase="grading", candidates=cands, winner=winner["i"])
    src = run_dir / winner["file"]
    up = run_dir / "upscaled.png"
    if upscale(src, up):
        src = up
    final = run_dir / "final.png"
    grade(src, final)
    _status(run_dir, phase="done", upscaled=up.exists(),
            final=final.name if final.exists() else winner["file"])


# ---------- endpoints ----------

@app.get("/")
def index():
    return FileResponse(ROOT / "index.html")


@app.get("/api/recipes")
def recipes():
    return [{"name": f.stem,
             "title": f.read_text(encoding="utf-8").splitlines()[0].lstrip("# ")}
            for f in sorted((REPO / "design-system" / "recipes").glob("*.md"))]


class UploadReq(BaseModel):
    name: str
    data: str  # dataURL or raw base64


@app.post("/api/upload")
def upload(req: UploadReq):
    raw = base64.b64decode(req.data.split(",")[-1])
    safe = re.sub(r"[^\w.\-]", "_", req.name) or "upload.png"
    fname = f"{time.strftime('%H%M%S')}_{safe}"
    (UPLOADS / fname).write_bytes(raw)
    return {"file": fname}


class ExpandReq(BaseModel):
    brief: str
    recipe: str = "cinematic-scene"


@app.post("/api/expand")
def expand(req: ExpandReq):
    card = (REPO / "design-system" / "recipes" / f"{req.recipe}.md")
    card_txt = card.read_text(encoding="utf-8")[:2000] if card.exists() else ""
    p = f"""You are a prompt architect for AI image generation. The user brief is vague;
expand it using this recipe card's prompt anatomy:

{card_txt}

User brief: {req.brief}

Reply ONLY JSON: {{"prompt": "<one structured prompt: subject with 2-3 concrete details,
composition/lens, lighting with direction, mood/grade palette, style anchor, negatives —
under 90 words>", "axis": "<the ONE axis the variations change>",
"variations": ["<v1>","<v2>","<v3>","<v4>"]}}"""
    for model in ("qwen3.6:27b", "gemma3:latest"):
        try:
            out = ollama_json(model, p)
            if out.get("prompt"):
                out["model_used"] = model
                return out
        except Exception:  # noqa: BLE001 — fall through to smaller model
            continue
    return JSONResponse({"error": "local LLM unavailable (is Ollama up?)"}, 503)


class JudgeReq(BaseModel):
    file: str            # uploads/ filename or runs/<id>/<file>
    brief: str


def _resolve(f: str) -> Path:
    p = (ROOT / f) if "/" in f else (UPLOADS / f)
    return p if p.resolve().is_relative_to(ROOT) else None


@app.post("/api/judge")
def judge_only(req: JudgeReq):
    p = _resolve(req.file)
    if not p or not p.exists():
        return JSONResponse({"error": "file not found"}, 404)
    return safe_judge(p, req.brief)


class RefineReq(BaseModel):
    file: str
    instruction: str
    brief: str = ""


@app.post("/api/refine")
def refine(req: RefineReq):
    src = _resolve(req.file)
    if not src or not src.exists():
        return JSONResponse({"error": "file not found"}, 404)
    run_dir = _new_run(req.instruction, "nano_banana_2", "refine")

    def work():
        _status(run_dir, phase="generating", candidates=[])
        # local Kontext first (free); Higgsfield nano banana as fallback
        r = kontext_local(src, req.instruction, run_dir / "cand1.png")
        if "error" in r:
            r = hf_generate("nano_banana_2", req.instruction, run_dir / "cand1.png",
                            ["--image", str(src)])
        if "error" in r:
            _status(run_dir, phase="failed", error=r["error"], candidates=[])
            return
        v = safe_judge(run_dir / "cand1.png", req.brief or req.instruction)
        cand = {"i": 1, "state": "done", "file": "cand1.png",
                "score": v.get("score", 0), "fix": v.get("fix", "")}
        final = run_dir / "final.png"
        grade(run_dir / "cand1.png", final)
        _status(run_dir, phase="done", candidates=[cand], winner=1,
                final=final.name if final.exists() else "cand1.png")

    threading.Thread(target=work, daemon=True).start()
    return {"id": run_dir.name}


class AnimateReq(BaseModel):
    file: str
    motion: str = "slow cinematic dolly-in, subtle ambient movement"
    duration: int = 5


def wan_animate(src: Path, motion: str, out_mp4: Path) -> dict:
    """Image → video via Wan 2.2 5B on local ComfyUI. ~3 min for a 2s clip."""
    C = f"http://localhost:{COMFY_PORT}"
    try:
        with open(src, "rb") as f:
            up = requests.post(f"{C}/upload/image",
                               files={"image": (src.name, f, "image/png")},
                               timeout=60).json()
        g = {
            "1": {"class_type": "UNETLoader", "inputs": {
                "unet_name": "wan2.2_ti2v_5B_fp16.safetensors", "weight_dtype": "default"}},
            "2": {"class_type": "CLIPLoader", "inputs": {
                "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan",
                "device": "default"}},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
            "4": {"class_type": "CLIPTextEncode", "inputs": {"text": motion, "clip": ["2", 0]}},
            "5": {"class_type": "CLIPTextEncode", "inputs": {
                "text": "static image, frozen, blurry, distorted, text, watermark",
                "clip": ["2", 0]}},
            "6": {"class_type": "LoadImage", "inputs": {"image": up["name"]}},
            "7": {"class_type": "Wan22ImageToVideoLatent", "inputs": {
                "vae": ["3", 0], "width": 768, "height": 768, "length": 49,
                "batch_size": 1, "start_image": ["6", 0]}},
            "8": {"class_type": "KSampler", "inputs": {
                "model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
                "latent_image": ["7", 0], "seed": int(time.time()) % 100000,
                "steps": 20, "cfg": 5.0, "sampler_name": "uni_pc",
                "scheduler": "simple", "denoise": 1.0}},
            "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
            "10": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": 24.0}},
            "11": {"class_type": "SaveVideo", "inputs": {
                "video": ["10", 0], "filename_prefix": "beast/clip",
                "format": "mp4", "codec": "h264"}},
        }
        pid = requests.post(f"{C}/prompt", json={"prompt": g, "client_id": "beast"},
                            timeout=30).json()["prompt_id"]
        t0 = time.time()
        while time.time() - t0 < 2400:
            time.sleep(10)
            h = requests.get(f"{C}/history/{pid}", timeout=30).json()
            if pid in h and h[pid]["status"].get("completed"):
                img = h[pid]["outputs"]["11"]["images"][0]
                produced = (COMFY_DIR / "output" / img["subfolder"] / img["filename"])
                shutil.copy2(produced, out_mp4)
                return {"file": out_mp4.name}
            if pid in h and h[pid]["status"].get("status_str") == "error":
                return {"error": "ComfyUI job errored — check comfyui log"}
        return {"error": "local video generation timed out (40 min)"}
    except Exception as e:  # noqa: BLE001 — ComfyUI down or API change
        return {"error": f"local video failed: {str(e)[:200]}"}


@app.post("/api/animate")
def animate(req: AnimateReq):
    src = _resolve(req.file)
    if not src or not src.exists():
        return JSONResponse({"error": "file not found"}, 404)
    run_dir = _new_run(req.motion, "wan2.2-local", "animate")

    def work():
        _status(run_dir, phase="generating", candidates=[])
        # local Wan 2.2 first (free, ~3 min); Seedance cloud fallback
        r = wan_animate(src, req.motion, run_dir / "clip.mp4")
        if "error" in r:
            r = hf_generate("seedance_2_0", req.motion, run_dir / "clip.mp4",
                            ["--start-image", str(src), "--duration", str(req.duration)])
        if "error" in r:
            _status(run_dir, phase="failed", error=r["error"], candidates=[])
            return
        _status(run_dir, phase="done", candidates=[
            {"i": 1, "state": "done", "file": "clip.mp4", "video": True}],
            final="clip.mp4", video=True)

    threading.Thread(target=work, daemon=True).start()
    return {"id": run_dir.name}


COMFY_DIR = Path(r"D:\ai\comfyui")
COMFY_PORT = 8188


def _port_pid(port: int):
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                         timeout=30).stdout
    for line in out.splitlines():
        if f":{port}" in line and "LISTENING" in line:
            return int(line.split()[-1])
    return None


@app.get("/api/backends")
def backends():
    ps = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}}\t{{.State}}"],
                        capture_output=True, text=True, timeout=30).stdout
    states = dict(line.split("\t") for line in ps.splitlines() if "\t" in line)
    out = []
    for name, port in BACKENDS.items():
        state = states.get(name, "not created")
        ready = False
        if state == "running":
            try:
                ready = requests.get(f"http://localhost:{port}/v1/health/ready",
                                     timeout=2).ok
            except Exception:  # noqa: BLE001 — warming up
                ready = False
        out.append({"name": name, "state": state, "ready": ready, "port": port})
    pid = _port_pid(COMFY_PORT)
    ready = False
    if pid:
        try:
            ready = requests.get(f"http://localhost:{COMFY_PORT}/system_stats",
                                 timeout=2).ok
        except Exception:  # noqa: BLE001
            ready = False
    out.append({"name": "comfyui", "state": "running" if pid else "exited",
                "ready": ready, "port": COMFY_PORT})
    return out


class BackendReq(BaseModel):
    name: str
    action: str  # start | stop


@app.post("/api/backend")
def backend(req: BackendReq):
    if req.action not in ("start", "stop"):
        return JSONResponse({"error": "unknown action"}, 400)
    if req.name == "comfyui":
        pid = _port_pid(COMFY_PORT)
        if req.action == "start" and not pid:
            subprocess.Popen([str(COMFY_DIR / "venv/Scripts/python.exe"), "main.py",
                              "--port", str(COMFY_PORT)], cwd=COMFY_DIR,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=0x00000008)  # DETACHED_PROCESS
        elif req.action == "stop" and pid:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True,
                           timeout=30)
        return {"ok": True, "note": "loads models on demand" if req.action == "start" else ""}
    if req.name not in BACKENDS:
        return JSONResponse({"error": "unknown backend"}, 400)
    r = subprocess.run(["docker", req.action, req.name],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return JSONResponse({"error": r.stderr[-200:] or "docker failed"}, 500)
    return {"ok": True, "note": "warmup takes ~5 min after start" if req.action == "start" else ""}


class To3DReq(BaseModel):
    file: str


@app.post("/api/to3d")
def to_3d(req: To3DReq):
    src = _resolve(req.file)
    if not src or not src.exists():
        return JSONResponse({"error": "file not found"}, 404)
    run_dir = _new_run("image → 3D (TRELLIS)", "trellis", "3d")

    def work():
        _status(run_dir, phase="generating", candidates=[])
        r = trellis_3d(src, run_dir / "model.glb")
        if "error" in r:
            _status(run_dir, phase="failed", error=r["error"], candidates=[])
            return
        _status(run_dir, phase="done", candidates=[
            {"i": 1, "state": "done", "file": "model.glb", "glb": True,
             "fix": f"via {r['source']} — import with Blender pipeline skill"}],
            final="model.glb", glb=True)

    threading.Thread(target=work, daemon=True).start()
    return {"id": run_dir.name}


class TtsReq(BaseModel):
    text: str
    voice: str = "af_heart"


@app.post("/api/tts")
def tts(req: TtsReq):
    global _kokoro
    model = KOKORO_DIR / "kokoro-v1.0.onnx"
    voices = KOKORO_DIR / "voices-v1.0.bin"
    if not model.exists() or not voices.exists():
        return JSONResponse({"error": "Kokoro model files still downloading — retry shortly"}, 503)
    try:
        if _kokoro is None:
            from kokoro_onnx import Kokoro
            _kokoro = Kokoro(str(model), str(voices))
        import soundfile as sf
        samples, sr = _kokoro.create(req.text, voice=req.voice, speed=1.0)
        fname = f"tts_{time.strftime('%H%M%S')}.wav"
        (UPLOADS / fname).parent.mkdir(exist_ok=True)
        sf.write(str(UPLOADS / fname), samples, sr)
        return {"file": fname, "url": f"/uploads/{fname}"}
    except Exception as e:  # noqa: BLE001 — surface TTS failure in UI
        return JSONResponse({"error": f"TTS failed: {str(e)[:200]}"}, 500)


class ToUEReq(BaseModel):
    file: str  # runs/<id>/model.glb


@app.post("/api/to_ue")
def to_ue(req: ToUEReq):
    src = _resolve(req.file)
    if not src or not src.exists():
        return JSONResponse({"error": "glb not found"}, 404)
    if not UE_CMD.exists():
        return JSONResponse({"error": "Unreal Engine not found at expected path"}, 500)
    run_dir = _new_run(f"UE import: {src.name}", "ue-bridge", "unreal")

    def work():
        _status(run_dir, phase="generating", candidates=[
            {"i": 1, "state": "blender: glb → fbx"}])
        fbx = run_dir / "asset.fbx"
        b = subprocess.run([str(BLENDER), "-b", "-P", str(BRIDGE / "glb_to_fbx.py"),
                            "--", str(src), str(fbx)],
                           capture_output=True, text=True, timeout=300)
        if not fbx.exists():
            _status(run_dir, phase="failed", error=f"blender convert failed: {b.stderr[-200:]}")
            return
        _status(run_dir, phase="generating", candidates=[
            {"i": 1, "state": "unreal: importing (first run can take minutes)"}])
        u = subprocess.run([str(UE_CMD), str(UE_PROJECT), "-run=pythonscript",
                            f"-script={BRIDGE / 'ue_import.py'} {fbx} /Game/BeastAssets",
                            "-stdout", "-unattended", "-nopause", "-nosplash"],
                           capture_output=True, text=True, timeout=1800)
        m = re.search(r"BEAST_IMPORTED: \[(.*?)\]", u.stdout)
        if not m or not m.group(1).strip():
            _status(run_dir, phase="failed",
                    error=f"UE import produced no asset: {(u.stdout or u.stderr)[-250:]}")
            return
        asset = m.group(1).strip().strip("'\"")
        _status(run_dir, phase="done", candidates=[
            {"i": 1, "state": "done", "fix": f"in RouteRush at {asset}"}],
            ue_asset=asset)

    threading.Thread(target=work, daemon=True).start()
    return {"id": run_dir.name}


@app.post("/api/run")
def start_run(req: RunReq):
    run_dir = _new_run(req.brief, req.model, "create")
    threading.Thread(target=_run_loop, args=(run_dir, req), daemon=True).start()
    return {"id": run_dir.name}


@app.get("/api/run/{run_id}")
def run_status(run_id: str):
    f = RUNS / run_id / "status.json"
    if not f.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return json.loads(f.read_text())


@app.get("/api/runs")
def list_runs():
    out = []
    for d in sorted(RUNS.iterdir(), reverse=True):
        f = d / "status.json"
        if f.exists():
            s = json.loads(f.read_text())
            out.append({"id": s.get("id", d.name), "brief": s.get("brief", "")[:70],
                        "phase": s.get("phase"), "kind": s.get("kind", "create")})
    return out[:30]


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8787)
