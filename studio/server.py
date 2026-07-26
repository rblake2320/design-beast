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

from typing import Literal

import requests
import uvicorn
from fastapi import FastAPI, Header
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import jobs
from jobs import (E_BACKEND_DOWN, E_CANCELLED, E_CENSORED, E_ENGINE,
                  E_JUDGE_REJECTED, E_VALIDATION, JobCancelled)

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
BACKENDS = {"nim-trellis": 8017, "nim-flux": 8018, "nim-kontext": 8019, "nim-flux2": 8020}
LOCAL_IMAGE_MODELS = {"local:flux.1-schnell": ("nim-flux", 8018),
                      "local:flux.2-klein": ("nim-flux2", 8020)}
KONTEXT_LOCAL = "http://localhost:8019/v1/infer"
ESRGAN = Path(r"D:\ai\tools\realesrgan\realesrgan-ncnn-vulkan.exe")
KOKORO_DIR = Path(r"D:\ai\tools\kokoro")
_kokoro = None
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe")
UE_CMD = Path(r"D:\Epic Games\UE_5.6\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
UE_PROJECT = Path(r"C:\Users\techai\route-rush-unreal\RouteRush.uproject")
UE_CONTENT = Path(r"C:\Users\techai\route-rush-unreal\Content\BeastAssets")
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
jobs.init()  # durable job store; recovers orphans from a previous process


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


def flux_local(prompt: str, out_file: Path, ar: str, port: int = 8018) -> dict:
    """FLUX on a local RTX NIM — free, unlimited, no cloud."""
    w, h = NIM_SIZES.get(ar, (1024, 1024))
    try:
        import random
        out = _nim_invoke(f"http://localhost:{port}/v1/infer",
                          {"prompt": prompt, "width": w, "height": h,
                           "steps": 4, "seed": random.randrange(1, 2**31)},
                          {"Accept": "application/json"}, timeout=600)
    except Exception as e:  # noqa: BLE001 — container down or busy
        return {"error": f"Local NIM not answering on :{port} — start it from the "
                         f"Backends panel and wait for warmup. ({str(e)[:120]})"}
    arts = out.get("artifacts") or []
    raw = base64.b64decode(arts[0].get("base64", "")) if arts else b""
    if len(raw) < 1000:
        return {"error": f"local NIM returned empty/invalid image: {str(out)[:150]}"}
    out_file.write_bytes(raw)
    try:  # some NIMs emit JPEG — normalize to real PNG so judge/upscale never choke
        from PIL import Image
        img = Image.open(out_file)
        if img.format != "PNG":
            img.convert("RGB").save(out_file, "PNG")
    except Exception:  # noqa: BLE001
        return {"error": "local NIM output was not a decodable image"}
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


def _upscale_valid(src: Path, dst: Path) -> bool:
    """Detect tile-scramble corruption: downscaled result must resemble the source."""
    from PIL import Image, ImageChops, ImageStat
    a = Image.open(src).convert("RGB")
    b = Image.open(dst).convert("RGB").resize(a.size)
    rms = ImageStat.Stat(ImageChops.difference(a, b)).rms
    return sum(rms) / 3 < 20  # clean upscale ≈ 5-10; scrambled tiles ≈ 40+


def upscale(src: Path, dst: Path) -> bool:
    """2x upscale. Real-ESRGAN (serialized tiling) validated against source;
    falls back to Lanczos so a corrupt AI upscale can never ship as final."""
    if ESRGAN.exists():
        try:
            # -j 1:1:1 serializes load/proc/save threads — fixes tile-stitching races
            subprocess.run([str(ESRGAN), "-i", str(src), "-o", str(dst),
                            "-s", "2", "-n", "realesrgan-x4plus",
                            "-t", "1024", "-j", "1:1:1"],
                           capture_output=True, timeout=180)
            if dst.exists() and _upscale_valid(src, dst):
                return True
        except Exception:  # noqa: BLE001 — timeout/VRAM contention → Lanczos fallback
            pass
        dst.unlink(missing_ok=True)
    subprocess.run([shutil.which("magick") or "magick", str(src),
                    "-filter", "Lanczos", "-resize", "200%", str(dst)],
                   capture_output=True, timeout=120)
    return dst.exists()


def ensure_comfy(timeout_s: int = 120) -> bool:
    if _port_pid(COMFY_PORT):
        return True
    subprocess.Popen([str(COMFY_DIR / "venv/Scripts/python.exe"), "main.py",
                      "--port", str(COMFY_PORT)], cwd=COMFY_DIR,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=0x00000008)
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            if requests.get(f"http://localhost:{COMFY_PORT}/system_stats", timeout=2).ok:
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(3)
    return False


def comfy_flux_image(prompt: str, out_file: Path, ar: str) -> dict:
    """FLUX schnell via ComfyUI raw weights — NO NIM prompt filter. Free, local."""
    if not ensure_comfy():
        return {"error": "ComfyUI would not start on :8188"}
    C = f"http://localhost:{COMFY_PORT}"
    w, h = NIM_SIZES.get(ar, (1024, 1024))
    import random
    g = {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": "flux1-schnell-fp8.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["2", 0]}},
        "4": {"class_type": "EmptySD3LatentImage",
              "inputs": {"width": w, "height": h, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
            "latent_image": ["4", 0], "seed": random.randrange(1, 2**31),
            "steps": 4, "cfg": 1.0, "sampler_name": "euler",
            "scheduler": "simple", "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0],
                                                    "filename_prefix": "beast/raw"}},
    }
    try:
        pid = requests.post(f"{C}/prompt", json={"prompt": g, "client_id": "beast"},
                            timeout=30).json()["prompt_id"]
        t0 = time.time()
        while time.time() - t0 < 600:
            time.sleep(4)
            h_ = requests.get(f"{C}/history/{pid}", timeout=30).json()
            if pid in h_ and h_[pid]["status"].get("completed"):
                img = h_[pid]["outputs"]["7"]["images"][0]
                produced = COMFY_DIR / "output" / img["subfolder"] / img["filename"]
                from PIL import Image
                Image.open(produced).convert("RGB").save(out_file, "PNG")
                return {"file": out_file.name, "url": ""}
            if pid in h_ and h_[pid]["status"].get("status_str") == "error":
                return {"error": "ComfyUI flux job errored"}
        return {"error": "ComfyUI flux job timed out"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"comfy flux failed: {str(e)[:200]}"}


