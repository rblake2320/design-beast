"""OCR over exactly verified bytes, independent of the Windows text locale."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


def observe_ocr(path: Path, expected_sha256: str, executable: str) -> dict[str, object]:
    pixels = path.read_bytes()
    if hashlib.sha256(pixels).hexdigest() != expected_sha256:
        raise ValueError("OCR source custody mismatch")
    result = subprocess.run([executable, "stdin", "stdout", "--psm", "11", "tsv"],
                            input=pixels, check=True, capture_output=True, timeout=30)
    text = result.stdout.decode("utf-8", errors="strict")
    if not text.startswith("level\tpage_num\t"):
        raise ValueError("OCR response is not TSV")
    return {"frame_sha256": expected_sha256, "tsv": text, "evidence_class": "unverified_ocr",
            "encoding": "utf-8", "input_transport": "verified bytes on stdin"}
