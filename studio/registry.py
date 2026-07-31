"""Backend registry + resolver — local-first, cloud-parity-with-keys.

The product rule this encodes: local open-source backends are the free
default and always eligible; cloud backends offer the same (or better) power
the moment the operator supplies their own auth (BYOK key env var or a
provider subscription) — and never silently before. Resolution order is a
cascade (after vigil's local→NIM→Ollama pattern): eligible local backends
first, then authenticated cloud, each list preserving registry order.

A backend is skipped for exactly one named reason (policy, missing auth,
wrong kind) — surfaced so a refusal is a routable fact, never a dead end.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).resolve().parent / "model_registry.json"
_auth_cmd_cache: dict[str, bool] = {}


def load(path: Path = REGISTRY_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["backends"]


def _has_auth(backend: dict[str, Any], *, probe_subscriptions: bool = False) -> bool:
    auth = backend.get("auth", "none")
    if auth == "none":
        return True
    if auth == "byok":
        env = backend.get("key_env", "")
        return bool(env and os.environ.get(env))
    if auth == "subscription":
        cmd = backend.get("auth_cmd")
        if not cmd:
            return False
        if not probe_subscriptions:
            # without probing we assume the subscription may be live; the
            # backend call itself is the authoritative check
            return True
        if cmd not in _auth_cmd_cache:
            try:
                _auth_cmd_cache[cmd] = subprocess.run(
                    cmd.split(), capture_output=True, timeout=15).returncode == 0
            except Exception:  # noqa: BLE001
                _auth_cmd_cache[cmd] = False
        return _auth_cmd_cache[cmd]
    return False


def resolve(kind: str, *, content_class: str = "general",
            allow_cloud: bool = True,
            backends: list[dict[str, Any]] | None = None,
            probe_subscriptions: bool = False) -> dict[str, Any]:
    """Return {"eligible": [...], "skipped": [{"id", "reason"}...]}.

    Eligible order: local first (registry order), then authenticated cloud.
    """
    entries = backends if backends is not None else load()
    local: list[dict[str, Any]] = []
    cloud: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for b in entries:
        if b.get("kind") != kind:
            continue
        if content_class not in b.get("content_classes", []):
            skipped.append({"id": b["id"],
                            "reason": f"content class '{content_class}' outside "
                                      f"provider terms"})
            continue
        if b.get("hosting") == "local":
            local.append(b)
            continue
        if not allow_cloud:
            skipped.append({"id": b["id"], "reason": "cloud disabled for this run"})
            continue
        if _has_auth(b, probe_subscriptions=probe_subscriptions):
            cloud.append(b)
        else:
            need = b.get("key_env") or b.get("auth_cmd") or "credentials"
            skipped.append({"id": b["id"], "reason": f"no auth ({need})"})
    return {"eligible": local + cloud, "skipped": skipped}


def capability_map(*, probe_subscriptions: bool = False) -> dict[str, Any]:
    """Full discovery view — feeds GET /api/registry and the future MCP tool."""
    entries = load()
    kinds = sorted({b["kind"] for b in entries})
    return {
        "kinds": kinds,
        "backends": [
            {**b, "available": (b.get("hosting") == "local"
                                or _has_auth(b, probe_subscriptions=probe_subscriptions))}
            for b in entries
        ],
    }
