"""Artifact provenance manifests for Beast Studio.

The manifest is deliberately local and deterministic: it records how an
artifact was produced without copying credentials, image bytes, or prompts
outside the run directory.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
MANIFEST_NAME = "manifest.json"
_SECRET_KEYS = {
    "authorization", "api_key", "apikey", "token", "secret", "password",
    "cookie", "nvcf_run_key",
}


def _redact(value: Any, key: str = "") -> Any:
    if key.lower() in _SECRET_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, tuple):
        return [_redact(v) for v in value]
    return value


def artifact_record(run_dir: Path, file: str | Path) -> dict[str, Any]:
    """Return a checksum record for a file contained by ``run_dir``."""
    root = run_dir.resolve()
    path = (run_dir / file).resolve() if not Path(file).is_absolute() else Path(file).resolve()
    if not path.is_relative_to(root):
        raise ValueError("artifact must be inside its run directory")
    if not path.is_file():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for block in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(block)
    return {
        "file": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
        "media_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
    }


def write_manifest(
    run_dir: Path,
    *,
    run_id: str,
    kind: str,
    model: str,
    params: dict[str, Any] | None = None,
    artifacts: list[str | Path] | None = None,
    engine: dict[str, Any] | None = None,
    seed: int | None = None,
    workflow: str | None = None,
) -> Path:
    """Atomically write a redacted, checksum-backed provenance manifest."""
    run_dir.mkdir(parents=True, exist_ok=True)
    records = [artifact_record(run_dir, item) for item in (artifacts or [])]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "kind": kind,
        "created_unix": time.time(),
        "model": model,
        "engine": _redact(engine or {}),
        "seed": seed,
        "workflow": workflow,
        "params": _redact(params or {}),
        "artifacts": records,
    }
    target = run_dir / MANIFEST_NAME
    temp = run_dir / f".{MANIFEST_NAME}.{os.getpid()}.tmp"
    temp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp, target)
    return target