def trellis_3d(image_path: Path, out_glb: Path, allow_hosted: bool = False) -> dict:
    """Image → 3D GLB. Local RTX NIM (:8017). Hosted NIM only when explicitly
    allowed — it sends the image off-machine (privacy, not just cost)."""
    img_b64 = base64.b64encode(image_path.read_bytes()).decode()
    payload = {"image": f"data:image/png;base64,{img_b64}", "slat_cfg_scale": 3,
               "ss_cfg_scale": 7.5, "slat_sampling_steps": 25,
               "ss_sampling_steps": 25, "seed": 1}
    try:
        out = _nim_invoke(TRELLIS_LOCAL, payload, {"Accept": "application/json"},
                          timeout=900)
        src = "local RTX NIM"
    except Exception as local_err:  # noqa: BLE001 — local NIM failed
        if not allow_hosted:
            return {"error": "local TRELLIS failed and hosted fallback is disabled by "
                             "default (it would send your image off-machine). Pass "
                             f"allow_hosted_fallback:true to permit it. ({str(local_err)[:100]})"}
        try:
            out = _nim_invoke("https://ai.api.nvidia.com/v1/genai/microsoft/trellis",
                              payload, {"Authorization": f"Bearer {_nim_key()}",
                                        "Accept": "application/json"})
            src = "hosted NIM"
        except Exception as e:  # noqa: BLE001
            return {"error": "TRELLIS unavailable: local NIM failed and "
                             f"hosted NIM failed ({str(e)[:150]})"}
    arts = out.get("artifacts") or []
    if not arts:
        return {"error": f"TRELLIS returned no mesh: {str(out)[:200]}"}
    out_glb.write_bytes(base64.b64decode(arts[0]["base64"]))
    return {"file": out_glb.name, "source": src}


