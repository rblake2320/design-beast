"""Conservative temporal evidence bridge for Beast Watch timelines.

This module deliberately does NOT infer clicks, keystrokes or causality from
screenshots. It creates bounded observation pairs for an independent semantic
observer, preserving source identity and fail-closed evidence requirements.
No external dependencies or model calls.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class EvidenceError(ValueError):
    """An observation cannot be grounded in retained source evidence."""


@dataclass(frozen=True)
class Observation:
    frame_id: str
    source_ms: int
    sha256: str
    path: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_observations(bundle: str | Path) -> list[Observation]:
    """Read a Watch bundle, checking evidence bytes before constructing pairs.

    Requires ingestion-time SHA-256. Older bundles lacking hashes must be
    explicitly migrated or reinspected, never silently trusted.
    """
    root = Path(bundle).resolve()
    timeline = json.loads((root / "timeline.json").read_text(encoding="utf-8"))
    if not str(timeline.get("schema", "")).startswith("beast.watch.timeline/v3"):
        raise EvidenceError("Watch timeline v3 with ingestion hashes required")
    frames = timeline.get("frames")
    if not isinstance(frames, list) or not frames:
        raise EvidenceError("No evidence frames")
    result: list[Observation] = []
    seen: set[str] = set()
    for row in frames:
        if not isinstance(row, dict):
            raise EvidenceError("Invalid frame record")
        frame_id = row.get("id") or row.get("frame_id")
        rel = row.get("file") or row.get("path")
        seconds = row.get("source_seconds")
        source_ms = round(seconds * 1000) if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) else None
        expected = row.get("sha256")
        if not isinstance(frame_id, str) or not frame_id or frame_id in seen:
            raise EvidenceError("Missing or duplicate frame ID")
        if not isinstance(rel, str) or not rel:
            raise EvidenceError("Missing evidence path")
        if not isinstance(source_ms, int) or source_ms < 0:
            raise EvidenceError("Invalid source timestamp")
        if not isinstance(expected, str) or len(expected) != 64:
            raise EvidenceError("Missing ingestion SHA-256")
        path = (root / rel).resolve()
        if not path.is_relative_to(root) or path.is_symlink() or not path.is_file():
            raise EvidenceError("Evidence path escape, symlink or missing file")
        if _sha256(path) != expected.lower():
            raise EvidenceError("Evidence bytes do not match ingestion hash")
        result.append(Observation(frame_id, source_ms, expected.lower(), rel))
        seen.add(frame_id)
    result.sort(key=lambda row: (row.source_ms, row.frame_id))
    return result


def plan_pairs(observations: list[Observation], max_gap_ms: int = 3000) -> list[dict[str, Any]]:
    """Propose adjacent state comparisons, never unobserved user actions."""
    if max_gap_ms <= 0:
        raise ValueError("max_gap_ms must be positive")
    pairs: list[dict[str, Any]] = []
    for before, after in zip(observations, observations[1:]):
        gap = after.source_ms - before.source_ms
        if gap == 0:
            continue
        pairs.append({
            "schema": "beast.watch.temporal-pair/v1",
            "before": {"frame_id": before.frame_id, "source_ms": before.source_ms, "sha256": before.sha256},
            "after": {"frame_id": after.frame_id, "source_ms": after.source_ms, "sha256": after.sha256},
            "gap_ms": gap,
            "status": "needs_reinspection" if gap > max_gap_ms else "unverified_observation",
            "permitted_claim": "visual_state_difference_only",
            "forbidden_claims": ["click", "keypress", "typed_text", "causality", "successful_execution"],
        })
    return pairs


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Create hash-grounded Watch temporal comparison requests")
    parser.add_argument("bundle", help="Existing Watch v3 bundle directory")
    parser.add_argument("--max-gap-ms", type=int, default=3000)
    parser.add_argument("--output", help="Optional new JSON output path; never overwrite")
    args = parser.parse_args()
    try:
        rows = plan_pairs(load_observations(args.bundle), args.max_gap_ms)
        data = json.dumps({"schema": "beast.watch.temporal-review/v1", "pairs": rows}, indent=2) + "\n"
        if args.output:
            with open(args.output, "x", encoding="utf-8") as f:
                f.write(data)
        else:
            print(data, end="")
        return 0
    except (EvidenceError, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Temporal bridge rejected input: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
