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
    if req.model.startswith("nim:"):
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
    final = run_dir / "final.png"
    grade(run_dir / winner["file"], final)
    _status(run_dir, phase="done", final=final.name if final.exists() else winner["file"])


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


@app.post("/api/animate")
def animate(req: AnimateReq):
    src = _resolve(req.file)
    if not src or not src.exists():
        return JSONResponse({"error": "file not found"}, 404)
    run_dir = _new_run(req.motion, "seedance_2_0", "animate")

    def work():
        _status(run_dir, phase="generating", candidates=[])
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