def dead_frame(p: Path) -> bool:
    """Near-uniform frame (black/white) — dead output, usually the NIM safety
    filter censoring a result by blanking it."""
    from PIL import Image, ImageStat
    try:
        return ImageStat.Stat(Image.open(p).convert("L")).stddev[0] < 3.0
    except Exception:  # noqa: BLE001
        return True


DEAD_FRAME_MSG = ("output was a blank frame — this is usually NVIDIA's built-in "
                  "content-safety filter censoring the result (dark/occult/violent "
                  "imagery trips it). Try a tamer source image or rephrase.")


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


def ensure_backend(name: str, run_dir: Path = None, wait_s: int = 480) -> bool:
    """Start a NIM container if needed and wait until ready. Surfaces progress."""
    port = BACKENDS.get(name)
    if not port:
        return False
    def ready():
        try:
            return requests.get(f"http://localhost:{port}/v1/health/ready", timeout=2).ok
        except Exception:  # noqa: BLE001
            return False
    if ready():
        return True
    subprocess.run(["docker", "start", name], capture_output=True, timeout=60)
    t0 = time.time()
    while time.time() - t0 < wait_s:
        if run_dir:
            _status(run_dir, phase="generating", candidates=[
                {"i": 1, "state": f"starting {name} — warmup ~{max(0, int((240 - (time.time()-t0))/60))+1} min"}])
        if ready():
            return True
        time.sleep(8)
    return False


def _status(run_dir: Path, **updates):
    with LOCK:
        f = run_dir / "status.json"
        s = json.loads(f.read_text()) if f.exists() else {}
        s.update(updates)
        f.write_text(json.dumps(s, indent=1))
    # mirror lifecycle into the durable job store
    phase = updates.get("phase")
    if phase:
        jid = run_dir.name
        if phase in ("generating", "grading"):
            if jobs.get(jid) and jobs.get(jid)["phase"] == "queued":
                jobs.set_phase(jid, "running")
        elif phase == "done":
            jobs.set_phase(jid, "done", result={k: v for k, v in s.items()
                                                if k in ("final", "winner", "ue_asset",
                                                         "video", "glb", "upscaled")})
        elif phase == "failed":
            code = s.get("error_code") or (
                E_CENSORED if "blank frame" in (s.get("error") or "") else
                E_JUDGE_REJECTED if "rejected by judge" in (s.get("error") or "") else
                E_BACKEND_DOWN if "not answering" in (s.get("error") or "") else E_ENGINE)
            jobs.set_phase(jid, "failed", s.get("error") or "unknown", code)


def _new_run(brief: str, model: str, kind: str, params: dict = None,
             idem_key: str = None):
    """Create a durable job + its artifact dir. Returns (run_dir, created)."""
    jid, created = jobs.create(kind, model, brief, params or {}, idem_key)
    run_dir = RUNS / jid
    if created:
        run_dir.mkdir(exist_ok=True)
        _status(run_dir, id=jid, brief=brief, model=model, kind=kind, phase="queued")
    return run_dir, created


# ---------- create loop ----------

MODEL_CHOICES = Literal["local:flux.1-schnell", "local:flux.2-klein",
                        "comfy:flux.1-schnell",
                        "nim:flux.1-schnell", "nim:flux.1-dev",
                        "gpt_image_2", "nano_banana_2", "z_image"]


class RunReq(BaseModel):
    brief: str = Field(min_length=3, max_length=2000)
    prompt: str = Field("", max_length=4000)  # expanded prompt; falls back to brief
    variations: list[str] = Field(default=[], max_length=8)
    model: MODEL_CHOICES = "local:flux.1-schnell"  # default MUST be free/local
    aspect_ratio: Literal["1:1", "16:9", "9:16", "4:3", "3:4"] = "1:1"
    reference: str = ""         # filename in uploads/ — Higgsfield models only


def _generate_one(run_dir: Path, i: int, prompt: str, req: RunReq) -> dict:
    cand = {"i": i, "prompt": prompt, "state": "generating"}
    try:
        return _generate_one_inner(cand, run_dir, i, prompt, req)
    except Exception as e:  # noqa: BLE001 — one bad candidate must never kill the run
        cand.update(state="failed", error=f"{type(e).__name__}: {str(e)[:200]}")
        return cand


