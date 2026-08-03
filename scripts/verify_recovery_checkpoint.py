"""Verify a Beast recovery checkpoint before resuming work."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(checkpoint_path: Path, *, allow_head_drift: bool = False) -> dict:
    checkpoint_path = checkpoint_path.resolve()
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    if payload.get("schema") not in {1, "beast.recovery/v2"}:
        raise ValueError(f"unsupported recovery schema: {payload.get('schema')!r}")
    repo = Path(payload["repo"]).resolve()
    head_now = git(repo, "rev-parse", "HEAD")
    head_matches = head_now == payload["git"]["head"]
    evidence = []
    for item in payload.get("evidence", []):
        path = Path(item["path"])
        exists = path.is_file()
        digest = sha256(path) if exists else ""
        evidence.append({
            "path": str(path), "exists": exists,
            "hash_matches": exists and digest == item["sha256"],
            "expected_sha256": item["sha256"], "actual_sha256": digest,
        })
    evidence_ok = all(item["exists"] and item["hash_matches"] for item in evidence)
    result = {
        "schema": "beast.recovery-verification/v1",
        "checkpoint": str(checkpoint_path),
        "repo": str(repo),
        "recorded_head": payload["git"]["head"],
        "current_head": head_now,
        "head_matches": head_matches,
        "head_drift_allowed": allow_head_drift,
        "current_status_porcelain": git(repo, "status", "--short").splitlines(),
        "loop": payload.get("loop", {}),
        "evidence": evidence,
        "evidence_ok": evidence_ok,
    }
    result["ok"] = evidence_ok and (head_matches or allow_head_drift)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--allow-head-drift", action="store_true")
    args = parser.parse_args()
    try:
        result = verify(args.checkpoint, allow_head_drift=args.allow_head_drift)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
