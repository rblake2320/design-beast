"""Package a source-faithful local review player from retained Watch measurements."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import digest, retain


def build(bundle: Path, pixels: Path, output: Path) -> dict[str, object]:
    timeline = json.loads((bundle / "timeline.json").read_text(encoding="utf-8"))
    report = json.loads((pixels / "report.json").read_text(encoding="utf-8"))
    intent = json.loads((pixels / "intent.json").read_text(encoding="utf-8"))
    if intent["timeline_sha256"] != digest(bundle / "timeline.json"):
        raise ValueError("pixel measurements belong to a different timeline")
    offset = timeline["source"]["range"]["start_seconds"]
    duration = timeline["source"]["range"]["end_seconds"]-offset
    rows = timeline["frames"]
    if not 2 <= len(rows) <= 96 or len(rows) != len(report["frames"]):
        raise ValueError("incomplete or unsupported review bundle")
    video = (bundle / timeline["source"]["local_video"]).resolve()
    if not video.is_relative_to(bundle.resolve()):
        raise ValueError("video escapes bundle")
    source_hash = digest(video)
    if timeline["source"].get("sha256", source_hash) != source_hash:
        raise ValueError("source video custody mismatch")
    output.mkdir(parents=True, exist_ok=False)
    retain(output / "intent.json", {"source_sha256": source_hash, "timeline_sha256": digest(bundle / "timeline.json"),
        "pixel_report_sha256": digest(pixels / "report.json"), "publication_allowed": False})
    try:
        (output / "media").mkdir()
        shutil.copyfile(video, output / "media/source.mp4")
        if digest(output / "media/source.mp4") != source_hash:
            raise ValueError("copied video differs")
        frames = []
        for index, (row, accounting) in enumerate(zip(rows, report["frames"])):
            path = (bundle / row["file"]).resolve()
            if not path.is_relative_to(bundle.resolve()):
                raise ValueError("frame escapes bundle")
            encoded = path.read_bytes()
            state_bytes = (pixels / f"frame-{index:03d}/state.json").read_bytes()
            state = json.loads(state_bytes)
            if (hashlib.sha256(encoded).hexdigest() != row["sha256"] or
                hashlib.sha256(state_bytes).hexdigest() != accounting["state_sha256"] or
                state["frame_sha256"] != row["sha256"] or
                accounting["sha256"] != row["sha256"] or accounting["clip_ms"] != state["clip_ms"] or
                state["clip_ms"] != round(row.get("clip_seconds", row["source_seconds"]-offset)*1000)):
                raise ValueError("review evidence custody mismatch")
            relative = f"media/frame-{index:03d}.jpg"
            with (output / relative).open("xb") as stream:
                stream.write(encoded)
            frames.append({"clip_ms": state["clip_ms"], "sha256": row["sha256"], "image": relative,
                "changed_regions": state["changed_regions"], "changed_fraction": state["changed_pixel_fraction"] or 0,
                "tracks": len(state["motion_tracks"]), "text": [t["text"] for t in state["text_elements"]],
                "appeared_text": bool(state["appeared_text_track_ids"])})
        data = {"source_sha256": source_hash, "end_ms": round(duration*1000),
            "source_offset_ms": round(offset*1000), "frames": frames}
        template = (Path(__file__).resolve().parents[1] / "watch/review_player.html").read_text(encoding="utf-8")
        # Never allow source OCR to terminate the data script element.
        safe_json = json.dumps(data, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        with (output / "index.html").open("x", encoding="utf-8") as stream:
            stream.write(template.replace("__WATCH_DATA__", safe_json))
        retain(output / "review-data.json", data)
        retain(output / "report.json", {"frames": len(frames), "source_sha256": source_hash,
            "review_data_sha256": digest(output / "review-data.json"),
            "html_sha256": digest(output / "index.html"), "generated_visuals": 0, "publication_allowed": False})
        return data
    except Exception as exc:
        retain(output / "failure.json", {"error": str(exc), "type": type(exc).__name__})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "pixels", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    args = parser.parse_args()
    build(args.bundle, args.pixels, args.output)


if __name__ == "__main__":
    main()