def _generate_one_inner(cand: dict, run_dir: Path, i: int, prompt: str, req: RunReq) -> dict:
    if req.model.startswith("comfy:"):
        r = comfy_flux_image(prompt, run_dir / f"cand{i}.png", req.aspect_ratio)
    elif req.model.startswith("local:"):
        _, port = LOCAL_IMAGE_MODELS.get(req.model, ("nim-flux", 8018))
        r = flux_local(prompt, run_dir / f"cand{i}.png", req.aspect_ratio, port)
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
    if dead_frame(run_dir / r["file"]):
        # blank frames: retry fresh seed; if the blank is deterministic (prompt trips
        # this model's filter), cross-fall to the OTHER local FLUX — still free/local
        if req.model.startswith("local:"):
            backend, port = LOCAL_IMAGE_MODELS.get(req.model, ("nim-flux", 8018))
            r2 = flux_local(prompt, run_dir / f"cand{i}.png", req.aspect_ratio, port)
            if "error" in r2 or dead_frame(run_dir / f"cand{i}.png"):
                alt = ("nim-flux2", 8020) if backend == "nim-flux" else ("nim-flux", 8018)
                if ensure_backend(alt[0]):
                    r3 = flux_local(prompt, run_dir / f"cand{i}.png",
                                    req.aspect_ratio, alt[1])
                    if "error" not in r3 and not dead_frame(run_dir / f"cand{i}.png"):
                        cand["engine_note"] = f"blank on {backend}, rescued by {alt[0]}"
        if dead_frame(run_dir / r["file"]):
            cand.update(state="done", score=0, kill=True, fix=DEAD_FRAME_MSG)
            return cand
    v = safe_judge(run_dir / r["file"], json.loads((run_dir / "status.json").read_text())["brief"])
    cand.update(state="done", score=v.get("score", 0), kill=v.get("kill", False),
                fix=v.get("fix", ""))
    return cand


def _run_loop(run_dir: Path, req: RunReq):
    try:
        _run_loop_inner(run_dir, req)
    except JobCancelled:
        _status(run_dir, phase="cancelled", error="cancelled by request")
    except Exception as e:  # noqa: BLE001 — a run must always reach a terminal phase
        _status(run_dir, phase="failed", error=f"{type(e).__name__}: {str(e)[:250]}")


def _run_loop_inner(run_dir: Path, req: RunReq):
    if req.model.startswith("local:"):
        backend, _ = LOCAL_IMAGE_MODELS.get(req.model, ("nim-flux", 8018))
        if not ensure_backend(backend, run_dir):
            _status(run_dir, phase="failed",
                    error=f"{backend} would not start/warm — check Backends panel")
            return
    jobs.checkpoint(run_dir.name)
    base = req.prompt.strip() or req.brief
    n = max(len(req.variations), 1) if req.variations else 4
    prompts = [f"{base}; {v}" if v else base for v in (req.variations or [""] * n)]
    _status(run_dir, phase="generating", candidates=[])
    with ThreadPoolExecutor(max_workers=4) as pool:
        cands = list(pool.map(lambda t: _generate_one(run_dir, t[0], t[1], req),
                              enumerate(prompts, 1)))
    jobs.checkpoint(run_dir.name)
    done = [c for c in cands if c["state"] == "done" and not c.get("kill")
            and c.get("score", 0) > 3]
    if not done:
        _status(run_dir, phase="failed", candidates=cands,
                error=next((c.get("error") for c in cands if c.get("error")),
                           "no candidate scored above 3/10 — rework the prompt"))
        return
    winner = max(done, key=lambda c: c["score"])

    # ---- P2: automatic judge-driven improvement pass ----
    # If the winner is imperfect and the judge left a fix note, apply it via
    # local Kontext, re-judge, and keep the better image. Max 2 iterations,
    # stop on no improvement or score >= 8. Zero cost, fully local.
    if winner.get("score", 0) < 8 and winner.get("fix"):
        _status(run_dir, phase="improving", candidates=cands, winner=winner["i"])
        if ensure_backend("nim-kontext", run_dir):
            brief = req.brief
            for it in (1, 2):
                jobs.checkpoint(run_dir.name)
                improved = run_dir / f"improved{it}.png"
                instruction = (f"{winner['fix']} Keep the same subject, framing, "
                               f"composition and style — change nothing else.")
                r = kontext_local(run_dir / winner["file"], instruction, improved)
                if "error" in r or dead_frame(improved):
                    break
                v = safe_judge(improved, brief)
                new = {"i": 90 + it, "state": "done", "file": improved.name,
                       "score": v.get("score", 0), "kill": v.get("kill", False),
                       "fix": v.get("fix", ""), "auto_improved": True}
                cands.append(new)
                if not new["kill"] and new["score"] > winner["score"]:
                    winner = new
                    _status(run_dir, phase="improving", candidates=cands,
                            winner=winner["i"])
                    if winner["score"] >= 8:
                        break
                else:
                    break  # no improvement — keep the original winner

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
    if len(raw) > 30 * 1024 * 1024:
        return JSONResponse({"error": "upload exceeds 30MB limit",
                             "code": E_VALIDATION}, 413)
    safe = re.sub(r"[^\w.\-]", "_", req.name) or "upload.png"
    fname = f"{time.strftime('%H%M%S')}_{safe}"
    (UPLOADS / fname).write_bytes(raw)
    try:
        from PIL import Image
        Image.open(UPLOADS / fname).verify()
    except Exception:  # noqa: BLE001
        (UPLOADS / fname).unlink(missing_ok=True)
        return JSONResponse({"error": "not a decodable image",
                             "code": E_VALIDATION}, 422)
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
    allow_cloud_fallback: bool = False  # True = may spend Higgsfield credits


