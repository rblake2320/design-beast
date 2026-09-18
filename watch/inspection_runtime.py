"""Watch-owned, write-ahead inspection execution and immutable receipts."""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path

from .inspection import InspectionContext, InspectionDecision, plan_seek
from .seek import reinspect
from .core import frame_name


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def retain(path: Path, payload: dict[str, object]) -> None:
    """Exclusive durable receipt. Existing intent forbids automatic replay."""
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())


def execute_inspection(bundle: Path, ffmpeg: str, decision: InspectionDecision,
                       context: InspectionContext, remaining_frames: int,
                       receipt: Path, *, fixed_fps: float | None = None,
                       max_seconds: float = 60.0, expected_source_sha256: str | None = None) -> dict[str, object]:
    """Single writer per bundle; interrupted/failed runs require explicit reconciliation."""
    bundle = bundle.resolve()
    if not receipt.resolve().is_relative_to(bundle):
        raise ValueError("receipt must be inside bundle")
    lock = bundle / ".inspection-lock"
    lock.mkdir(exist_ok=False)
    try:
        result = _execute_locked(bundle, ffmpeg, decision, context, remaining_frames,
                                 receipt, fixed_fps=fixed_fps, max_seconds=max_seconds,
                                 expected_source_sha256=expected_source_sha256)
    except Exception:
        # Preserve lock: an operator must inspect intent/failure and reconcile.
        raise
    lock.rmdir()
    return result


def _execute_locked(bundle: Path, ffmpeg: str, decision: InspectionDecision,
                       context: InspectionContext, remaining_frames: int,
                       receipt: Path, *, fixed_fps: float | None = None,
                       max_seconds: float = 60.0, expected_source_sha256: str | None = None) -> dict[str, object]:
    if isinstance(max_seconds, bool) or not math.isfinite(max_seconds) or max_seconds <= 0:
        raise ValueError("invalid compute budget")
    decision = InspectionDecision.model_validate(decision.model_dump())
    context = InspectionContext.model_validate(context.model_dump())
    plan = plan_seek(decision, context, remaining_frames, fixed_fps=fixed_fps)
    timeline_path = bundle / "timeline.json"
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    if not timeline_path.resolve().is_relative_to(bundle) or not (bundle / "frames").resolve().is_relative_to(bundle):
        raise ValueError("timeline/frame directory escapes Watch bundle")
    for row in timeline.get("frames", []):
        path = bundle / row["file"]
        if not path.resolve().is_relative_to(bundle) or not path.with_name(path.stem + ".verify.jpg").resolve().is_relative_to(bundle):
            raise ValueError("existing frame escapes Watch bundle")
    for stamp in plan.timestamps if plan else ():
        if not (bundle / "frames" / frame_name(stamp)).resolve().is_relative_to(bundle):
            raise ValueError("planned frame escapes Watch bundle")
    if not timeline_path.with_suffix(".json.tmp").resolve().is_relative_to(bundle):
        raise ValueError("temporary timeline escapes Watch bundle")
    actual_range = timeline["source"]["range"]
    if (actual_range["start_seconds"] * 1000 != context.source_interval.start_ms
            or actual_range["end_seconds"] * 1000 != context.source_interval.end_ms):
        raise ValueError("context does not match actual source range")
    video = (bundle / timeline["source"]["local_video"]).resolve()
    if not video.is_relative_to(bundle.resolve()):
        raise ValueError("source escapes Watch bundle")
    intent: dict[str, object] = {
        "schema": "beast.watch.inspection-receipt/v1",
        "status": "intent", "context": context.model_dump(mode="json"),
        "decision": decision.model_dump(mode="json"),
        "source_sha256": digest(video), "timeline_before_sha256": digest(timeline_path),
        "plan": plan.model_dump(mode="json") if plan else None,
        "frame_budget": remaining_frames,
        "max_seconds": max_seconds,
    }
    if expected_source_sha256 is not None and intent["source_sha256"] != expected_source_sha256:
        raise ValueError("source differs from expected frozen identity")
    retain(receipt, intent)
    started = time.perf_counter()
    try:
        request = None if plan is None else reinspect(
            bundle, ffmpeg, center=plan.center_seconds, level=plan.level,
            direction=plan.direction, before=plan.before_seconds, after=plan.after_seconds,
            fps=plan.fps, reason="; ".join(decision.uncertainty_reasons),
            deadline=time.monotonic() + max_seconds)
        after = json.loads(timeline_path.read_text(encoding="utf-8"))
        retained = {round(float(row["source_seconds"]), 3): row for row in after["frames"]}
        if plan and any(stamp not in retained for stamp in plan.timestamps):
            raise ValueError("Watch failed to retain every requested frame")
        frames = []
        for stamp in plan.timestamps if plan else ():
            row = retained[stamp]
            path = (bundle / row["file"]).resolve()
            if not path.is_relative_to(bundle.resolve()):
                raise ValueError("frame escapes Watch bundle")
            actual = digest(path)
            if row.get("sha256") != actual:
                raise ValueError("frame integrity mismatch")
            frames.append({"source_seconds": stamp, "file": row["file"], "sha256": actual})
        if digest(video) != intent["source_sha256"]:
            raise ValueError("source changed during inspection")
        result: dict[str, object] = {
            "status": "completed", "intent_sha256": digest(receipt),
            "elapsed_seconds": time.perf_counter() - started,
            "charged_frames": len(plan.timestamps) if plan else 0,
            "provider_cost": 0, "request": request, "frames": frames,
            "timeline_after_sha256": digest(timeline_path),
        }
    except Exception as exc:
        retain(receipt.with_suffix(".failure.json"), {
            "status": "outcome_unknown", "intent_sha256": digest(receipt),
            "error_type": type(exc).__name__, "error": str(exc),
        })
        raise
    retain(receipt.with_suffix(".result.json"), result)
    return result
