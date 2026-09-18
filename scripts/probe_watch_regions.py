"""Bounded same-case resolution probe. Not a held-out evaluation."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.frame_observer import observe_frame
from watch.inspection_runtime import digest, retain


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    timeline = json.loads((args.bundle / "timeline.json").read_text(encoding="utf-8"))
    # Deliberately selected after failures: diagnostic, not unbiased recall proof.
    cases = [(0, "top-left", (0, 0, 640, 180)),
             (17, "viewport", (320, 140, 820, 640)),
             (23, "viewport", (320, 140, 820, 640)),
             (34, "center", (200, 120, 1080, 600))]
    retain(args.output / "protocol.json", {"selection": "post-failure diagnostic; not held out",
        "timeline_sha256": digest(args.bundle / "timeline.json"), "cases": cases,
        "model": "qwen3-vl:8b-instruct", "max_calls": 4, "procedure_promotions": 0})
    rows = sorted(timeline["frames"], key=lambda item: item["source_seconds"])
    for index, label, box in cases:
        row = rows[index]
        path = (args.bundle / row["file"]).resolve()
        if not path.is_relative_to(args.bundle.resolve()):
            raise ValueError("source escapes bundle")
        pixels = path.read_bytes()
        if hashlib.sha256(pixels).hexdigest() != row["sha256"]:
            raise ValueError("source changed")
        directory = args.output / f"frame-{index:03d}-{label}"
        directory.mkdir()
        with Image.open(io.BytesIO(pixels)) as image:
            image.crop(box).save(directory / "crop.png")
        retain(directory / "lineage.json", {"original_sha256": row["sha256"], "bbox_xyxy": box,
            "clip_ms": round(row["source_seconds"] * 1000), "crop_sha256": digest(directory / "crop.png"),
            "transformation": "deterministic crop; no generated pixels", "label": label})
        observe_frame(directory / "crop.png", round(row["source_seconds"] * 1000),
                      digest(directory / "crop.png"), directory / "vision", "qwen3-vl:8b-instruct",
                      expected_model_digest="0533d74300e4f9bc367d675d4e64ffd073d50ff16a2b4096cc2e8a1cf8c96319")
        print(index, "retained", flush=True)


if __name__ == "__main__":
    main()
