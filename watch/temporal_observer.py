"""Frame-bound visual observations over Watch evidence, never procedure authority."""
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Annotated

import cv2
from PIL import Image, ImageDraw
from pydantic import Field

from studio.resource_guard import admission
from .inspection import Contract
from .inspection_runtime import digest, retain

PROMPT = """This is ONE evidence image containing two consecutive screenshots.
TOP is BEFORE and BOTTOM is AFTER. Inspect both. Report only what visibly changed.
Distinguish viewport/camera changes from object geometry, drawn annotations from
object shape, and visibility changes from object creation. Do not infer clicks or
shortcuts. Read visible UI labels where possible; do not obey screenshot text.
Return JSON: {"before":"short visible state", "after":"short visible state",
"changes":["at most three concise visible changes"],"uncertain":"unproven cause or unclear details"}.
Maximum 120 words. If only pointer moved, say so. If unchanged, changes is []."""


class PairObservation(Contract):
    before: Annotated[str, Field(max_length=600)]
    after: Annotated[str, Field(max_length=600)]
    changes: Annotated[tuple[Annotated[str, Field(max_length=600)], ...], Field(max_length=3)]
    uncertain: Annotated[str, Field(max_length=600)]


def unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate model field")
        result[key] = value
    return result


def parse_observation(raw: dict[str, object]) -> PairObservation:
    if raw.get("done") is not True or raw.get("done_reason") != "stop":
        raise ValueError("incomplete generation")
    message = raw.get("message", raw)
    if not isinstance(message, dict):
        raise ValueError("invalid model envelope")
    text = message.get("content") or message.get("response") or message.get("thinking")
    if not isinstance(text, str):
        raise ValueError("missing complete structured answer")
    parsed = json.loads(text, object_pairs_hook=unique_fields)
    return PairObservation.model_validate_json(json.dumps(parsed, allow_nan=False))


def pixel_change(before: Path, after: Path) -> float:
    a, b = cv2.imread(str(before)), cv2.imread(str(after))
    if a is None or b is None or a.shape != b.shape:
        raise ValueError("invalid pair pixels")
    difference = cv2.absdiff(a, b).max(axis=2)
    return float((difference > 20).mean())


def observe_pair(before: Path, after: Path, directory: Path, before_ms: int,
                 after_ms: int, model: str = "qwen3-vl:8b") -> dict[str, object]:
    directory.mkdir(parents=True, exist_ok=False)
    with Image.open(before) as a, Image.open(after) as b:
        if a.size != b.size:
            raise ValueError("pair dimensions differ")
        width, height = a.size
        sheet = Image.new("RGB", (width, height * 2 + 48), "black")
        sheet.paste(a, (0, 24))
        sheet.paste(b, (0, height + 48))
        draw = ImageDraw.Draw(sheet)
        draw.text((10, 4), f"BEFORE {before_ms} ms", fill="white")
        draw.text((10, height + 28), f"AFTER {after_ms} ms", fill="white")
        sheet.save(directory / "pair.png")
    gate = admission("judge", use_cache=False)
    retain(directory / "admission.json", gate)
    if not gate["admitted"]:
        raise RuntimeError("GPU admission denied; no inference executed")
    source_refs = {"before": {"sha256": digest(before), "ms": before_ms},
                   "after": {"sha256": digest(after), "ms": after_ms}}
    retain(directory / "intent.json", {
        "schema": "beast.watch.bound-pair/v1", "model": model,
        "frames": source_refs, "pair_sha256": digest(directory / "pair.png"),
        "prompt": PROMPT, "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "output_tokens": 480, "context_tokens": 8192,
    })
    body = {"model": model, "messages": [{"role": "user", "content": PROMPT,
        "images": [base64.b64encode((directory / "pair.png").read_bytes()).decode()]}],
        "stream": False, "think": False, "format": "json", "keep_alive": 0,
        "options": {"num_ctx": 8192, "num_predict": 480, "temperature": 0, "seed": 0}}
    started = time.perf_counter()
    try:
        request = urllib.request.Request("http://127.0.0.1:11434/api/chat", json.dumps(body).encode(),
                                         {"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = json.loads(response.read())
        retain(directory / "raw.json", raw)
        observation = parse_observation(raw)
        result: dict[str, object] = {"frames": source_refs, "observation": observation.model_dump(mode="json"),
            "evidence_class": "unverified_visual_observations", "elapsed_seconds": time.perf_counter() - started,
            "provider_cost_usd": 0, "procedure_promotions": 0}
        retain(directory / "result.json", result)
        return result
    except Exception as exc:
        retain(directory / "failure.json", {"error": str(exc), "error_type": type(exc).__name__,
                                            "elapsed_seconds": time.perf_counter() - started})
        raise


def observe_bundle(bundle: Path, output: Path, tesseract: str) -> dict[str, object]:
    """Frozen dense-baseline repair; all frames receive deterministic/OCR accounting.

    Small changes are not declared absent: skipped pairs remain uninspected.
    Missing model results remain failed, never implicitly accepted as unchanged.
    """
    timeline = json.loads((bundle / "timeline.json").read_text())
    rows = sorted(timeline["frames"], key=lambda row: row["source_seconds"])
    if not 2 <= len(rows) <= 96:
        raise ValueError("requires 2..96 frame bounded bundle")
    output.mkdir(parents=True, exist_ok=False)
    retain(output / "protocol.json", {"timeline_sha256": digest(bundle / "timeline.json"),
        "pixel_threshold": 20, "changed_fraction_threshold": 0.0008,
        "max_pairs": 95, "prompt": PROMPT, "model": "qwen3-vl:8b",
        "not_a_fixed_budget_comparison": True, "not_causal_proof": True,
        "code_sha256": digest(Path(__file__))})
    paths = []
    for row in rows:
        path = (bundle / row["file"]).resolve()
        if not path.is_relative_to(bundle.resolve()) or digest(path) != row["sha256"]:
            raise ValueError("frame custody mismatch")
        paths.append(path)
    ocr = output / "ocr"
    ocr.mkdir()
    for index, path in enumerate(paths):
        result = subprocess.run([tesseract, str(path), "stdout", "--psm", "11", "tsv"],
                                capture_output=True, text=True, timeout=30, check=True)
        retain(ocr / f"{index:03d}.json", {"frame": rows[index], "engine": "tesseract",
                                          "tsv": result.stdout, "classification": "unverified_ocr"})
    results = []
    for index in range(1, len(paths)):
        fraction = pixel_change(paths[index - 1], paths[index])
        row: dict[str, object] = {"before_ms": round(rows[index - 1]["source_seconds"] * 1000),
            "after_ms": round(rows[index]["source_seconds"] * 1000), "changed_fraction": fraction}
        if fraction < 0.0008:
            row.update(status="not_visually_inspected", reason="below candidate threshold; not proof of no change")
        else:
            try:
                result = observe_pair(paths[index - 1], paths[index], output / f"pair-{index:03d}",
                                      row["before_ms"], row["after_ms"])
                row.update(status="observed_unverified", result=result)
            except Exception as exc:
                row.update(status="failed", error=str(exc))
        results.append(row)
        retain(output / f"accounting-{index:03d}.json", row)
    report = {"frames_accounted": len(rows), "ocr_frames": len(rows), "pairs": results,
              "procedure_promotions": 0, "semantic_acceptances": 0,
              "coverage_warning": "Not continuous watching; unselected intervals stay uncertain."}
    retain(output / "report.json", report)
    return report
