"""Run CPU spatial/temporal measurement on a retained Watch frame bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import digest, retain
from watch.ocr_observer import observe_ocr


def clip_stamps(timeline: dict[str, object]) -> list[int]:
    """Resolve the two clocks without silently accepting contradictory coordinates."""
    offset = timeline.get("source", {}).get("range", {}).get("start_seconds", 0)
    stamps = []
    for row in timeline["frames"]:
        relative = row["source_seconds"]-offset
        clip = row.get("clip_seconds", relative)
        if abs(clip-relative) > .001:
            raise ValueError("source and clip clocks disagree")
        stamps.append(round(clip*1000))
    return stamps


def run(bundle: Path, output: Path, ocr_root: Path | None, max_seconds: float = 180) -> dict[str, object]:
    from watch.visual_state import VisualStateTracker, decode_verified
    import cv2
    import numpy as np

    raw_timeline = (bundle / "timeline.json").read_bytes()
    timeline = json.loads(raw_timeline)
    rows = timeline["frames"]
    if not 2 <= len(rows) <= 96:
        raise ValueError("requires 2..96 frames")
    stamps = clip_stamps(timeline)
    if any(type(s) is not int or s < 0 for s in stamps) or any(b <= a for a, b in zip(stamps, stamps[1:])):
        raise ValueError("unordered or duplicate timestamps")
    if not 0 < max_seconds <= 600:
        raise ValueError("invalid runtime budget")
    output.mkdir(parents=True, exist_ok=False)
    retain(output / "intent.json", {"schema": "beast.watch.pixel-run/v1",
        "timeline_sha256": hashlib.sha256(raw_timeline).hexdigest(), "max_frames": len(rows),
        "max_seconds": max_seconds, "opencv": cv2.__version__, "numpy": np.__version__,
        "implementation_sha256": digest(Path(__file__).resolve().parents[1] / "watch/visual_state.py"),
        "time_basis": "clip-relative milliseconds", "model_calls": 0, "audio_or_transcript": False,
        "ocr_mode": "reused_retained_receipts" if ocr_root else "fresh_tesseract",
        "elapsed_excludes_prior_ocr": bool(ocr_root)})
    tracker = VisualStateTracker()
    started = time.monotonic()
    results = []
    try:
        for index, row in enumerate(rows):
            if time.monotonic() - started >= max_seconds:
                raise TimeoutError("pixel run budget exhausted; partial states not a complete run")
            path = (bundle / row["file"]).resolve()
            if not path.is_relative_to(bundle.resolve()):
                raise ValueError("frame escapes bundle")
            image = decode_verified(path, row["sha256"])
            directory = output / f"frame-{index:03d}"
            directory.mkdir()
            if ocr_root is None:
                ocr = observe_ocr(path, row["sha256"], r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                                  timeout=max(.001, min(30, max_seconds-(time.monotonic()-started))))
            else:
                flat = ocr_root / f"frame-{index:03d}.json"
                ocr_path = flat if flat.exists() else ocr_root / f"frame-{index:03d}" / "ocr.json"
                if not ocr_path.resolve().is_relative_to(ocr_root.resolve()):
                    raise ValueError("OCR escapes retained root")
                ocr_bytes = ocr_path.read_bytes()
                ocr = json.loads(ocr_bytes)
                retain(directory / "ocr-source.json", {"receipt_sha256": hashlib.sha256(ocr_bytes).hexdigest()})
            if ocr["frame_sha256"] != row["sha256"] or not isinstance(ocr["tsv"], str):
                raise ValueError("OCR custody or observation missing")
            retain(directory / "ocr.json", ocr)
            state = tracker.update(image, stamps[index], row["sha256"], ocr["tsv"])
            if time.monotonic()-started >= max_seconds:
                raise TimeoutError("pixel run budget exhausted during observation")
            retain(directory / "state.json", state.model_dump(mode="json"))
            # Diagnostic derivatives are never reused as perception input.
            overlay = image.copy()
            for x, y, w, h in state.changed_regions:
                cv2.rectangle(overlay, (x, y), (x+w, y+h), (0, 200, 255), 1)
            for track in state.motion_tracks:
                cv2.line(overlay, tuple(round(v) for v in track.before), tuple(round(v) for v in track.after), (0, 255, 0), 1)
            ok, encoded = cv2.imencode(".jpg", overlay)
            if not ok:
                raise ValueError("diagnostic encoding failed")
            with (directory / "diagnostic.jpg").open("xb") as stream:
                stream.write(encoded.tobytes())
            results.append({"clip_ms": state.clip_ms, "sha256": state.frame_sha256,
                "tracks": len(state.motion_tracks), "text_elements": len(state.text_elements),
                "changed_regions": len(state.changed_regions), "scale": state.motion_scale,
                "tracking_reset": state.tracking_reset, "state_sha256": digest(directory / "state.json")})
        if time.monotonic()-started >= max_seconds:
            raise TimeoutError("pixel run budget exhausted before report")
        report = {"frames": results, "elapsed_seconds": time.monotonic()-started,
            "model_calls": 0, "semantic_acceptances": 0, "procedure_promotions": 0,
            "status": "measured_not_semantically_verified"}
        retain(output / "report.json", report)
        return report
    except Exception as exc:
        retain(output / "failure.json", {"type": type(exc).__name__, "error": str(exc),
                                         "frames_completed": len(results), "status": "incomplete"})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ocr-root", type=Path)
    args = parser.parse_args()
    result = run(args.bundle, args.output, args.ocr_root)
    sys.stdout.write(json.dumps({"frames": len(result["frames"]), "status": result["status"],
                                 "elapsed_seconds": result["elapsed_seconds"]}) + "\n")


if __name__ == "__main__":
    main()
