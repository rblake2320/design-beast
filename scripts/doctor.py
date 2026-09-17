"""beast doctor — verify the whole design stack in one pass.

Every check prints OK / WARN / FAIL with a one-line fix hint. Exit code is the
number of FAILs, so agents and CI can gate on it. Optional lanes degrade to
WARN, never FAIL — the stack is modular by design (CLAUDE.md non-negotiable #1:
report degradation, never silently skip).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "studio"))
import config  # noqa: E402

FFMPEG_HINT = (Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
               / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
               / "ffmpeg-8.1.2-full_build/bin")

results: list[tuple[str, str, str]] = []  # (level, name, note)


def check(name: str, ok: bool | None, note: str = "", fix: str = "") -> None:
    level = "OK" if ok else ("WARN" if ok is None else "FAIL")
    results.append((level, name, note if ok else f"{note}  fix: {fix}".strip()))


def _http_ok(url: str, timeout: float = 3) -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def _tool(name: str) -> str | None:
    if shutil.which(name):
        return name
    hinted = FFMPEG_HINT / f"{name}.exe"
    return str(hinted) if hinted.exists() else None


# ---- core tools ----
check("python 3.12+", sys.version_info >= (3, 12), sys.version.split()[0],
      "install Python 3.12")
check("ffmpeg", _tool("ffmpeg") is not None,
      "on PATH or winget location", "winget install Gyan.FFmpeg; add bin to PATH")
check("ffprobe", _tool("ffprobe") is not None, "", "comes with ffmpeg")
check("yt-dlp", shutil.which("yt-dlp") is not None,
      "needed by beast watch", "pip install yt-dlp")
check("node >= 22", shutil.which("node") is not None,
      "needed by HyperFrames", "winget install OpenJS.NodeJS.LTS")
check("git", shutil.which("git") is not None, "", "winget install Git.Git")

# ---- ComfyUI lane ----
comfy_dir = Path(config.get("comfy_dir"))
check("ComfyUI install", comfy_dir.exists(), str(comfy_dir),
      "git clone ComfyUI to comfy_dir (see docs/SETUP.md)")
if comfy_dir.exists():
    check("ComfyUI venv", (comfy_dir / config.get("comfy_python")).exists(), "",
          "python -m venv venv + install requirements in ComfyUI dir")
    models = {
        "flux1-schnell-fp8.safetensors": "checkpoints",
        "ltx-2.3-22b-dev-nvfp4.safetensors": "checkpoints",
        "wan2.2_ti2v_5B_fp16.safetensors": "diffusion_models",
        "wan2.2_vae.safetensors": "vae",
        "umt5_xxl_fp8_e4m3fn_scaled.safetensors": "text_encoders",
        "gemma_3_12B_it_fp4_mixed.safetensors": "text_encoders",
    }
    missing = [n for n, d in models.items()
               if not (comfy_dir / "models" / d / n).exists()]
    check("ComfyUI models (flux/ltx/wan)", not missing,
          "all present" if not missing else f"missing: {', '.join(missing)}",
          "download per docs/SETUP.md")
    up = _http_ok("http://localhost:8188/system_stats")
    check("ComfyUI server :8188", True if up else None,
          "running" if up else "not running (auto-starts on demand)", "")

# ---- local AI services ----
ollama = _http_ok("http://localhost:11434/api/tags")
check("Ollama :11434", ollama, "", "install Ollama; ollama serve")
if ollama:
    try:
        import urllib.request
        tags = json.loads(urllib.request.urlopen(
            "http://localhost:11434/api/tags", timeout=5).read())
        names = {m["name"].split(":")[0] for m in tags.get("models", [])}
        judge = config.get("judge_model").split(":")[0]
        check(f"judge model ({config.get('judge_model')})", judge in names, "",
              f"ollama pull {config.get('judge_model')}")
    except Exception:  # noqa: BLE001
        check("judge model", None, "could not list Ollama models", "")
check("MemoryWeb :8100", True if _http_ok("http://localhost:8100/api/health")
      else None, "", "nssm restart MemoryWeb-API (optional service)")

# ---- beast library (media organizer) lane — optional, degrades to WARN ----
_lib_missing = []
for mod in ("imagehash", "insightface", "easyocr", "transformers", "onnxruntime", "pgvector"):
    try:
        __import__(mod)
    except ImportError:
        _lib_missing.append(mod)
check("library python deps", True if not _lib_missing else None,
      "imagehash insightface easyocr transformers onnxruntime pgvector" if not _lib_missing
      else f"missing: {' '.join(_lib_missing)}", "pip install -r requirements-library.txt")
_siglip = "models--" + config.get("library_embed_model").replace("/", "--")
_hf_dirs = [Path(os.environ.get("HF_HOME", Path.home() / ".cache/huggingface")) / "hub"]
for _var in ("HF_HUB_CACHE", "TRANSFORMERS_CACHE"):   # transformers honours both (legacy on Windows boxes)
    if os.environ.get(_var):
        _hf_dirs.append(Path(os.environ[_var]))
_siglip_hit = next((d / _siglip for d in _hf_dirs if (d / _siglip).exists()), None)
check("library SigLIP2 weights", True if _siglip_hit else None, str(_siglip_hit or _hf_dirs[0] / _siglip),
      "first `beast library embed` run downloads them (~1.6 GB)")
_face = Path.home() / ".insightface/models/buffalo_l"
check("library InsightFace buffalo_l", True if _face.exists() else None, str(_face),
      "first `beast library faces` run downloads it (~300 MB)")
if ollama:
    _lib_models = {config.get("library_fast_model"), config.get("library_deep_model"), "bge-m3"}
    try:
        _have = {m["name"] for m in tags.get("models", [])} | {m["name"].split(":")[0] for m in tags.get("models", [])}
        _lack = sorted(m for m in _lib_models if m not in _have and m.split(":")[0] not in _have)
        check("library review models", True if not _lack else None,
              ", ".join(sorted(_lib_models)) if not _lack else f"missing: {', '.join(_lack)}",
              "ollama pull " + " ".join(_lack))
    except NameError:
        check("library review models", None, "could not list Ollama models", "")
check("library store", True, "postgres/pgvector (shared, BEAST_LIBRARY_DSN)" if config.get("library_dsn")
      else f"sqlite {config.get('library_db')}")


def _down_hours(key: str, up: bool) -> float:
    """Remember since when a lane has been down so a stale outage reads as one, not a blip."""
    import time
    state_path = REPO / "session" / "doctor-state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    except ValueError:
        state = {}
    hours = 0.0
    if up:
        state.pop(key, None)
    else:
        hours = (time.time() - state.setdefault(key, time.time())) / 3600
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return hours


# Outcome checks on the store itself: stuck work, permanent errors, a stale backup.
_lib_db = Path(config.get("library_db"))
if _lib_db.exists() and not config.get("library_dsn"):
    try:
        import sqlite3 as _sq
        _c = _sq.connect(str(_lib_db))
        _stuck = _c.execute("SELECT COUNT(*) FROM queue WHERE status = 'running' AND claimed_at < ?",
                            (time.strftime("%Y-%m-%dT%H:%M:%S",
                             time.localtime(time.time() - 3600)),)).fetchone()[0]
        _errs = _c.execute("SELECT COUNT(*) FROM queue WHERE status = 'error'").fetchone()[0]
        _last_bak = _c.execute("SELECT ts FROM ledger WHERE event = 'backup' ORDER BY id DESC LIMIT 1").fetchone()
        _n = _c.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        _c.close()
        check("library queue: no stuck claims (>1h)", _stuck == 0, f"{_stuck} stuck of {_n} assets",
              "beast library recover")
        check("library queue: no error rows", True if _errs == 0 else None, f"{_errs} errors",
              "beast library recover  (requeues once; inspect ledger if they return)")
        _bak_age_h = ((time.time()
                       - time.mktime(time.strptime(_last_bak[0], "%Y-%m-%dT%H:%M:%S")))
                      / 3600) if _last_bak else None
        check("library backup age", True if _bak_age_h is not None and _bak_age_h < 48 else (None if _n < 50 else False),
              f"{_bak_age_h:.0f} h" if _bak_age_h is not None else "never", "beast library backup --dir <dest>/.beast/backups")
    except Exception as _exc:  # noqa: BLE001
        check("library store health", False, f"{type(_exc).__name__}: {_exc}"[:80], "beast library recover / restore")

_vllm_up = _http_ok(config.get("library_vllm_url").split("/v1/")[0] + "/health")
_vllm_h = _down_hours("library_vllm", _vllm_up)
# The batched tier is the 8x knob: after a day down it is a FAIL, not an "optional lane".
check("library batched review (vLLM :8021)", True if _vllm_up else (None if _vllm_h < 24 else False),
      config.get("library_review_model") if _vllm_up
      else f"down for {_vllm_h:.1f} h — fast tier falls back to Ollama (8x slower)",
      "docker start beast-vllm  (recipe: docs/LIBRARY.md)")

# ---- audio / vision venvs (optional lanes) ----
for name, path in [
    ("yolo-vision venv", Path(r"D:\content\yolo-vision\.venv")),
    ("chatterbox venv", Path(r"D:\AI\tts\chatterbox-venv")),
    ("ACE-Step install", Path(r"D:\AI\ACE-Step-1.5\.venv")),
    ("kokoro model", Path(config.get("kokoro_dir"))),
    ("Real-ESRGAN", Path(config.get("esrgan"))),
]:
    check(name, True if path.exists() else None, str(path),
          "see docs/SETUP.md for this lane")

# ---- game editing suite (optional lane, installed 2026-07-31) ----
for name, path in [
    ("Krita", Path(r"C:\Program Files\Krita (x64)\bin\krita.exe")),
    ("GIMP 3", Path(r"C:\Users\techai\AppData\Local\Programs\GIMP 3\bin\gimp-3.exe")),
    ("Audacity", Path(r"C:\Program Files\Audacity\audacity.exe")),
    ("Tiled", Path(r"C:\Program Files\Tiled\tiled.exe")),
    ("Inkscape", Path(r"C:\Program Files\Inkscape\bin\inkscape.exe")),
    ("Godot 4.7", Path(r"D:\tools\godot\Godot_v4.7.1-stable_win64.exe")),
    ("Pixelorama", Path(r"D:\tools\pixelorama\Pixelorama-Windows-64bit\Pixelorama.exe")),
]:
    check(name, True if path.exists() else None, "",
          "see STACK.md game-editing row (winget / GitHub releases)")
check("gltf-transform", shutil.which("gltf-transform") is not None, "",
      "npm install -g @gltf-transform/cli")

# ---- engines (optional lanes) ----
check("Blender", Path(config.get("blender")).exists(), "",
      "install Blender 5.x, update config")
check("UE 5.8 (BeastLab MCP host)", Path(config.get("ue58_exe")).exists(), "",
      "optional — game lane")
check("UE 5.6 (to_ue target)", Path(config.get("ue_cmd")).exists(), "",
      "optional — game lane")

# ---- integrity ----
sys.path.insert(0, str(REPO / "studio"))
import ledger  # noqa: E402
ok, msg = ledger.verify(REPO / "studio" / "runs" / ledger.LEDGER_NAME)
check("provenance ledger chain", ok, msg, "investigate tampering/corruption")
prov_errors = list((REPO / "studio" / "runs").glob("*/provenance_error.txt"))
check("provenance writes", not prov_errors,
      "clean" if not prov_errors else
      f"{len(prov_errors)} run(s) failed to record provenance "
      f"(e.g. {prov_errors[0].parent.name})",
      "read the provenance_error.txt files; manifests may be missing")
baseline = REPO / "studio" / ".beast_env_baseline.json"
if baseline.exists() and comfy_dir.exists():
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "replay_diff.py"),
                        "--check"], capture_output=True, text=True, timeout=300)
    check("env drift vs baseline", True if r.returncode == 0 else None,
          r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "",
          "beast replay --save-baseline to accept current env")

# ---- registry sanity ----
import registry  # noqa: E402
try:
    entries = registry.load()
    kinds = {b["kind"] for b in entries}
    local_ok = all(any(b["kind"] == k and b["hosting"] == "local"
                       for b in entries) for k in kinds)
    check("registry: local default per kind", local_ok,
          f"{len(entries)} backends / {len(kinds)} kinds",
          "every kind needs a free local backend (product promise)")
except Exception as e:  # noqa: BLE001
    check("registry loads", False, str(e)[:80], "fix studio/model_registry.json")

# ---- disk ----
free_gb = shutil.disk_usage("D:\\").free / 1e9 if os.name == "nt" else \
    shutil.disk_usage("/").free / 1e9
check("disk free (D:)", free_gb > 100, f"{free_gb:.0f} GB",
      "models + renders need headroom; clean studio/runs or watched/")

# ---- report ----
width = max(len(n) for _, n, _ in results) + 2
fails = 0
for level, name, note in results:
    mark = {"OK": "[ OK ]", "WARN": "[warn]", "FAIL": "[FAIL]"}[level]
    print(f"{mark} {name:<{width}} {note}")
    fails += level == "FAIL"
warns = sum(1 for lv, _, _ in results if lv == "WARN")
print(f"\n{len(results)} checks: {len(results) - fails - warns} ok, "
      f"{warns} degraded (optional), {fails} failing")
sys.exit(fails)
