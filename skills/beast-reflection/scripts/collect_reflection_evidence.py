#!/usr/bin/env python3
"""Build a compact, private evidence bundle from recent Codex sessions and a repo."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "beast.reflection.evidence/v1"
COLLECTOR_VERSION = 2
TEXT_EVENT_TYPES = {"user_message": "user", "agent_message": "assistant"}
ARTIFACT_EXTENSIONS = {".md", ".json", ".jsonl", ".toml", ".yaml", ".yml"}
ARTIFACT_ROOTS = ("proofs", "watched", "docs")
MAX_HASH_BYTES = 10 * 1024 * 1024

SECRET_PATTERNS = (
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"), "Bearer [REDACTED]"),
    (re.compile(r"\b(?:sk|rk|pk)-(?:proj-)?[A-Za-z0-9_-]{12,}\b"), "[REDACTED_API_TOKEN]"),
    (re.compile(r"\bgh[opusr]_[A-Za-z0-9]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (
        re.compile(
            r"(?i)(\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)\b\s*[:=]\s*)([^\s,;]+)"
        ),
        r"\1[REDACTED]",
    ),
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def redact(text: str) -> tuple[str, int]:
    count = 0
    for pattern, replacement in SECRET_PATTERNS:
        text, substitutions = pattern.subn(replacement, text)
        count += substitutions
    return text, count


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured) if configured else Path.home() / ".codex"


def normalize_path(value: str | Path) -> str:
    """Return a comparison-safe absolute path without requiring it to exist."""
    return os.path.normcase(str(Path(value).expanduser().resolve(strict=False))).rstrip("\\/")


def path_is_within(candidate: str | Path, root: str | Path) -> bool:
    try:
        return os.path.commonpath((normalize_path(candidate), normalize_path(root))) == normalize_path(root)
    except (OSError, ValueError):
        return False


def extract_workspace_roots(value: Any) -> list[str]:
    roots: list[str] = []
    if isinstance(value, str) and value.strip():
        return [value]
    if not isinstance(value, list):
        return roots
    for item in value:
        candidate: Any = item
        if isinstance(item, dict):
            candidate = item.get("path") or item.get("root") or item.get("cwd")
        if isinstance(candidate, str) and candidate.strip():
            roots.append(candidate)
    return roots


class SessionScope:
    def __init__(
        self,
        mode: str,
        allowed_roots: Iterable[Path] = (),
        included_session_ids: Iterable[str] = (),
    ) -> None:
        if mode not in {"repo", "global"}:
            raise ValueError(f"Unsupported reflection scope: {mode}")
        self.mode = mode
        self.allowed_roots = sorted({normalize_path(path) for path in allowed_roots})
        self.included_session_ids = sorted(
            {session_id.strip() for session_id in included_session_ids if session_id.strip()}
        )
        if mode == "repo" and not self.allowed_roots:
            raise ValueError("Repository scope requires at least one allowed root")

    def includes(
        self,
        cwd: str | None,
        workspace_roots: Iterable[str],
        session_id: str | None = None,
    ) -> bool:
        if self.mode == "global":
            return True
        if session_id and session_id in self.included_session_ids:
            return True
        candidates = ([cwd] if cwd else []) + list(workspace_roots)
        return any(
            path_is_within(candidate, allowed)
            for candidate in candidates
            for allowed in self.allowed_roots
        )

    def manifest(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "allowed_roots": self.allowed_roots,
            "included_session_ids": self.included_session_ids,
        }


def session_files(root: Path, cutoff: datetime) -> Iterable[Path]:
    if not root.exists():
        return []
    cutoff_epoch = cutoff.timestamp()
    return sorted(
        (path for path in root.rglob("*.jsonl") if path.stat().st_mtime >= cutoff_epoch),
        key=lambda path: str(path).lower(),
    )


def collect_sessions(
    root: Path,
    cutoff: datetime,
    max_chars: int,
    max_events: int,
    scope: SessionScope | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    scope = scope or SessionScope("global")
    events: list[dict[str, Any]] = []
    sessions: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    stats = {
        "files_considered": 0,
        "lines_read": 0,
        "parse_errors": 0,
        "events_excluded": 0,
        "duplicates_removed": 0,
        "messages_truncated": 0,
        "redactions": 0,
        "limit_reached": 0,
        "messages_out_of_scope": 0,
        "sessions_in_scope": 0,
        "sessions_out_of_scope": 0,
    }

    for path in session_files(root, cutoff):
        stats["files_considered"] += 1
        session_id = path.stem
        cwd: str | None = None
        workspace_roots: list[str] = []
        observed_cwds: set[str] = set()
        session_in_scope = scope.mode == "global"
        kept = 0
        relative = path.relative_to(root).as_posix()

        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, raw_line in enumerate(handle, 1):
                stats["lines_read"] += 1
                try:
                    item = json.loads(raw_line)
                except (json.JSONDecodeError, TypeError):
                    stats["parse_errors"] += 1
                    continue

                payload = item.get("payload") or {}
                if item.get("type") == "session_meta":
                    session_id = str(payload.get("id") or payload.get("session_id") or session_id)
                    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else cwd
                    if cwd:
                        observed_cwds.add(cwd)
                    workspace_roots = extract_workspace_roots(payload.get("workspace_roots"))
                    session_in_scope = session_in_scope or scope.includes(
                        cwd, workspace_roots, session_id
                    )
                    continue

                if item.get("type") == "turn_context":
                    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else cwd
                    if cwd:
                        observed_cwds.add(cwd)
                    roots = extract_workspace_roots(payload.get("workspace_roots"))
                    if roots:
                        workspace_roots = roots
                    session_in_scope = session_in_scope or scope.includes(
                        cwd, workspace_roots, session_id
                    )
                    continue

                if item.get("type") != "event_msg":
                    continue
                payload_type = payload.get("type")
                role = TEXT_EVENT_TYPES.get(payload_type)
                if role is None:
                    stats["events_excluded"] += 1
                    continue

                timestamp = parse_timestamp(item.get("timestamp"))
                if timestamp is None or timestamp < cutoff:
                    stats["events_excluded"] += 1
                    continue

                if not scope.includes(cwd, workspace_roots, session_id):
                    stats["messages_out_of_scope"] += 1
                    continue

                message = payload.get("message")
                if not isinstance(message, str) or not message.strip():
                    stats["events_excluded"] += 1
                    continue
                stripped = message.lstrip()
                if stripped.startswith("<environment_context>"):
                    stats["events_excluded"] += 1
                    continue

                sanitized, redactions = redact(message.strip())
                stats["redactions"] += redactions
                original_chars = len(sanitized)
                truncated = original_chars > max_chars
                if truncated:
                    sanitized = sanitized[:max_chars] + "\n[TRUNCATED]"
                    stats["messages_truncated"] += 1

                digest = sha256_text(sanitized)
                dedup_key = (session_id, role, digest)
                if dedup_key in seen:
                    stats["duplicates_removed"] += 1
                    continue
                seen.add(dedup_key)

                events.append(
                    {
                        "timestamp": timestamp.isoformat(),
                        "session_id": session_id,
                        "source": relative,
                        "line": line_number,
                        "role": role,
                        "text": sanitized,
                        "sha256": digest,
                        "original_chars": original_chars,
                        "truncated": truncated,
                        "image_count": len(payload.get("images") or []) if role == "user" else 0,
                        "context_cwd": cwd,
                        "context_workspace_roots": workspace_roots,
                    }
                )
                kept += 1
                if len(events) >= max_events:
                    stats["limit_reached"] = 1
                    break

        if session_in_scope or kept:
            stats["sessions_in_scope"] += 1
            sessions.append(
                {
                    "session_id": session_id,
                    "source": relative,
                    "cwd": cwd,
                    "observed_cwds": sorted(observed_cwds),
                    "workspace_roots": workspace_roots,
                    "messages_kept": kept,
                    "size_bytes": path.stat().st_size,
                    "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                }
            )
        else:
            stats["sessions_out_of_scope"] += 1
        if stats["limit_reached"]:
            break

    events.sort(key=lambda event: (event["timestamp"], event["source"], event["line"]))
    return sessions, events, stats


def run_git(repo: Path, arguments: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 127, ""
    return completed.returncode, completed.stdout.strip()


def repository_worktree_roots(repo: Path) -> list[Path]:
    code, output = run_git(repo, ["worktree", "list", "--porcelain"])
    roots: list[Path] = [repo]
    if code == 0:
        for line in output.splitlines():
            if line.startswith("worktree "):
                roots.append(Path(line.removeprefix("worktree ")))
    unique = {normalize_path(root): Path(root) for root in roots}
    return [unique[key] for key in sorted(unique)]


def build_session_scope(
    repo: Path, mode: str, included_session_ids: Iterable[str] = ()
) -> SessionScope:
    roots = repository_worktree_roots(repo) if mode == "repo" else []
    return SessionScope(mode, roots, included_session_ids)


def collect_repo(repo: Path, cutoff: datetime) -> dict[str, Any]:
    status_code, status = run_git(repo, ["status", "--short"])
    log_code, log = run_git(
        repo,
        ["log", f"--since={cutoff.isoformat()}", "--format=%H%x09%cI%x09%s"],
    )
    head_code, head = run_git(repo, ["rev-parse", "HEAD"])
    commits = []
    if log_code == 0:
        for line in log.splitlines():
            parts = line.split("\t", 2)
            if len(parts) == 3:
                commits.append({"commit": parts[0], "timestamp": parts[1], "subject": parts[2]})

    artifacts: list[dict[str, Any]] = []
    cutoff_epoch = cutoff.timestamp()
    for root_name in ARTIFACT_ROOTS:
        artifact_root = repo / root_name
        if not artifact_root.exists():
            continue
        for path in artifact_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in ARTIFACT_EXTENSIONS:
                continue
            stat = path.stat()
            if stat.st_mtime < cutoff_epoch:
                continue
            digest = None
            if stat.st_size <= MAX_HASH_BYTES:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            artifacts.append(
                {
                    "path": path.relative_to(repo).as_posix(),
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    "sha256": digest,
                }
            )
    artifacts.sort(key=lambda artifact: artifact["path"])

    return {
        "root": str(repo.resolve()),
        "head": head if head_code == 0 else None,
        "is_git_repo": status_code == 0,
        "worktree_status": status.splitlines() if status_code == 0 else [],
        "commits": commits,
        "recent_artifacts": artifacts,
    }


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--sessions-root", type=Path, default=default_codex_home() / "sessions")
    parser.add_argument(
        "--scope",
        choices=("repo", "global"),
        default="repo",
        help="repo keeps only this Git repository and its worktrees; global is explicit user-wide reflection",
    )
    parser.add_argument(
        "--include-session",
        action="append",
        default=[],
        metavar="SESSION_ID",
        help="audited manual override for a known repo thread rooted above the repo; repeatable",
    )
    parser.add_argument("--since-hours", type=float, default=24.0)
    parser.add_argument("--max-message-chars", type=int, default=12_000)
    parser.add_argument("--max-events", type=int, default=5_000)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.since_hours <= 0 or args.max_message_chars <= 0 or args.max_events <= 0:
        raise SystemExit("since-hours, max-message-chars, and max-events must be positive")

    generated_at = utc_now()
    cutoff = generated_at - timedelta(hours=args.since_hours)
    repo = args.repo.resolve()
    scope = build_session_scope(repo, args.scope, args.include_session)
    output = args.output
    if output is None:
        stamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
        output = repo / ".beast" / "reflection" / f"evidence-{stamp}.json"
    elif not output.is_absolute():
        output = repo / output

    sessions, events, stats = collect_sessions(
        args.sessions_root.resolve(),
        cutoff,
        args.max_message_chars,
        args.max_events,
        scope,
    )
    repository = collect_repo(repo, cutoff)
    completed_at = utc_now()
    newest_event_at = events[-1]["timestamp"] if events else None
    newest_event_age_seconds = None
    if newest_event_at:
        newest_timestamp = parse_timestamp(newest_event_at)
        if newest_timestamp:
            newest_event_age_seconds = max(0.0, (completed_at - newest_timestamp).total_seconds())
    receipt_seed = "|".join(
        (
            completed_at.isoformat(),
            args.scope,
            str(repository.get("head") or "no-head"),
            str(len(events)),
        )
    )
    run_receipt = {
        "status": "completed",
        "receipt_id": sha256_text(receipt_seed)[:20],
        "collector_version": COLLECTOR_VERSION,
        "started_at": generated_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": round((completed_at - generated_at).total_seconds(), 6),
        "scope": scope.manifest(),
        "repository_head": repository.get("head"),
        "source_activity": "recent" if events else "none-in-window",
        "newest_retained_event_at": newest_event_at,
        "newest_event_age_seconds": newest_event_age_seconds,
    }
    bundle = {
        "schema": SCHEMA,
        "generated_at": generated_at.isoformat(),
        "cutoff": cutoff.isoformat(),
        "policy": {
            "private_working_evidence": True,
            "raw_tool_outputs_included": False,
            "reasoning_included": False,
            "automatic_authority_file_edits_allowed": False,
        },
        "collection": stats,
        "run_receipt": run_receipt,
        "sessions": sessions,
        "events": events,
        "repository": repository,
    }
    fingerprint_material = json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    bundle["bundle_fingerprint_sha256"] = sha256_text(fingerprint_material)
    write_json_atomic(output, bundle)
    print(f"evidence: {output.resolve()}")
    print(
        f"scope: {args.scope} | sessions: {len(sessions)} | messages: {len(events)} | "
        f"out-of-scope: {stats['messages_out_of_scope']} | redactions: {stats['redactions']}"
    )
    print(f"freshness receipt: {run_receipt['receipt_id']} | {run_receipt['status']}")
    if stats["limit_reached"]:
        print("warning: max-events reached; narrow the time window or raise the explicit limit", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
