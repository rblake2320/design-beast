"""Hash-chained provenance ledger — tamper-evident run history.

Pattern ported from vigil (rblake2320/vigil, core/auto_evidence.py): each JSONL
entry stores `prev` (the previous entry's chain hash) and `chain_hash` =
SHA-256 over the entry serialized WITHOUT chain_hash. Editing, deleting, or
reordering any historical line breaks every hash after it, so the whole
history verifies in one pass — the audit-grade layer per-run manifests
(islands) cannot provide on their own.

Append is best-effort and must never fail the run it describes; verify is
strict and names the first broken line.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

LEDGER_NAME = "provenance_ledger.jsonl"
_GENESIS = "0" * 64
_LOCK = threading.Lock()


def _chain_hash(entry_without_chain: dict[str, Any]) -> str:
    payload = json.dumps(entry_without_chain, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def _head(ledger_path: Path) -> str:
    if not ledger_path.exists():
        return _GENESIS
    head = _GENESIS
    with ledger_path.open("rb") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                head = json.loads(raw).get("chain_hash", head)
            except json.JSONDecodeError:
                continue
    return head


def append(ledger_path: Path, *, run_id: str, kind: str, model: str,
           manifest_sha256: str | None,
           artifacts: list[dict[str, Any]] | None = None,
           outcome: str | None = None) -> dict[str, Any] | None:
    """Append one chained entry. Returns the entry, or None on any failure."""
    try:
        with _LOCK:
            entry = {
                "ts_unix": time.time(),
                "run_id": run_id,
                "kind": kind,
                "model": model,
                "manifest_sha256": manifest_sha256,
                "artifacts": [{"file": a.get("file"), "sha256": a.get("sha256")}
                              for a in (artifacts or [])],
                "outcome": outcome,
                "prev": _head(ledger_path),
            }
            entry["chain_hash"] = _chain_hash(entry)
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with ledger_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry
    except Exception:  # noqa: BLE001 — the ledger never fails the run
        return None


def verify(ledger_path: Path) -> tuple[bool, str]:
    """Walk the chain. Returns (ok, message); message names the first break."""
    if not ledger_path.exists():
        return True, "ledger empty (nothing to verify)"
    expected_prev = _GENESIS
    count = 0
    with ledger_path.open("rb") as f:
        for lineno, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                return False, f"line {lineno}: not valid JSON"
            recorded = entry.pop("chain_hash", None)
            if entry.get("prev") != expected_prev:
                return False, (f"line {lineno} (run {entry.get('run_id')}): "
                               f"prev-link broken — chain edited or reordered")
            if _chain_hash(entry) != recorded:
                return False, (f"line {lineno} (run {entry.get('run_id')}): "
                               f"content hash mismatch — entry modified")
            expected_prev = recorded
            count += 1
    return True, f"chain intact: {count} entries, head {expected_prev[:16]}"


def manifest_sha256(manifest_path: Path) -> str | None:
    try:
        return hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    except Exception:  # noqa: BLE001
        return None