@app.post("/api/refine")
def refine(req: RefineReq):
    src = _resolve(req.file)
    if not src or not src.exists():
        return JSONResponse({"error": "file not found", "code": E_VALIDATION}, 404)
    run_dir, created = _new_run(req.instruction, "kontext-local", "refine",
                                req.model_dump())
    if not created:
        return {"id": run_dir.name, "idempotent_replay": True}

    def work():
        _status(run_dir, phase="generating", candidates=[])
        # local Kontext first (free); Higgsfield nano banana only if explicitly allowed
        ensure_backend("nim-kontext", run_dir)
        r = kontext_local(src, req.instruction, run_dir / "cand1.png")
        if "error" in r and req.allow_cloud_fallback:
            r = hf_generate("nano_banana_2", req.instruction, run_dir / "cand1.png",
                            ["--image", str(src)])
            if "error" not in r:
                _status(run_dir, model="nano_banana_2")  # truthful provenance
        if "error" in r:
            _status(run_dir, phase="failed", error=r["error"], candidates=[])
            return
        if dead_frame(run_dir / "cand1.png"):
            _status(run_dir, phase="failed", error=f"refine {DEAD_FRAME_MSG}",
                    candidates=[])
            return
        v = safe_judge(run_dir / "cand1.png", req.brief or req.instruction)
        cand = {"i": 1, "state": "done", "file": "cand1.png",
                "score": v.get("score", 0), "kill": v.get("kill", False),
                "fix": v.get("fix", "")}
        if v.get("kill") or v.get("score", 0) <= 3:
            _status(run_dir, phase="failed", candidates=[cand],
                    error=f"refine output rejected by judge ({v.get('score')}/10): "
                          f"{v.get('fix','')}")
            return
        final = run_dir / "final.png"
        grade(run_dir / "cand1.png", final)
        _status(run_dir, phase="done", candidates=[cand], winner=1,
                final=final.name if final.exists() else "cand1.png")

    threading.Thread(target=work, daemon=True).start()
    return {"id": run_dir.name}


