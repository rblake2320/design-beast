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


def _media_type(path: Path) -> str:
    """Identify supported artifacts from bytes, then fall back to the suffix.

    Some backends return JPEG bytes while Beast keeps the requested ``.png``
    filename. Provenance must describe the artifact that actually exists, not
    the extension we expected the backend to honor.
    """
    with path.open("rb") as src:
        header = src.read(16)
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return "audio/wav"
    if len(header) >= 8 and header[4:8] == b"ftyp":
        return "video/mp4"
    if header.startswith(b"glTF"):
        return "model/gltf-binary"
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


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
        "media_type": _media_type(path),
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
    seed: Any | None = None,
    workflow: str | None = None,
    outcome: dict[str, Any] | None = None,
    environment: dict[str, Any] | None = None,
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
        "outcome": _redact(outcome or {}),
        "params": _redact(params or {}),
        "artifacts": records,
        # exact-replay record: comfy/node commits, venv digest, graph + model hashes
        "environment": _redact(environment) if environment else None,
    }
    target = run_dir / MANIFEST_NAME
    temp = run_dir / f".{MANIFEST_NAME}.{os.getpid()}.tmp"
    temp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp, target)
    return target
