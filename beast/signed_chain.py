"""Ed25519-signed, hash-chained JSONL evidence receipts."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


GENESIS = "0" * 64


def canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def generate_keypair(private_path: Path, public_path: Path) -> None:
    if private_path.exists() or public_path.exists():
        raise FileExistsError("refusing to overwrite an evidence signing key")
    key = Ed25519PrivateKey.generate()
    private_bytes = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_bytes = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.write_bytes(private_bytes)
    try:
        os.chmod(private_path, 0o600)
    except OSError:
        pass
    public_path.write_bytes(public_bytes)


def _head(path: Path) -> str:
    if not path.exists():
        return GENESIS
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return json.loads(lines[-1])["chain_hash"] if lines else GENESIS


def append(path: Path, private_path: Path, *, event: str, subject: str,
           evidence: list[dict[str, Any]], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("evidence key must be Ed25519")
    public_raw = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    entry: dict[str, Any] = {
        "schema": "beast.signed-evidence/v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "subject": subject,
        "evidence": evidence,
        "metadata": metadata or {},
        "prev": _head(path),
        "signing_key_sha256": hashlib.sha256(public_raw).hexdigest(),
    }
    payload = canonical(entry)
    entry["chain_hash"] = hashlib.sha256(payload).hexdigest()
    entry["signature"] = base64.b64encode(key.sign(payload)).decode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return entry
