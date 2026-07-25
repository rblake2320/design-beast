#!/usr/bin/env python3
"""Beast Studio — local web UI for the design-beast quality loop.

Run:  python studio/server.py   →  http://localhost:8787
Flow: brief → N candidates (Higgsfield CLI) → local vision judge → grade winner.
"""
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

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
RUNS = ROOT / "runs"
RUNS.mkdir(exist_ok=True)
sys.path.insert(0, str(REPO / "scripts"))
from judge_image import judge  # noqa: E402

app = FastAPI(title="Beast Studio")
app.mount("/runs", StaticFiles(directory=RUNS), name="runs")
LOCK = threading.Lock()


class RunReq(BaseModel):
    brief: str
    variations: list[str] = []  # one per candidate; empty → 4 identical
    model: str = "gpt_image_2"
    aspect_ratio: str = "1:1"


def _status(run_dir: Path, **updates):
    with LOCK:
        f = run_dir / "status.json"
        s = json.loads(f.read_text()) if f.exists() else {}
        s.update(updates)
        f.write_text(json.dumps(s, indent=1))


def _generate_one(run_dir: Path, i: int, prompt: str, model: str, ar: str) -> dict:
    cand = {"i": i, "prompt": prompt, "state": "generating"}
    hf = shutil.which("higgsfield") or "higgsfield"
    cmd = [hf, "generate", "create", model, "--prompt", prompt,
           "--aspect_ratio", ar, "--wait", "--wait-timeout", "15m", "--json"]
    if model == "gpt_image_2":
        cmd += ["--resolution", "2k"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1000)
        urls = re.findall(r'https://[^"\s]+\.(?:png|jpe?g|webp)[^"\s]*', proc.stdout)
        if not urls:
            cand.update(state="failed", error=(proc.stderr or proc.stdout)[-300:])
            return cand
        img = run_dir / f"cand{i}.png"
        urllib.request.urlretrieve(urls[0], img)
        cand.update(state="judging", url=urls[0], file=img.name)
        brief = json.loads((run_dir / "status.json").read_text())["brief"]
        try:
            v = judge(str(img), brief, "qwen3-vl:8b")
        except Exception:  # noqa: BLE001 — one retry after cold-load timeout
            v = judge(str(img), brief, "qwen3-vl:8b")
        cand.update(state="done", score=v.get("score", 0), kill=v.get("kill", False),
                    fix=v.get("fix", ""))
    except Exception as e:  # noqa: BLE001 — surface per-candidate failure in UI
        cand.update(state="failed", error=str(e)[:300])
    return cand


def _run_loop(run_dir: Path, req: RunReq):
    n = max(len(req.variations), 1) if req.variations else 4
    prompts = [f"{req.brief}; {v}" if v else req.brief
               for v in (req.variations or [""] * n)]
    _status(run_dir, phase="generating", candidates=[])
    with ThreadPoolExecutor(max_workers=4) as pool:
        cands = list(pool.map(
            lambda t: _generate_one(run_dir, t[0], t[1], req.model, req.aspect_ratio),
            enumerate(prompts, 1)))
    done = [c for c in cands if c["state"] == "done" and not c.get("kill")]
    if not done:
        _status(run_dir, phase="failed", candidates=cands)
        return
    winner = max(done, key=lambda c: c["score"])
    _status(run_dir, phase="grading", candidates=cands, winner=winner["i"])
    final = run_dir / "final.png"
    subprocess.run([shutil.which("magick") or "magick", str(run_dir / winner["file"]),
                    "-modulate", "100,93", "-level", "1%,99.5%", str(final)],
                   capture_output=True, timeout=120)
    _status(run_dir, phase="done",
            final=final.name if final.exists() else winner["file"])


@app.get("/")
def index():
    return FileResponse(ROOT / "index.html")


@app.get("/api/recipes")
def recipes():
    out = []
    for f in sorted((REPO / "design-system" / "recipes").glob("*.md")):
        title = f.read_text(encoding="utf-8").splitlines()[0].lstrip("# ")
        out.append({"name": f.stem, "title": title})
    return out


@app.post("/api/run")
def start_run(req: RunReq):
    run_id = time.strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS / run_id
    run_dir.mkdir()
    _status(run_dir, id=run_id, brief=req.brief, model=req.model, phase="queued")
    threading.Thread(target=_run_loop, args=(run_dir, req), daemon=True).start()
    return {"id": run_id}


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
            out.append({"id": s.get("id", d.name), "brief": s.get("brief", "")[:80],
                        "phase": s.get("phase"), "final": s.get("final")})
    return out[:30]


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8787)
