"""Execution-environment snapshots for exact replay (WIN-PLAN move #1).

Captures, per ComfyUI-backed run: ComfyUI + custom-node commits, a package-set
digest of the Comfy venv, the exact submitted graph hash, and SHA-256 of every
model file the graph references. The snapshot lands in the run dir as
``environment.json`` and is folded into the provenance manifest at terminal
state. ``diff()`` names every drifted component precisely — the answer to
ComfyUI's "worked Friday, red box Monday" problem.

Costs are kept honest: git introspection is milliseconds; ``pip freeze`` is
subprocess-cached for PKG_CACHE_TTL_S; model hashing streams once per file
version ever, keyed by (path, size, mtime) in a persistent JSON cache beside
the models. All capture is best-effort — a snapshot failure must never fail
the run it describes.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
SNAPSHOT_NAME = "environment.json"
HASH_CACHE_NAME = ".beast_model_hashes.json"
PKG_CACHE_TTL_S = 600

# graph-input keys whose values name model files on disk
_MODEL_KEYS = ("ckpt_name", "unet_name", "vae_name", "clip_name", "clip_name1",
               "clip_name2", "text_encoder", "lora_name", "model_name")
# comfy model subdirs to search, in order
_MODEL_DIRS = ("checkpoints", "diffusion_models", "vae", "text_encoders",
               "clip", "loras", "unet", "upscale_models")

_pkg_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _git(dir_: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(dir_), *args],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:  # noqa: BLE001
        return None


def _repo_state(dir_: Path) -> dict[str, Any]:
    # `git -C` walks up to ancestor repos; only report a commit when this dir
    # is itself a repo root, so plain dirs never inherit a parent's identity.
    top = _git(dir_, "rev-parse", "--show-toplevel")
    if top is None or Path(top).resolve() != dir_.resolve():
        return {"commit": None}
    commit = _git(dir_, "rev-parse", "HEAD")
    if commit is None:
        return {"commit": None}
    return {"commit": commit,
            "dirty": bool(_git(dir_, "status", "--porcelain"))}


def _packages(comfy_python: Path) -> dict[str, Any]:
    """Digest of the Comfy venv's package set + the torch line, TTL-cached."""
    key = str(comfy_python)
    hit = _pkg_cache.get(key)
    if hit and time.time() - hit[0] < PKG_CACHE_TTL_S:
        return hit[1]
    try:
        out = subprocess.run([str(comfy_python), "-m", "pip", "freeze"],
                             capture_output=True, text=True, timeout=120)
        lines = sorted(ln.strip() for ln in out.stdout.splitlines() if ln.strip())
        torch_line = next((ln for ln in lines if ln.lower().startswith("torch==")), None)
        result = {
            "packages_sha256": hashlib.sha256("\n".join(lines).encode()).hexdigest(),
            "package_count": len(lines),
            "torch": torch_line.split("==", 1)[1] if torch_line else None,
        }
    except Exception:  # noqa: BLE001
        result = {"packages_sha256": None, "package_count": 0, "torch": None}
    _pkg_cache[key] = (time.time(), result)
    return result


# cache lives beside this module, NOT inside comfy_dir — a foreign file there
# flips the ComfyUI repo to dirty and pollutes the very drift signal we record
_CACHE_DIR = Path(__file__).resolve().parent


def _load_hash_cache(comfy_dir: Path) -> dict[str, Any]:
    try:
        return json.loads((_CACHE_DIR / HASH_CACHE_NAME).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_hash_cache(comfy_dir: Path, cache: dict[str, Any]) -> None:
    try:
        tmp = _CACHE_DIR / f"{HASH_CACHE_NAME}.{os.getpid()}.tmp"
        tmp.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, _CACHE_DIR / HASH_CACHE_NAME)
    except Exception:  # noqa: BLE001
        pass


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for block in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def graph_model_names(graph: dict[str, Any]) -> list[str]:
    """Every model filename the submitted graph references, sorted unique."""
    names: set[str] = set()
    for node in (graph or {}).values():
        inputs = node.get("inputs", {}) if isinstance(node, dict) else {}
        for key in _MODEL_KEYS:
            val = inputs.get(key)
            if isinstance(val, str) and val:
                names.add(val)
    return sorted(names)


def _model_records(comfy_dir: Path, names: list[str]) -> dict[str, Any]:
    """SHA-256 per referenced model file, via the persistent (size,mtime) cache."""
    cache = _load_hash_cache(comfy_dir)
    records: dict[str, Any] = {}
    dirty = False
    for name in names:
        path = next((p for d in _MODEL_DIRS
                     if (p := comfy_dir / "models" / d / name).is_file()), None)
        if path is None:
            records[name] = {"sha256": None, "note": "file not found"}
            continue
        st = path.stat()
        key = f"{path}|{st.st_size}|{int(st.st_mtime)}"
        if key not in cache:
            cache[key] = {"sha256": _file_sha256(path)}
            dirty = True
        records[name] = {"sha256": cache[key]["sha256"], "bytes": st.st_size}
    if dirty:
        _save_hash_cache(comfy_dir, cache)
    return records


