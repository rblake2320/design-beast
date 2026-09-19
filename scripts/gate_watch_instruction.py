"""Link reviewed instruction units to source frames before exporting a draft plan."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.teachability import InstructionUnit, gate
from watch.training_draft import TrainingDraft
from watch.inspection_runtime import digest, retain


def evaluate(review: Path, units_path: Path, output: Path, *, is_plan: bool = False) -> None:
    review_bytes = (review / "review-data.json").read_bytes()
    review_hash = hashlib.sha256(review_bytes).hexdigest()
    data = json.loads(review_bytes)
    receipt = json.loads((review / "report.json").read_bytes())
    if review_hash != receipt["review_data_sha256"] or digest(review / "media/source.mp4") != data["source_sha256"]:
        raise ValueError("review/source custody changed")
    units_bytes = units_path.read_bytes()
    units_hash = hashlib.sha256(units_bytes).hexdigest()
    payload = json.loads(units_bytes)
    if is_plan:
        plan = TrainingDraft.model_validate_json(json.dumps(payload))
        payload = {"source_sha256": plan.source_sha256, "units": [
            {"unit_id": f"unit-{index:03d}", "kind": "ambiguous_transition", "start_ms": step.start_ms,
             "end_ms": step.end_ms, "sentence": step.caption, "frame_refs": [r.model_dump() for r in step.frame_refs],
             "verdict": "pending"} for index, step in enumerate(plan.steps)]}
    if payload["source_sha256"] != data["source_sha256"]:
        raise ValueError("unit source mismatch")
    units = [InstructionUnit.model_validate_json(json.dumps(row)) for row in payload["units"]]
    if not 1 <= len(units) <= 50 or len({u.unit_id for u in units}) != len(units):
        raise ValueError("invalid unit count or duplicate identity")
    known = {(f["clip_ms"], f["sha256"]) for f in data["frames"]}
    for frame in data["frames"]:
        path = (review / frame["image"]).resolve()
        if not path.is_relative_to(review.resolve()) or digest(path) != frame["sha256"]:
            raise ValueError("review frame custody mismatch")
    for unit in units:
        if unit.end_ms > data["end_ms"] or any((f.clip_ms, f.sha256) not in known for f in unit.frame_refs):
            raise ValueError("unit references foreign/out-of-range evidence")
    output.mkdir(parents=True, exist_ok=False)
    retain(output / "intent.json", {"units_sha256": units_hash, "review_data_sha256": review_hash})
    retain(output / "units.json", payload)
    decisions = [gate(unit) for unit in units]
    eligible = [u for u, d in zip(units, decisions) if d["decision"] == "eligible_draft"]
    if eligible:
        plan = {"schema_version": "beast.watch.training-draft/v1", "source_sha256": data["source_sha256"],
            "source_duration_ms": data["end_ms"], "visual_policy": "original_source_only", "publication_allowed": False,
            "steps": [{"start_ms": u.start_ms, "end_ms": u.end_ms, "caption": u.sentence,
                "frame_refs": [r.model_dump() for r in u.frame_refs], "review_state": "uncertain", "requires_human_approval": True} for u in eligible]}
        TrainingDraft.model_validate_json(json.dumps(plan))
        retain(output / "training-draft.json", plan)
    retain(output / "report.json", {"decisions": decisions, "eligible_units": len(eligible),
        "status": "draft_available" if eligible else "review_required_no_narration", "publication_allowed": False,
        "boundary": "validates declared review and evidence links, not causal truth or reviewer identity"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("review", "output"):
        parser.add_argument("--"+key, type=Path, required=True)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--units", type=Path)
    inputs.add_argument("--plan", type=Path)
    args = parser.parse_args()
    try:
        evaluate(args.review, args.units or args.plan, args.output, is_plan=args.plan is not None)
    except Exception as exc:
        sys.stderr.write(json.dumps({"status": "rejected", "error": str(exc), "type": type(exc).__name__})+"\n")
        raise SystemExit(2)
