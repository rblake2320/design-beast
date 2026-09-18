"""Replayable dense Watch observation experiment; no transcript or hidden labels."""
from __future__ import annotations

import argparse
import json
import hashlib
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.inspection import Confidence, InspectionContext, InspectionDecision, Interval
from watch.inspection_runtime import digest, execute_inspection, retain
from watch.frame_observer import observe_frame
from watch.temporal_observer import pixel_change


def prepare(source: Path, start: int, output: Path, ffmpeg: str) -> None:
    output.mkdir(parents=True, exist_ok=False)
    retain(output / "source.json", {"source_path": str(source.resolve()), "source_sha256": digest(source),
                                   "start_seconds": start, "end_seconds": start + 30,
                                   "audio": "excluded", "transcript": "excluded"})
    subprocess.run([ffmpeg, "-v", "error", "-nostdin", "-n", "-threads", "2", "-ss", str(start),
                    "-i", str(source), "-t", "31", "-an", "-vf", "scale=1280:-2",
                    "-c:v", "libx264", "-threads", "2", "-preset", "fast", "-crf", "18",
                    str(output / "video.mp4")], check=True, timeout=180, capture_output=True)
    retain(output / "timeline.json", {"schema": "beast.watch.timeline/v3",
        "source": {"local_video": "video.mp4", "range": {"start_seconds": 0, "end_seconds": 30,
        "start": "0", "end": "30"}}, "sampling": {"height": 720}, "frames": []})
    interval = Interval(start_ms=0, end_ms=30000)
    context = InspectionContext(source_interval=interval, candidate_interval=interval,
                               confidence=Confidence(perception=0.0, transition=0.0, procedure=0.0))
    decision = InspectionDecision(requested_action="increase_density", target_interval=interval,
        predicted_value_of_inspection=0.5, confidence=context.confidence,
        uncertainty_reasons=("Dense repair baseline; semantic coverage required across entire bounded interval.",))
    execute_inspection(output, ffmpeg, decision, context, 61, output / "inspection.json", fixed_fps=2.0,
                       expected_source_sha256=digest(output / "video.mp4"))


def run(bundle: Path, output: Path, tesseract: str, model: str) -> None:
    output.mkdir(parents=True, exist_ok=False)
    timeline = json.loads((bundle / "timeline.json").read_text())
    rows = sorted(timeline["frames"], key=lambda row: row["source_seconds"])
    if [row["source_seconds"] for row in rows] != [index / 2 for index in range(61)]:
        raise ValueError("frozen experiment requires unique exact 2fps timestamps")
    inspection = json.loads((bundle / "inspection.result.json").read_text())
    intent = json.loads((bundle / "inspection.json").read_text())
    if digest(bundle / "timeline.json") != inspection["timeline_after_sha256"] or digest(bundle / "video.mp4") != intent["source_sha256"]:
        raise ValueError("frozen bundle identity changed")
    if inspection["intent_sha256"] != digest(bundle / "inspection.json"):
        raise ValueError("inspection receipt chain changed")
    source = json.loads((bundle / "source.json").read_text())
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=10) as response:
        identity = next(item for item in json.loads(response.read())["models"] if item["name"] == model)
    retain(output / "protocol.json", {"timeline_sha256": digest(bundle / "timeline.json"),
        "source": source, "clip_sha256": intent["source_sha256"], "model_digest": identity["digest"],
        "model": model, "frames": 61, "max_vision_calls": 61, "output_tokens_per_frame": 600,
        "frame_binding": "single-image request; timestamp and hash attached only by code",
        "inference_sample_rate": 2, "comparison": "repair not equal-budget efficiency test",
        "observer_sha256": digest(Path(__file__).resolve().parents[1] / "watch/frame_observer.py")})
    states = []
    for index, row in enumerate(rows):
        path = (bundle / row["file"]).resolve()
        if not path.is_relative_to(bundle.resolve()) or digest(path) != row["sha256"]:
            raise ValueError("frame custody failure")
        frame_dir = output / f"frame-{index:03d}"
        frame_dir.mkdir()
        ocr_status = "failed"
        try:
            ocr_pixels = path.read_bytes()
            if hashlib.sha256(ocr_pixels).hexdigest() != row["sha256"]:
                raise ValueError("OCR source changed before submission")
            ocr = subprocess.run([tesseract, "stdin", "stdout", "--psm", "11", "tsv"],
                                 input=ocr_pixels, check=True, capture_output=True, timeout=30)
            if digest(path) != row["sha256"]:
                raise ValueError("OCR source changed")
            retain(frame_dir / "ocr.json", {"frame_sha256": row["sha256"], "tsv": ocr.stdout.decode("utf-8"),
                                            "evidence_class": "unverified_ocr"})
            ocr_status = "observed_unverified"
        except Exception as exc:
            retain(frame_dir / "ocr-failure.json", {"error": str(exc), "error_type": type(exc).__name__})
        try:
            result = observe_frame(path, round(row["source_seconds"] * 1000), row["sha256"],
                                   frame_dir / "vision", model=model, source_offset_ms=source["start_seconds"] * 1000,
                                   source_sha256=source["source_sha256"], expected_model_digest=identity["digest"])
            states.append({"frame": row, "status": "observed_unverified", "ocr_status": ocr_status, "result": result})
        except Exception as exc:
            states.append({"frame": row, "status": "failed", "ocr_status": ocr_status, "error": str(exc)})
        retain(frame_dir / "accounting.json", states[-1])
        sys.stdout.write(f"{index + 1}/61 {states[-1]['status']}\n")
        sys.stdout.flush()
    transitions = []
    for index in range(1, len(states)):
        before, after = states[index - 1], states[index]
        for entry in (before, after):
            if digest(bundle / entry["frame"]["file"]) != entry["frame"]["sha256"]:
                raise ValueError("frame changed before temporal comparison")
        item = {"before_sha256": before["frame"]["sha256"], "after_sha256": after["frame"]["sha256"],
                "before_ms": round(before["frame"]["source_seconds"] * 1000),
                "after_ms": round(after["frame"]["source_seconds"] * 1000),
                "pixel_change_fraction": pixel_change(bundle / before["frame"]["file"], bundle / after["frame"]["file"]),
                "evidence_class": "unverified_transition_candidate", "procedure_confidence": None}
        if before["status"] == after["status"] == "observed_unverified":
            item["before_state"] = before["result"]["state"]
            item["after_state"] = after["result"]["state"]
        else:
            item["status"] = "uncertain_missing_observation"
        transitions.append(item)
    retain(output / "report.json", {"frames_accounted": 61, "states": states, "transitions": transitions,
        "complete_observations": sum(row["status"] == "observed_unverified" for row in states),
        "procedure_promotions": 0, "awaiting_independent_review": True})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--ffmpeg")
    parser.add_argument("--tesseract", default=r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    parser.add_argument("--model", default="qwen3-vl:8b-instruct")
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args.source, args.start, args.output, args.ffmpeg)
    else:
        run(args.source, args.output, args.tesseract, args.model)


if __name__ == "__main__":
    main()
