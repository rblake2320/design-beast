"""Append a UTF8 repair evidence set; never overwrite the failed OCR receipts."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import digest, retain
from watch.ocr_observer import observe_ocr


def main():
    bundle = Path("watched/dense-repair-01")
    prior = Path("proofs/watch-repair/dense-instruct-01")
    output = Path("proofs/watch-repair/dense-ocr-recovery-01")
    output.mkdir(parents=True, exist_ok=False)
    rows = sorted(json.loads((bundle / "timeline.json").read_text())["frames"], key=lambda row: row["source_seconds"])
    retain(output / "intent.json", {"reason": "All prior OCR used incorrect Windows decoding; 17 null, others may contain mojibake",
        "prior_report_sha256": digest(prior / "report.json"), "timeline_sha256": digest(bundle / "timeline.json"),
        "max_cpu_ocr_calls": len(rows), "vision_calls": 0})
    results = []
    for index, row in enumerate(rows):
        path = (bundle / row["file"]).resolve()
        if not path.is_relative_to(bundle.resolve()):
            raise ValueError("source escapes bundle")
        value = observe_ocr(path, row["sha256"], r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        value.update(clip_ms=round(row["source_seconds"] * 1000),
                     prior_receipt_sha256=digest(prior / f"frame-{index:03d}" / "ocr.json"))
        retain(output / f"frame-{index:03d}.json", value)
        results.append({"frame": index, "sha256": row["sha256"], "status": "unverified_ocr"})
    retain(output / "report.json", {"frames": results, "semantic_acceptances": 0, "vision_calls": 0})
    print(f"Retained {len(results)} replacement OCR observations; original failure evidence unchanged.")


if __name__ == "__main__":
    main()
