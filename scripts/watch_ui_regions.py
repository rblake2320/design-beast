"""Pinned OmniParser icon detector, CPU only; boxes do not establish UI semantics."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import digest, retain

MODEL = "microsoft/OmniParser-v2.0"
REVISION = "6600256cb0f1b07651e3bc86166196307bad7e2d"


def run(bundle: Path, output: Path) -> None:
    from huggingface_hub import hf_hub_download
    from ultralytics import YOLO
    from PIL import Image
    import torch

    rows = json.loads((bundle / "timeline.json").read_text(encoding="utf-8"))["frames"]
    if len(rows) != 61:
        raise ValueError("frozen detector experiment requires 61 frames")
    output.mkdir(parents=True, exist_ok=False)
    retain(output / "intent.json", {"model": MODEL, "revision": REVISION, "device": "cpu",
        "frames": 61, "timeline_sha256": digest(bundle / "timeline.json"), "threshold": .25,
        "caption_model": None, "license": "upstream icon_detect/LICENSE; weights not redistributed",
        "warning": "Detector boxes/scores are uncalibrated; neither cursor identity nor tool function inferred"})
    started = time.monotonic()
    try:
        license_path = hf_hub_download(MODEL, "icon_detect/LICENSE", revision=REVISION)
        weights = hf_hub_download(MODEL, "icon_detect/model.pt", revision=REVISION)
        retain(output / "weights.json", {"sha256": digest(Path(weights)),
            "license_sha256": digest(Path(license_path)), "license_text": Path(license_path).read_text(encoding="utf-8")})
        torch.set_num_threads(4)
        model = YOLO(weights)
        records = []
        for index, row in enumerate(rows):
            path = (bundle / row["file"]).resolve()
            if not path.is_relative_to(bundle.resolve()):
                raise ValueError("frame escapes bundle")
            pixels = path.read_bytes()
            if hashlib.sha256(pixels).hexdigest() != row["sha256"]:
                raise ValueError("detector frame custody mismatch")
            with Image.open(io.BytesIO(pixels)) as source:
                result = model.predict(source.convert("RGB"), device="cpu", conf=.25, imgsz=1280,
                                       max_det=300, verbose=False)[0]
            boxes = [{"bbox_xyxy": [float(v) for v in box], "raw_score": float(score)}
                     for box, score in zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist())]
            item = {"clip_ms": round(row["source_seconds"]*1000), "sha256": row["sha256"],
                    "regions": boxes, "evidence_class": "unverified_ui_region_detection"}
            retain(output / f"frame-{index:03d}.json", item)
            records.append({"clip_ms": item["clip_ms"], "regions": len(boxes)})
        retain(output / "report.json", {"frames": records, "elapsed_seconds": time.monotonic()-started,
            "semantic_acceptances": 0, "procedure_promotions": 0, "device": "cpu"})
        sys.stdout.write(json.dumps({"status": "detected_unverified", "frames": len(records)})+"\n")
    except Exception as exc:
        retain(output / "failure.json", {"error": str(exc), "type": type(exc).__name__})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.bundle, args.output)


if __name__ == "__main__":
    main()
