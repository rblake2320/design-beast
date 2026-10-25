"""CPU source-linked rewind comparison; no narration, action inference or promotion."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageChops, ImageStat
from watch.inspection import Confidence, DeterministicWatchPolicy, InspectionContext, Interval
from watch.inspection_runtime import digest, execute_inspection, retain
from watch.rewind import EvidenceDebt, ChangeSample, budget_fps, refinement, request, rewind_window
from watch.teachability import InstructionUnit, gate


def changes(bundle: Path, frames: list[dict]) -> tuple[ChangeSample, ...]:
    rows = sorted(frames, key=lambda f: f["source_seconds"])
    result = []
    for before, after in zip(rows, rows[1:]):
        with Image.open(bundle / before["file"]) as a, Image.open(bundle / after["file"]) as b:
            if a.size != b.size:
                raise ValueError("frame dimensions changed")
            difference = ImageStat.Stat(ImageChops.difference(a.convert("RGB"), b.convert("RGB")))
            result.append(ChangeSample(start_ms=round(before["source_seconds"]*1000),
                end_ms=round(after["source_seconds"]*1000), mean_absolute_difference=sum(difference.mean)/3))
    return tuple(result)


def evaluate(review: Path, units: Path, output: Path, *, frames: int = 16,
             lookback_ms: int = 2000, seconds: float = 60.0, ffmpeg: str = "ffmpeg",
             reverse_order: bool = False) -> dict:
    if type(frames) is not int or not 8 <= frames <= 96 or not 1 <= seconds <= 120:
        raise ValueError("invalid frame/time budget")
    data_bytes, unit_bytes = (review / "review-data.json").read_bytes(), units.read_bytes()
    data, payload = json.loads(data_bytes), json.loads(unit_bytes)
    receipt = json.loads((review / "report.json").read_bytes())
    if hashlib.sha256(data_bytes).hexdigest() != receipt["review_data_sha256"]:
        raise ValueError("changed review manifest")
    source = review / "media/source.mp4"
    source_hash = digest(source)
    if source_hash != data["source_sha256"] or source_hash != payload["source_sha256"]:
        raise ValueError("source mismatch")
    if len(payload["units"]) != 1:
        raise ValueError("experiment accepts exactly one reviewed result unit")
    unit = InstructionUnit.model_validate_json(json.dumps(payload["units"][0]))
    if unit.kind != "observable_result" or gate(unit)["decision"] != "eligible_draft":
        raise ValueError("reviewed result-only seed required")
    if unit.end_ms > data["end_ms"]:
        raise ValueError("seed interval outside source")
    known = {(f["clip_ms"], f["sha256"]) for f in data["frames"]}
    for ref in unit.frame_refs:
        if (ref.clip_ms, ref.sha256) not in known:
            raise ValueError("foreign frame reference")
    for row in data["frames"]:
        path = (review / row["image"]).resolve()
        if not path.is_relative_to(review.resolve()) or digest(path) != row["sha256"]:
            raise ValueError("frame custody mismatch")
    anchor = max(ref.clip_ms for ref in unit.frame_refs)
    window = rewind_window(anchor, lookback_ms, data["end_ms"])
    output.mkdir(parents=True, exist_ok=False)
    retain(output / "protocol.json", {"source_sha256": source_hash,
        "review_sha256": hashlib.sha256(data_bytes).hexdigest(), "units_sha256": hashlib.sha256(unit_bytes).hexdigest(),
        "source_offset_ms": data["source_offset_ms"], "coordinate_system": "clip milliseconds",
        "window": window.model_dump(), "frame_budget_per_arm": frames, "seconds_per_arm": seconds,
        "coarse_frames": 5, "refinement": "largest full-frame RGB mean absolute difference; latest tie wins",
        "anchor_assumption": "latest cited frame of supplied reviewed result unit, not automatically discovered onset",
        "baseline": "existing deterministic Watch decision intersected with same backward window; fps fitted to budget",
        "execution_order": list(reversed(["watch-adaptive-bounded", "debt-rewind"])) if reverse_order else ["watch-adaptive-bounded", "debt-rewind"],
        "boundary": "known-case scheduling/mechanical proof, not blind action recovery or calibrated confidence",
        "code_sha256": {p: digest(Path(__file__).resolve().parents[1] / p) for p in
            ("watch/rewind.py", "scripts/evaluate_watch_rewind.py", "watch/inspection.py", "watch/inspection_runtime.py", "watch/seek.py")}})
    retain(output / "seed.json", payload)
    results = []
    try:
        arms = ("debt-rewind", "watch-adaptive-bounded") if reverse_order else ("watch-adaptive-bounded", "debt-rewind")
        for arm in arms:
            bundle = output / arm
            bundle.mkdir()
            shutil.copyfile(source, bundle / "video.mp4")
            retain(bundle / "timeline.json", {"schema": "beast.watch.timeline/v3",
                "source": {"local_video": "video.mp4", "range": {"start_seconds": 0,
                    "end_seconds": data["end_ms"]/1000, "start": "0", "end": str(data["end_ms"]/1000)}},
                "sampling": {"height": 720}, "frames": []})
            context = InspectionContext(source_interval=Interval(start_ms=0, end_ms=data["end_ms"]),
                candidate_interval=window, confidence=Confidence(perception=0.0, transition=0.0, procedure=0.0))
            started = time.perf_counter()
            if arm == "watch-adaptive-bounded":
                decision = DeterministicWatchPolicy().decide(context)
                target = decision.target_interval
                decision = decision.model_copy(update={"target_interval": Interval(
                    start_ms=max(window.start_ms, target.start_ms), end_ms=min(window.end_ms, target.end_ms))})
                first_budget = frames
            else:
                decision = request(window, "Known result; inspect preceding interval to investigate unresolved action/control.")
                first_budget = 5
            first = execute_inspection(bundle, ffmpeg, decision, context, first_budget, bundle / "first.json",
                fixed_fps=budget_fps(decision.target_interval, first_budget), max_seconds=seconds,
                expected_source_sha256=source_hash)
            measured = changes(bundle, first["frames"])
            retain(bundle / "changes.json", {"pairs": [s.model_dump() for s in measured]})
            charged = first["charged_frames"]
            all_frames = {f["source_seconds"]: f for f in first["frames"]}
            if arm == "debt-rewind":
                next_decision = refinement(window, measured)
                if next_decision and frames-charged >= 2:
                    remaining = seconds-(time.perf_counter()-started)
                    if remaining <= 0:
                        raise TimeoutError("arm time budget exhausted")
                    second = execute_inspection(bundle, ffmpeg, next_decision, context, frames-charged,
                        bundle / "refine.json", fixed_fps=budget_fps(next_decision.target_interval, frames-charged),
                        max_seconds=remaining, expected_source_sha256=source_hash)
                    charged += second["charged_frames"]
                    all_frames.update({f["source_seconds"]: f for f in second["frames"]})
            elapsed = time.perf_counter()-started
            if elapsed > seconds:
                raise TimeoutError("arm time budget exceeded")
            result = {"arm": arm, "charged_frames": charged, "unique_frames": len(all_frames),
                "elapsed_seconds": elapsed, "frames": sorted(all_frames.values(), key=lambda f: f["source_seconds"]),
                "debt": EvidenceDebt().model_dump(), "status": "review_required", "gpu_calls": 0,
                "paid_api_calls": 0, "verified_procedure": False, "publication_allowed": False,
                "action_recall": None, "false_causal_claim_rate": None,
                "boundary": "no action detector; null semantic metrics, not zero errors"}
            retain(bundle / "report.json", result)
            results.append(result)
        if digest(source) != source_hash:
            raise ValueError("original source changed during evaluation")
        report = {"arms": results, "winner": None, "publication_allowed": False,
                  "boundary": "sampling comparison only; reviewer must assess action evidence; no narration path"}
        retain(output / "report.json", report)
        return report
    except Exception as exc:
        retain(output / "failure.json", {"status": "incomplete_do_not_score", "error": str(exc), "type": type(exc).__name__})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("review", "units", "output"):
        parser.add_argument("--"+key, type=Path, required=True)
    parser.add_argument("--frames", type=int, default=16)
    parser.add_argument("--lookback-ms", type=int, default=2000)
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    try:
        report = evaluate(args.review, args.units, args.output, frames=args.frames,
            lookback_ms=args.lookback_ms, seconds=args.seconds, ffmpeg=args.ffmpeg)
        sys.stdout.write(json.dumps({"report": str(args.output / "report.json"), "winner": report["winner"]})+"\n")
        return 0
    except Exception as exc:
        sys.stderr.write(json.dumps({"error": str(exc), "type": type(exc).__name__})+"\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
