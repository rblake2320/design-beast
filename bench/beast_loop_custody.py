"""Seal Beast-loop experiments and retain an append-only result chain.

This module does not execute an agent. It prevents the surrounding experiment
from quietly changing after implementation freeze, task selection, or failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ZERO_HASH = "0" * 64
CONDITIONS = ("baseline", "adaptive_frames", "beast")


class CustodyError(ValueError):
    """Raised when an experiment's chain of custody is invalid."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise CustodyError(result.stderr.strip() or result.stdout.strip() or "git command failed")
    return result.stdout.strip()


def _repo_relative(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError as exc:
        raise CustodyError(f"implementation file is outside repository: {path}") from exc


def _file_receipt(path: Path, *, label: str | None = None) -> dict:
    if not path.is_file():
        raise CustodyError(f"required file does not exist: {path}")
    return {
        "name": label or path.name,
        "bytes": path.stat().st_size,
        "sha256": digest_file(path),
    }


def _reject_placeholders(value: Any, location: str = "envelope") -> None:
    if value is None or (isinstance(value, str) and value.strip().lower() in {"", "tbd", "todo", "unknown"}):
        raise CustodyError(f"{location} contains an unresolved value")
    if isinstance(value, dict):
        if not value:
            raise CustodyError(f"{location} cannot be empty")
        for key, child in value.items():
            _reject_placeholders(child, f"{location}.{key}")
    elif isinstance(value, list):
        if not value:
            raise CustodyError(f"{location} cannot be empty")
        for index, child in enumerate(value):
            _reject_placeholders(child, f"{location}[{index}]")


def create_freeze(repo: Path, envelope_path: Path, include: list[Path]) -> dict:
    repo = repo.resolve()
    status = _git(repo, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise CustodyError("implementation freeze requires a clean worktree")
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    _reject_placeholders(envelope)
    records = []
    seen = set()
    for candidate in include:
        absolute = candidate if candidate.is_absolute() else repo / candidate
        relative = _repo_relative(repo, absolute)
        if relative in seen:
            raise CustodyError(f"duplicate implementation file: {relative}")
        seen.add(relative)
        receipt = _file_receipt(absolute, label=relative)
        receipt["path"] = receipt.pop("name")
        records.append(receipt)
    payload = {
        "schema": "beast.loop-freeze/v1",
        "created_utc": utc_now(),
        "frozen_commit": _git(repo, "rev-parse", "HEAD"),
        "envelope": envelope,
        "envelope_fingerprint": digest_value(envelope),
        "implementation": sorted(records, key=lambda item: item["path"]),
        "worktree_clean_at_freeze": True,
    }
    payload["freeze_fingerprint"] = digest_value(payload)
    return payload


def verify_freeze(repo: Path, freeze: dict) -> list[str]:
    errors = []
    claimed = freeze.get("freeze_fingerprint", "")
    unsigned = {key: value for key, value in freeze.items() if key != "freeze_fingerprint"}
    if claimed != digest_value(unsigned):
        errors.append("freeze fingerprint mismatch")
    frozen_commit = str(freeze.get("frozen_commit", ""))
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", frozen_commit, "HEAD"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        errors.append("current HEAD does not descend from frozen commit")
    for receipt in freeze.get("implementation", []):
        path = repo / receipt.get("path", "")
        if not path.is_file():
            errors.append(f"missing frozen implementation file: {receipt.get('path', '')}")
        elif digest_file(path) != receipt.get("sha256"):
            errors.append(f"frozen implementation changed: {receipt.get('path', '')}")
    return errors


def create_seal(repo: Path, freeze: dict, registry_path: Path, protocol: dict, seed: str | None = None) -> dict:
    freeze_errors = verify_freeze(repo, freeze)
    if freeze_errors:
        raise CustodyError("; ".join(freeze_errors))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if registry.get("schema") != "beast.loop-task-registry/v1":
        raise CustodyError("unsupported task registry schema")
    if registry.get("freeze_fingerprint") != freeze.get("freeze_fingerprint"):
        raise CustodyError("task registry does not reference this implementation freeze")
    if registry.get("selection_role") != "independent_reviewer" or not str(registry.get("selected_by", "")).strip():
        raise CustodyError("tasks must be selected by a named independent reviewer")

    tasks = []
    task_ids = set()
    domain_counts: dict[str, int] = {}
    for task in registry.get("tasks", []):
        task_id = str(task.get("task_id", "")).strip()
        domain = str(task.get("domain", "")).strip()
        if not task_id or not domain or task_id in task_ids:
            raise CustodyError(f"invalid or duplicate task identity: {task_id!r}")
        task_ids.add(task_id)
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        if task.get("selected_after_freeze") is not True:
            raise CustodyError(f"{task_id}: selection-after-freeze was not attested")
        source = Path(task.get("source_path", ""))
        oracle = Path(task.get("oracle_path", ""))
        receipt = Path(task.get("selection_receipt_path", ""))
        tasks.append({
            "task_id": task_id,
            "domain": domain,
            "source": _file_receipt(source, label=source.name),
            "oracle": _file_receipt(oracle, label=str(task.get("oracle_id") or oracle.name)),
            "selection_receipt": _file_receipt(receipt, label=receipt.name),
            "visual_only_fact_count": int(task.get("visual_only_fact_count", 0)),
            "ambiguous_segment_count": int(task.get("ambiguous_segment_count", 0)),
        })
        if tasks[-1]["visual_only_fact_count"] < 1 or tasks[-1]["ambiguous_segment_count"] < 1:
            raise CustodyError(f"{task_id}: visual-only and ambiguous evidence must be predeclared")

    minimum_domains = int(protocol["minimum_domains"])
    minimum_tasks = int(protocol["minimum_tasks_per_domain"])
    repetitions = int(protocol["minimum_repetitions_per_condition"])
    if len(domain_counts) < minimum_domains:
        raise CustodyError(f"task registry has fewer than {minimum_domains} domains")
    for domain, count in domain_counts.items():
        if count < minimum_tasks:
            raise CustodyError(f"{domain}: fewer than {minimum_tasks} tasks")

    schedule = []
    for task in tasks:
        for condition in CONDITIONS:
            for repetition in range(1, repetitions + 1):
                schedule.append({
                    "task_id": task["task_id"],
                    "domain": task["domain"],
                    "condition": condition,
                    "repetition": repetition,
                })
    schedule_seed = seed or secrets.token_hex(32)
    random.Random(schedule_seed).shuffle(schedule)
    for index, item in enumerate(schedule, start=1):
        item["run_index"] = index

    payload = {
        "schema": "beast.loop-experiment-seal/v1",
        "experiment_id": registry.get("experiment_id"),
        "created_utc": utc_now(),
        "freeze_fingerprint": freeze["freeze_fingerprint"],
        "frozen_commit": freeze["frozen_commit"],
        "envelope_fingerprint": freeze["envelope_fingerprint"],
        "task_registry_sha256": digest_file(registry_path),
        "selected_by": registry["selected_by"],
        "selection_role": registry["selection_role"],
        "tasks": sorted(tasks, key=lambda item: item["task_id"]),
        "schedule_seed": schedule_seed,
        "schedule": schedule,
        "expected_runs": len(schedule),
        "claim_boundary": "The seal proves custody and balance, not task success. Oracle contents remain sequestered from executor contexts; only their hashes appear here.",
    }
    payload["seal_fingerprint"] = digest_value(payload)
    return payload


def verify_seal(seal: dict) -> list[str]:
    errors = []
    claimed = seal.get("seal_fingerprint", "")
    unsigned = {key: value for key, value in seal.items() if key != "seal_fingerprint"}
    if claimed != digest_value(unsigned):
        errors.append("seal fingerprint mismatch")
    schedule = seal.get("schedule", [])
    if seal.get("expected_runs") != len(schedule):
        errors.append("expected run count does not match schedule")
    identities = set()
    indexes = []
    for item in schedule:
        identity = (item.get("task_id"), item.get("condition"), item.get("repetition"))
        if identity in identities:
            errors.append(f"duplicate scheduled run: {identity}")
        identities.add(identity)
        indexes.append(item.get("run_index"))
    if indexes != list(range(1, len(schedule) + 1)):
        errors.append("schedule run indexes are not contiguous")
    return errors


def _read_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise CustodyError(f"invalid result JSON at line {line_number}") from exc
    return records


def verify_result_chain(seal: dict, records: list[dict], artifact_root: Path | None = None, *, require_complete: bool = False) -> list[str]:
    errors = verify_seal(seal)
    schedule = seal.get("schedule", [])
    previous = ZERO_HASH
    if len(records) > len(schedule):
        errors.append("result chain contains more rows than the sealed schedule")
    for index, record in enumerate(records):
        expected = schedule[index] if index < len(schedule) else {}
        identity_fields = ("run_index", "task_id", "domain", "condition", "repetition")
        for field in identity_fields:
            if record.get(field) != expected.get(field):
                errors.append(f"result {index + 1}: {field} does not match sealed schedule")
        if record.get("seal_fingerprint") != seal.get("seal_fingerprint"):
            errors.append(f"result {index + 1}: seal fingerprint mismatch")
        if record.get("envelope_fingerprint") != seal.get("envelope_fingerprint"):
            errors.append(f"result {index + 1}: envelope fingerprint mismatch")
        if record.get("previous_record_sha256") != previous:
            errors.append(f"result {index + 1}: previous-record hash mismatch")
        unsigned = {key: value for key, value in record.items() if key != "record_sha256"}
        calculated = digest_value(unsigned)
        if record.get("record_sha256") != calculated:
            errors.append(f"result {index + 1}: record hash mismatch")
        previous = record.get("record_sha256", "")
        artifacts = record.get("artifacts", [])
        if not artifacts:
            errors.append(f"result {index + 1}: no artifact receipts")
        if artifact_root is not None:
            root = artifact_root.resolve()
            for artifact in artifacts:
                candidate = (root / artifact.get("path", "")).resolve()
                try:
                    candidate.relative_to(root)
                except ValueError:
                    errors.append(f"result {index + 1}: artifact escapes root")
                    continue
                if not candidate.is_file():
                    errors.append(f"result {index + 1}: missing artifact {artifact.get('path', '')}")
                elif digest_file(candidate) != artifact.get("sha256"):
                    errors.append(f"result {index + 1}: artifact hash mismatch {artifact.get('path', '')}")
    if require_complete and len(records) != len(schedule):
        errors.append(f"incomplete result chain: {len(records)} of {len(schedule)} runs")
    return errors


def append_result(seal: dict, results_path: Path, row_path: Path, artifact_root: Path) -> dict:
    records = _read_records(results_path)
    existing_errors = verify_result_chain(seal, records, artifact_root)
    if existing_errors:
        raise CustodyError("; ".join(existing_errors))
    if len(records) >= len(seal["schedule"]):
        raise CustodyError("sealed schedule is already complete")
    row = json.loads(row_path.read_text(encoding="utf-8"))
    expected = seal["schedule"][len(records)]
    for field in ("run_index", "task_id", "domain", "condition", "repetition"):
        if row.get(field) != expected[field]:
            raise CustodyError(f"new result field {field} does not match sealed schedule")
    row["seal_fingerprint"] = seal["seal_fingerprint"]
    row["envelope_fingerprint"] = seal["envelope_fingerprint"]
    row["previous_record_sha256"] = records[-1]["record_sha256"] if records else ZERO_HASH
    for artifact in row.get("artifacts", []):
        candidate = (artifact_root / artifact.get("path", "")).resolve()
        try:
            candidate.relative_to(artifact_root.resolve())
        except ValueError as exc:
            raise CustodyError("artifact escapes root") from exc
        if not candidate.is_file() or digest_file(candidate) != artifact.get("sha256"):
            raise CustodyError(f"artifact receipt does not resolve: {artifact.get('path', '')}")
    if not row.get("artifacts"):
        raise CustodyError("at least one artifact receipt is required")
    row["record_sha256"] = digest_value(row)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with results_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return row


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    freeze_parser = sub.add_parser("freeze")
    freeze_parser.add_argument("--repo", type=Path, default=Path.cwd())
    freeze_parser.add_argument("--envelope", type=Path, required=True)
    freeze_parser.add_argument("--include", type=Path, action="append", required=True)
    freeze_parser.add_argument("--out", type=Path, required=True)

    verify_freeze_parser = sub.add_parser("verify-freeze")
    verify_freeze_parser.add_argument("freeze", type=Path)
    verify_freeze_parser.add_argument("--repo", type=Path, default=Path.cwd())

    seal_parser = sub.add_parser("seal")
    seal_parser.add_argument("--repo", type=Path, default=Path.cwd())
    seal_parser.add_argument("--freeze", type=Path, required=True)
    seal_parser.add_argument("--registry", type=Path, required=True)
    seal_parser.add_argument("--protocol", type=Path, default=Path(__file__).with_name("beast-loop-protocol.json"))
    seal_parser.add_argument("--seed")
    seal_parser.add_argument("--out", type=Path, required=True)

    verify_results_parser = sub.add_parser("verify-results")
    verify_results_parser.add_argument("--seal", type=Path, required=True)
    verify_results_parser.add_argument("--results", type=Path, required=True)
    verify_results_parser.add_argument("--artifact-root", type=Path)
    verify_results_parser.add_argument("--require-complete", action="store_true")
    verify_results_parser.add_argument("--out-json", type=Path)

    append_parser = sub.add_parser("append-result")
    append_parser.add_argument("--seal", type=Path, required=True)
    append_parser.add_argument("--results", type=Path, required=True)
    append_parser.add_argument("--row", type=Path, required=True)
    append_parser.add_argument("--artifact-root", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "freeze":
            payload = create_freeze(args.repo, args.envelope, args.include)
            _write_json(args.out, payload)
        elif args.command == "verify-freeze":
            payload = json.loads(args.freeze.read_text(encoding="utf-8"))
            errors = verify_freeze(args.repo, payload)
            print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
            return 0 if not errors else 1
        elif args.command == "seal":
            freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
            protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
            payload = create_seal(args.repo, freeze, args.registry, protocol, args.seed)
            _write_json(args.out, payload)
        elif args.command == "append-result":
            seal = json.loads(args.seal.read_text(encoding="utf-8"))
            payload = append_result(seal, args.results, args.row, args.artifact_root)
            print(json.dumps(payload, indent=2, sort_keys=True))
        elif args.command == "verify-results":
            seal = json.loads(args.seal.read_text(encoding="utf-8"))
            records = _read_records(args.results)
            errors = verify_result_chain(
                seal, records, args.artifact_root, require_complete=args.require_complete
            )
            if args.out_json and not errors:
                _write_json(args.out_json, records)
            print(json.dumps({"ok": not errors, "errors": errors, "runs": len(records)}, indent=2))
            return 0 if not errors else 1
    except (CustodyError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
