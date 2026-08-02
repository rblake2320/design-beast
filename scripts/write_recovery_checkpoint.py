"""Write an atomic, secret-free recovery checkpoint for a Beast work session."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def hash_file(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--next-action", action="append", default=[])
    parser.add_argument("--evidence", type=Path, action="append", default=[])
    parser.add_argument("--project", default="")
    parser.add_argument("--engine-root", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--map", dest="map_name", default="")
    args = parser.parse_args()

    repo = args.repo.resolve()
    evidence = []
    for candidate in args.evidence:
        resolved = candidate.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        evidence.append(hash_file(resolved))

    checkpoint = {
        "schema": 1,
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "repo": str(repo),
        "git": {
            "branch": run_git(repo, "branch", "--show-current"),
            "head": run_git(repo, "rev-parse", "HEAD"),
            "status_porcelain": run_git(repo, "status", "--short").splitlines(),
        },
        "goal": args.goal,
        "current": args.current,
        "next_actions": args.next_action,
        "unreal": {
            "project": args.project,
            "engine_root": args.engine_root,
            "run_id": args.run_id,
            "map": args.map_name,
        },
        "evidence": evidence,
        "secrets_stored": False,
    }
    payload = json.dumps(checkpoint, indent=2, sort_keys=True) + "\n"
    atomic_write(args.session_dir / "latest.json", payload)

    lines = [
        "# Recovery Checkpoint",
        "",
        f"- Recorded UTC: `{checkpoint['recorded_utc']}`",
        f"- Repo: `{repo}`",
        f"- Branch: `{checkpoint['git']['branch']}`",
        f"- HEAD: `{checkpoint['git']['head']}`",
        f"- Current: {args.current}",
        "",
        "## Resume",
        "",
    ]
    lines.extend(f"- {action}" for action in args.next_action)
    lines.extend(["", "Read `latest.json` and verify Git status and evidence hashes before acting.", ""])
    atomic_write(args.session_dir / "RECOVER.md", "\n".join(lines))
    print(args.session_dir / "latest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
