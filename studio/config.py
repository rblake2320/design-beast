"""Per-node configuration for Beast Studio.

Resolution order for every key:
  1. env var  BEAST_<KEY>            (e.g. BEAST_COMFY_DIR=/data/comfyui)
  2. repo-root beast.config.json     (gitignored — node-local)
  3. platform default below          (Windows = the original dev box paths)

Optional features (Unreal, Blender, ESRGAN, Kokoro, ComfyUI) degrade cleanly:
if the configured path does not exist on this node, the endpoint that needs it
reports "not available on this node" instead of crashing. This is what makes
`git clone` on a DGX Spark / Linux box a real deployment path.
"""
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_file_cfg: dict = {}
_cfg_path = REPO / "beast.config.json"
if _cfg_path.exists():
    try:
        _file_cfg = json.loads(_cfg_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 — a broken config must be loud
        raise SystemExit(f"beast.config.json is not valid JSON: {e}")

_WIN = sys.platform == "win32"

_DEFAULTS = {
    # engines / tools (paths)
    "esrgan": (r"D:\ai\tools\realesrgan\realesrgan-ncnn-vulkan.exe" if _WIN
               else "~/beast/tools/realesrgan/realesrgan-ncnn-vulkan"),
    "kokoro_dir": r"D:\ai\tools\kokoro" if _WIN else "~/beast/models/kokoro",
    "blender": (r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
                if _WIN else "/usr/bin/blender"),
    "comfy_dir": r"D:\ai\comfyui" if _WIN else "~/beast/comfyui",
    "comfy_python": ("venv/Scripts/python.exe" if _WIN else "venv/bin/python"),
    # Unreal is Windows/x86-only in this shop — empty default elsewhere
    "ue_cmd": (r"D:\Epic Games\UE_5.6\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
               if _WIN else ""),
    "ue_project": (r"C:\Users\techai\route-rush-unreal\RouteRush.uproject"
                   if _WIN else ""),
    "ue_content": (r"C:\Users\techai\route-rush-unreal\Content\BeastAssets"
                   if _WIN else ""),
    "ue58_exe": (r"D:\DEpic GamesUE_5.8\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
                 if _WIN else ""),
    "beastlab": (r"D:\Epic Games\Projects\BeastLab\BeastLab.uproject" if _WIN else ""),
    # services (urls / ports are identical across nodes by convention)
    "ollama_url": "http://localhost:11434/api/generate",
    "judge_model": "qwen3-vl:8b",
    "expand_models": "qwen3.6:27b,gemma3:latest",
}


def get(key: str, default: str = "") -> str:
    env = os.environ.get(f"BEAST_{key.upper()}")
    if env is not None:
        return env
    if key in _file_cfg:
        return str(_file_cfg[key])
    return _DEFAULTS.get(key, default)


def path(key: str) -> Path:
    """Path-valued key. Empty/unset resolves to a guaranteed-missing path so
    feature guards (`X.exists()`) stay one-liners."""
    v = get(key)
    if not v:
        return Path("__unset__/missing")
    return Path(os.path.expanduser(v))