def ltx_animate(src: Path, motion: str, out_mp4: Path, duration: int = 5) -> dict:
    """Image → cinema video WITH generated audio via LTX-2.3 22B nvfp4 (local ComfyUI)."""
    C = f"http://localhost:{COMFY_PORT}"
    frames = min(241, max(25, (int(duration) * 24 // 8) * 8 + 1))
    try:
        with open(src, "rb") as f:
            up = requests.post(f"{C}/upload/image",
                               files={"image": (src.name, f, "image/png")},
                               timeout=60).json()
        ck = "ltx-2.3-22b-dev-nvfp4.safetensors"
        g = {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ck}},
            "2": {"class_type": "LTXAVTextEncoderLoader", "inputs": {
                "text_encoder": "gemma_3_12B_it_fp4_mixed.safetensors",
                "ckpt_name": ck, "device": "default"}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": motion, "clip": ["2", 0]}},
            "4": {"class_type": "CLIPTextEncode", "inputs": {
                "text": "static, frozen, blurry, distorted, text, watermark, morphing",
                "clip": ["2", 0]}},
            "5": {"class_type": "LTXVConditioning", "inputs": {
                "positive": ["3", 0], "negative": ["4", 0], "frame_rate": 24.0}},
            "6": {"class_type": "LoadImage", "inputs": {"image": up["name"]}},
            "7": {"class_type": "LTXVImgToVideo", "inputs": {
                "positive": ["5", 0], "negative": ["5", 1], "vae": ["1", 2],
                "image": ["6", 0], "width": 768, "height": 768, "length": frames,
                "batch_size": 1, "strength": 1.0}},
            "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
            "9": {"class_type": "LTXVScheduler", "inputs": {
                "steps": 24, "max_shift": 2.05, "base_shift": 0.95,
                "stretch": True, "terminal": 0.1}},
            "14": {"class_type": "LTXVAudioVAELoader", "inputs": {"ckpt_name": ck}},
            "15": {"class_type": "LTXVEmptyLatentAudio", "inputs": {
                "frames_number": frames, "frame_rate": 24, "batch_size": 1,
                "audio_vae": ["14", 0]}},
            "16": {"class_type": "LTXVConcatAVLatent", "inputs": {
                "video_latent": ["7", 2], "audio_latent": ["15", 0]}},
            "10": {"class_type": "SamplerCustom", "inputs": {
                "model": ["1", 0], "add_noise": True,
                "noise_seed": int(time.time()) % 100000, "cfg": 3.5,
                "positive": ["7", 0], "negative": ["7", 1], "sampler": ["8", 0],
                "sigmas": ["9", 0], "latent_image": ["16", 0]}},
            "17": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["10", 0]}},
            "11": {"class_type": "VAEDecode", "inputs": {"samples": ["17", 0], "vae": ["1", 2]}},
            "18": {"class_type": "LTXVAudioVAEDecode", "inputs": {
                "samples": ["17", 1], "audio_vae": ["14", 0]}},
            "12": {"class_type": "CreateVideo", "inputs": {
                "images": ["11", 0], "fps": 24.0, "audio": ["18", 0]}},
            "13": {"class_type": "SaveVideo", "inputs": {
                "video": ["12", 0], "filename_prefix": "beast/cinema",
                "format": "mp4", "codec": "h264"}},
        }
        pid = requests.post(f"{C}/prompt", json={"prompt": g, "client_id": "beast"},
                            timeout=60).json()["prompt_id"]
        t0 = time.time()
        while time.time() - t0 < 3000:
            time.sleep(15)
            h = requests.get(f"{C}/history/{pid}", timeout=30).json()
            if pid in h and h[pid]["status"].get("completed"):
                img = h[pid]["outputs"]["13"]["images"][0]
                shutil.copy2(COMFY_DIR / "output" / img["subfolder"] / img["filename"],
                             out_mp4)
                return {"file": out_mp4.name}
            if pid in h and h[pid]["status"].get("status_str") == "error":
                return {"error": "LTX render errored — check ComfyUI"}
        return {"error": "LTX render timed out (50 min)"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"cinema video failed: {str(e)[:200]}"}


class AnimateReq(BaseModel):
    file: str
    motion: str = Field("slow cinematic dolly-in, subtle ambient movement",
                        max_length=1000)
    duration: Literal[3, 5] = 5
    quality: Literal["fast", "cinema"] = "fast"
    allow_cloud_fallback: bool = False  # True = may spend Higgsfield credits