def capture(comfy_dir: Path, comfy_python: Path,
            graph: dict[str, Any] | None = None) -> dict[str, Any]:
    """Snapshot everything a replay needs to name drift precisely."""
    nodes_dir = comfy_dir / "custom_nodes"
    custom_nodes = {}
    if nodes_dir.is_dir():
        for entry in sorted(nodes_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith((".", "__")):
                custom_nodes[entry.name] = _repo_state(entry)
    graph_json = json.dumps(graph, sort_keys=True) if graph else None
    return {
        "schema_version": SCHEMA_VERSION,
        "captured_unix": time.time(),
        "python": sys.version.split()[0],
        "comfy": _repo_state(comfy_dir),
        "custom_nodes": custom_nodes,
        **_packages(comfy_python),
        "graph_sha256": (hashlib.sha256(graph_json.encode()).hexdigest()
                         if graph_json else None),
        "models": _model_records(comfy_dir, graph_model_names(graph or {})),
    }


def capture_and_write(run_dir: Path, comfy_dir: Path, comfy_python: Path,
                      graph: dict[str, Any] | None = None) -> Path | None:
    """Best-effort: snapshot and persist to the run dir. Never raises."""
    try:
        snap = capture(comfy_dir, comfy_python, graph)
        run_dir.mkdir(parents=True, exist_ok=True)
        tmp = run_dir / f".{SNAPSHOT_NAME}.{os.getpid()}.tmp"
        tmp.write_text(json.dumps(snap, indent=2, sort_keys=True), encoding="utf-8")
        target = run_dir / SNAPSHOT_NAME
        os.replace(tmp, target)
        return target
    except Exception:  # noqa: BLE001
        return None


def load(run_dir: Path) -> dict[str, Any] | None:
    try:
        return json.loads((run_dir / SNAPSHOT_NAME).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def diff(recorded: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Human-readable drift lines between two snapshots. Empty list = no drift.

    Pure function — unit-testable without ComfyUI, git, or a GPU.
    """
    drift: list[str] = []

    def _commit(state: dict | None) -> str:
        if not state or state.get("commit") is None:
            return "untracked"
        return state["commit"][:12] + (" (dirty)" if state.get("dirty") else "")

    if (recorded.get("comfy") or {}).get("commit") != (current.get("comfy") or {}).get("commit") \
            or (recorded.get("comfy") or {}).get("dirty") != (current.get("comfy") or {}).get("dirty"):
        drift.append(f"ComfyUI: {_commit(recorded.get('comfy'))} -> "
                     f"{_commit(current.get('comfy'))}")

    rec_nodes = recorded.get("custom_nodes") or {}
    cur_nodes = current.get("custom_nodes") or {}
    for name in sorted(set(rec_nodes) | set(cur_nodes)):
        old, new = rec_nodes.get(name), cur_nodes.get(name)
        if old is None:
            drift.append(f"custom node ADDED since run: {name} ({_commit(new)})")
        elif new is None:
            drift.append(f"custom node REMOVED since run: {name}")
        elif old.get("commit") != new.get("commit") or old.get("dirty") != new.get("dirty"):
            drift.append(f"custom node {name}: {_commit(old)} -> {_commit(new)}")

    if recorded.get("torch") != current.get("torch"):
        drift.append(f"torch: {recorded.get('torch')} -> {current.get('torch')}")
    if recorded.get("packages_sha256") != current.get("packages_sha256"):
        drift.append(
            f"venv package set changed "
            f"({recorded.get('package_count')} -> {current.get('package_count')} pkgs; "
            f"digest {str(recorded.get('packages_sha256'))[:12]} -> "
            f"{str(current.get('packages_sha256'))[:12]})")

    rec_models = recorded.get("models") or {}
    cur_models = current.get("models") or {}
    for name in sorted(rec_models):
        old_sha = (rec_models.get(name) or {}).get("sha256")
        new_sha = (cur_models.get(name) or {}).get("sha256")
        if new_sha is None and old_sha is not None:
            drift.append(f"model MISSING: {name}")
        elif old_sha != new_sha:
            drift.append(f"model changed: {name} "
                         f"({str(old_sha)[:12]} -> {str(new_sha)[:12]})")

    if recorded.get("python") != current.get("python"):
        drift.append(f"python: {recorded.get('python')} -> {current.get('python')}")
    return drift
