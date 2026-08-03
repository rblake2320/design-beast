"""Validate that a Watch procedure contains real visual and reinspection links."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(procedure: dict, timeline: dict) -> dict:
    errors: list[str] = []
    watching = procedure.get("watching_evidence", {})
    frames = {row["id"] for row in timeline.get("frames", [])}
    transcript = " ".join(
        str(row.get("text", "")).casefold()
        for row in timeline.get("transcript", {}).get("segments", [])
    )
    visual_facts = [
        item for item in watching.get("visual_only_facts", [])
        if str(item.get("claim", "")).strip()
    ]
    if not visual_facts:
        errors.append("at least one visual-only fact is required")
    for index, item in enumerate(visual_facts):
        prefix = f"visual_only_facts[{index}]"
        cited = item.get("frame_ids", [])
        if not cited:
            errors.append(f"{prefix}: frame_ids are required")
        for frame_id in cited:
            if frame_id not in frames:
                errors.append(f"{prefix}: unknown frame {frame_id}")
        terms = [
            str(term).casefold().strip()
            for term in item.get("transcript_search_terms", []) if str(term).strip()
        ]
        if not terms:
            errors.append(f"{prefix}: transcript_search_terms are required")
        if item.get("transcript_absence_checked") is not True:
            errors.append(f"{prefix}: transcript_absence_checked must be true")
        matches = [term for term in terms if term in transcript]
        if matches:
            errors.append(f"{prefix}: claimed visual-only terms found in transcript: {matches}")

    requests = timeline.get("evidence_requests", [])
    for index, item in enumerate(watching.get("ambiguous_segments", [])):
        if not str(item.get("description", "")).strip():
            continue
        if item.get("requires_reinspection"):
            request_index = item.get("evidence_request_index")
            if not isinstance(request_index, int) or not (0 <= request_index < len(requests)):
                errors.append(f"ambiguous_segments[{index}]: valid evidence_request_index required")
            if item.get("resolved") is not True:
                errors.append(f"ambiguous_segments[{index}]: reinspection is not resolved")

    return {
        "schema": "beast.watch.watching-gate/v1",
        "ok": not errors,
        "visual_only_fact_count": len(visual_facts),
        "reinspection_count": len(requests),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("procedure", type=Path)
    parser.add_argument("timeline", type=Path)
    args = parser.parse_args()
    result = validate(
        json.loads(args.procedure.read_text(encoding="utf-8")),
        json.loads(args.timeline.read_text(encoding="utf-8")),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
