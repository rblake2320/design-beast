"""Join retained pixel, UI-region and temporal features; recommend, never adjudicate."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.inspection import Confidence, InspectionContext, Interval
from watch.inspection_runtime import retain
from watch.pixel_policy import PixelInspectionPolicy
from watch.visual_state import VisualState


def validate_regions(regions: object, width: int, height: int) -> None:
    if not isinstance(regions, list) or len(regions) > 300:
        raise ValueError("invalid UI region count")
    for region in regions:
        if not isinstance(region, dict) or set(region) != {"bbox_xyxy", "raw_score"}:
            raise ValueError("invalid UI region schema")
        box, score = region["bbox_xyxy"], region["raw_score"]
        if not isinstance(box, list) or len(box) != 4:
            raise ValueError("invalid UI region box")
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in [*box, score]):
            raise ValueError("nonfinite UI region")
        if not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height and 0 <= score <= 1):
            raise ValueError("UI region outside source or score bounds")


def read_record(path: Path) -> tuple[dict[str, object], str]:
    data = path.read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def fuse(pixels: Path, ui: Path, temporal: Path, output: Path) -> None:
    report, report_hash = read_record(pixels / "report.json")
    ui_report, ui_hash = read_record(ui / "report.json")
    temporal_report, temporal_hash = read_record(temporal / "report.json")
    rows = report["frames"]
    if len(rows) != 61 or len(ui_report["frames"]) != 61 or len(temporal_report["windows"]) != 7:
        raise ValueError("incomplete component run")
    output.mkdir(parents=True, exist_ok=False)
    retain(output / "intent.json", {"pixel_report_sha256": report_hash, "ui_report_sha256": ui_hash,
                                    "temporal_report_sha256": temporal_hash})
    known = {row["clip_ms"]: row["sha256"] for row in rows}
    if len(known) != 61:
        raise ValueError("duplicate pixel timestamp")
    try:
        windows = []
        previous_vector = None
        for i in range(7):
            value, sha = read_record(temporal / f"window-{i:02d}.json")
            if len(value["frames"]) != 16 or any(known.get(ref["clip_ms"]) != ref["sha256"] for ref in value["frames"]):
                raise ValueError("temporal window has foreign frames")
            stamps = [ref["clip_ms"] for ref in value["frames"]]
            if any(b <= a for a, b in zip(stamps, stamps[1:])):
                raise ValueError("temporal frames not chronological")
            vector = value["embedding"]
            if len(vector) != 1024 or any(type(v) not in (int, float) or not math.isfinite(v) for v in vector):
                raise ValueError("invalid temporal features")
            if not .99 <= sum(v*v for v in vector) <= 1.01:
                raise ValueError("temporal features not normalized")
            distance = value["distance_from_previous"]
            if previous_vector is None:
                if distance is not None:
                    raise ValueError("first temporal distance must be absent")
            else:
                expected_distance = 1-sum(a*b for a, b in zip(previous_vector, vector))
                if type(distance) not in (int, float) or not math.isfinite(distance) or abs(distance-expected_distance) > 1e-5:
                    raise ValueError("temporal distance disagrees with retained features")
            previous_vector = vector
            windows.append({"window": i, "sha256": sha, "start_ms": value["frames"][0]["clip_ms"],
                            "end_ms": value["frames"][-1]["clip_ms"], "distance": value["distance_from_previous"]})
        for i, row in enumerate(rows):
            value, sha = read_record(pixels / f"frame-{i:03d}" / "state.json")
            if sha != row["state_sha256"]:
                raise ValueError("pixel state receipt changed")
            state = VisualState.model_validate_json(json.dumps(value))
            if state.frame_sha256 != row["sha256"] or state.clip_ms != row["clip_ms"]:
                raise ValueError("pixel report does not match actual state frame")
            regions, region_sha = read_record(ui / f"frame-{i:03d}.json")
            if regions["sha256"] != state.frame_sha256 or regions["clip_ms"] != state.clip_ms:
                raise ValueError("UI regions refer to foreign pixels")
            validate_regions(regions["regions"], *state.dimensions)
            interval = Interval(start_ms=rows[max(0, i-1)]["clip_ms"], end_ms=state.clip_ms)
            context = InspectionContext(source_interval=Interval(start_ms=rows[0]["clip_ms"], end_ms=rows[-1]["clip_ms"]),
                candidate_interval=interval, confidence=Confidence(perception=0.0, transition=0.0, procedure=0.0))
            covering = [w for w in windows if w["start_ms"] <= state.clip_ms <= w["end_ms"]]
            temporal_change = max((w["distance"] for w in covering if w["distance"] is not None), default=0.0)
            decision = PixelInspectionPolicy(state, ui_region_count=len(regions["regions"]),
                                             temporal_change_score=temporal_change).decide(context)
            retain(output / f"frame-{i:03d}.json", {"clip_ms": state.clip_ms, "frame_sha256": state.frame_sha256,
                "pixel_state_sha256": sha, "ui_regions_sha256": region_sha, "ui_regions": regions["regions"],
                "temporal_windows": covering,
                "inspection_recommendation": decision.model_dump(mode="json"),
                "confidence_status": "zero policy inputs mean not established; not calibrated probabilities",
                "evidence_class": "unverified_multichannel_visual_state"})
        retain(output / "report.json", {"frames": 61, "temporal_windows": 7, "inspection_executions": 0,
                                         "semantic_acceptances": 0, "procedure_promotions": 0})
    except Exception as exc:
        retain(output / "failure.json", {"error": str(exc), "type": type(exc).__name__})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pixels", "ui", "temporal", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    args = parser.parse_args()
    fuse(args.pixels, args.ui, args.temporal, args.output)


if __name__ == "__main__":
    main()