def wan_animate(src: Path, motion: str, out_mp4: Path, duration: int = 5) -> dict:
    """Image → video via Wan 2.2 5B on local ComfyUI. Up to 5s (121 frames)."""
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
                "vae": ["3", 0], "width": 768, "height": 768,
                # duration seconds → frames @24fps, node step=4, Wan sweet spot ≤121 (5s)
                "length": min(121, max(25, (int(duration) * 24 // 4) * 4 + 1)),
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
    engine = "ltx-2.3-cinema" if req.quality == "cinema" else "wan2.2-local"
    run_dir, created = _new_run(req.motion, engine, "animate", req.model_dump())
    if not created:
        return {"id": run_dir.name, "idempotent_replay": True}

    def work():
        _status(run_dir, phase="generating", candidates=[
            {"i": 1, "state": f"{engine}: rendering (cinema ≈ 20-30 min, fast ≈ 2-4 min)"}])
        with jobs.GPU_HEAVY:  # one heavy video/3D job at a time
            jobs.checkpoint(run_dir.name)
            if req.quality == "cinema":
                r = ltx_animate(src, req.motion, run_dir / "clip.mp4", req.duration)
            else:
                r = wan_animate(src, req.motion, run_dir / "clip.mp4", req.duration)
        if "error" in r and req.allow_cloud_fallback:
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
UE58_EXE = Path(r"D:\DEpic GamesUE_5.8\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe")
BEASTLAB = r"D:\Epic Games\Projects\BeastLab\BeastLab.uproject"
UE_MCP_PORT = 8000


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
    upid = _port_pid(UE_MCP_PORT)
    uready = False
    if upid:
        try:  # MCP endpoint answers POST; 405/406 on GET still proves liveness
            uready = requests.get(f"http://localhost:{UE_MCP_PORT}/mcp",
                                  timeout=2).status_code in (200, 405, 406)
        except Exception:  # noqa: BLE001
            uready = False
    out.append({"name": "unreal-mcp", "state": "running" if upid else "exited",
                "ready": uready, "port": UE_MCP_PORT})
    return out


class BackendReq(BaseModel):
    name: str
    action: str  # start | stop


@app.post("/api/backend")
def backend(req: BackendReq):
    if req.action not in ("start", "stop"):
        return JSONResponse({"error": "unknown action"}, 400)
    if req.name == "unreal-mcp":
        pid = _port_pid(UE_MCP_PORT)
        if req.action == "start" and not pid:
            subprocess.Popen([str(UE58_EXE), BEASTLAB, "-nullrhi", "-nosplash",
                              "-unattended", "-ExecCmds=ModelContextProtocol.StartServer"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=0x00000008)
        elif req.action == "stop" and pid:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True,
                           timeout=30)
        return {"ok": True,
                "note": "engine boots ~1-2 min" if req.action == "start" else ""}
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
    allow_hosted_fallback: bool = False  # True = image may leave this machine


@app.post("/api/to3d")
def to_3d(req: To3DReq):
    src = _resolve(req.file)
    if not src or not src.exists():
        return JSONResponse({"error": "file not found"}, 404)
    run_dir, created = _new_run("image → 3D (TRELLIS)", "trellis", "3d",
                                req.model_dump())
    if not created:
        return {"id": run_dir.name, "idempotent_replay": True}

    def work():
        _status(run_dir, phase="generating", candidates=[])
        with jobs.GPU_HEAVY:
            jobs.checkpoint(run_dir.name)
            ensure_backend("nim-trellis", run_dir)
            r = trellis_3d(src, run_dir / "model.glb", req.allow_hosted_fallback)
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
    run_dir, created = _new_run(f"UE import: {src.name}", "ue-bridge", "unreal",
                                req.model_dump())
    if not created:
        return {"id": run_dir.name, "idempotent_replay": True}

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
        asset = m.group(1).strip().strip("'\"") if m and m.group(1).strip() else ""
        # UE can crash on shutdown AFTER writing the asset, garbling the stdout
        # marker — trust the disk: the .uasset landing is the real success signal.
        landed = (UE_CONTENT / f"{fbx.stem}.uasset")
        if not asset and not landed.exists():
            _status(run_dir, phase="failed",
                    error=f"UE import produced no asset: {(u.stdout or u.stderr)[-250:]}")
            return
        if not asset:
            asset = f"/Game/BeastAssets/{fbx.stem}"
        _status(run_dir, phase="done", candidates=[
            {"i": 1, "state": "done", "fix": f"in RouteRush at {asset}"}],
            ue_asset=asset)

    threading.Thread(target=work, daemon=True).start()
    return {"id": run_dir.name}


@app.post("/api/run")
def start_run(req: RunReq, idempotency_key: str = Header(None)):
    if req.reference and req.model.startswith(("local:", "nim:")):
        return JSONResponse({"error": "reference images are only supported by Higgsfield "
                             "models (nano_banana_2, gpt_image_2) — local FLUX would "
                             "silently ignore it. Drop the reference or switch model.",
                             "code": E_VALIDATION}, 400)
    run_dir, created = _new_run(req.brief, req.model, "create",
                                req.model_dump(), idempotency_key)
    if created:
        threading.Thread(target=_run_loop, args=(run_dir, req), daemon=True).start()
    return {"id": run_dir.name, "idempotent_replay": not created}


@app.get("/api/run/{run_id}")
def run_status(run_id: str):
    f = RUNS / run_id / "status.json"
    if not f.exists():
        j = jobs.get(run_id)
        if j:
            return {"id": run_id, "phase": j["phase"], "error": j["error"],
                    "error_code": j["error_code"], "kind": j["kind"]}
        return JSONResponse({"error": "not found"}, status_code=404)
    s = json.loads(f.read_text())
    j = jobs.get(run_id)
    if j:
        s["error_code"] = j["error_code"]
        if j["phase"] == "cancelled":
            s["phase"] = "cancelled"
    return s


@app.post("/api/job/{run_id}/cancel")
def cancel_job(run_id: str):
    if not jobs.get(run_id):
        return JSONResponse({"error": "not found"}, 404)
    ok = jobs.request_cancel(run_id)
    # if a ComfyUI render is in flight, interrupt it too
    try:
        requests.post(f"http://localhost:{COMFY_PORT}/interrupt", timeout=3)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": ok, "note": "queued jobs cancel instantly; running jobs stop at "
                              "their next stage checkpoint"}


@app.post("/api/job/{run_id}/retry")
def retry_job(run_id: str):
    j = jobs.get(run_id)
    if not j:
        return JSONResponse({"error": "not found"}, 404)
    if j["phase"] not in ("failed", "cancelled"):
        return JSONResponse({"error": f"job is {j['phase']} — only failed/cancelled "
                             "jobs can be retried", "code": E_VALIDATION}, 400)
    dispatch = {"create": (start_run, RunReq), "refine": (refine, RefineReq),
                "animate": (animate, AnimateReq), "3d": (to_3d, To3DReq),
                "unreal": (to_ue, ToUEReq)}
    if j["kind"] not in dispatch or not j["params"]:
        return JSONResponse({"error": "job kind not retryable", "code": E_VALIDATION}, 400)
    fn, model_cls = dispatch[j["kind"]]
    try:
        out = fn(model_cls(**j["params"])) if j["kind"] != "create" else fn(
            model_cls(**j["params"]), None)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"retry failed: {str(e)[:200]}"}, 500)
    return out


@app.get("/api/health")
def health():
    db_ok = bool(jobs.recent(1) is not None)
    import shutil as _sh
    free_gb = _sh.disk_usage(str(RUNS)).free // 2**30
    return {"ok": db_ok and free_gb > 5, "db": db_ok, "disk_free_gb": free_gb,
            "active_jobs": [r["id"] for r in jobs.recent(50)
                            if r["phase"] in ("queued", "running")]}


@app.get("/api/events/{run_id}")
def events(run_id: str):
    """Server-sent events: one JSON event per phase change until terminal."""
    def gen():
        last = None
        for _ in range(1800):  # cap at ~1 hour
            f = RUNS / run_id / "status.json"
            s = json.loads(f.read_text()) if f.exists() else {}
            j = jobs.get(run_id) or {}
            s["phase"] = "cancelled" if j.get("phase") == "cancelled" else s.get("phase")
            snap = json.dumps(s)
            if snap != last:
                last = snap
                yield f"data: {snap}\n\n"
            if s.get("phase") in ("done", "failed", "cancelled"):
                return
            time.sleep(2)
    return StreamingResponse(gen(), media_type="text/event-stream")


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
