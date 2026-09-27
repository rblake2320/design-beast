"""Retrospective evidence-availability comparison; no inference or semantic verdicts."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import subprocess
import time

from pydantic import BaseModel, ConfigDict, Field

COMMIT = "a7d8faeca4ede6ff1f540ba14737b6ccdb1285ed"
STARTS = [0, 8, 16, 24, 32, 40, 45]
ROOT = "proofs/watch-pixel-state"


class Frame(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)
    file: str
    clip_seconds: float = Field(ge=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    perceptual_hash: str = Field(pattern=r"^[a-f0-9]{16}$")


class Timeline(BaseModel):
    frames: list[Frame] = Field(min_length=61, max_length=61)


class Member(BaseModel):
    clip_ms: int
    sha256: str


class Window(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)
    window: int
    frames: list[Member] = Field(min_length=16, max_length=16)
    embedding: list[float] = Field(min_length=1024, max_length=1024)
    distance_from_previous: float | None


class GitInputs:
    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.inventory: dict[str, dict[str, int | str]] = {}

    def read(self, path: str) -> bytes:
        relative = PurePosixPath(path)
        if relative.is_absolute() or ".." in relative.parts or "\\" in path:
            raise ValueError("unsafe artifact path")
        data = subprocess.run(
            ["git", "-C", str(self.repo), "show", f"{COMMIT}:{path}"],
            check=True, capture_output=True, timeout=30,
        ).stdout
        self.inventory[path] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        return data


def distance(before: list[float], after: list[float]) -> float:
    if len(before) != len(after) or not before:
        raise ValueError("inconsistent vectors")
    for vector in (before, after):
        if not all(math.isfinite(x) for x in vector):
            raise ValueError("nonfinite vector")
        if abs(sum(x*x for x in vector) - 1) > 1e-5:
            raise ValueError("not normalized")
    return 1 - sum(a*b for a, b in zip(before, after))


def choose(scores: dict[int, float]) -> list[int]:
    if len(scores) != 6 or set(scores) != set(range(1, 7)):
        raise ValueError("candidate set differs")
    if not all(math.isfinite(x) for x in scores.values()):
        raise ValueError("nonfinite score")
    return sorted(scores, key=lambda i: (-scores[i], i))[:2]


def covered(interval: tuple[float, float], windows: list[tuple[float, float]]) -> bool:
    start, end = interval
    if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= 30):
        raise ValueError("invalid reference interval")
    return any(left <= start and end <= right for left, right in windows)


def retain(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def case(inputs: GitInputs, name: str, bundle: str) -> dict:
    prefix = f"proofs/watch-repair/inputs/{bundle}"
    timeline = Timeline.model_validate_json(inputs.read(f"{prefix}/timeline.json"))
    frames = timeline.frames
    if [f.clip_seconds for f in frames] != [i/2 for i in range(61)]:
        raise ValueError("unexpected sample clock")
    for frame in frames:
        data = inputs.read(f"{prefix}/{frame.file}")
        if hashlib.sha256(data).hexdigest() != frame.sha256:
            raise ValueError("frame bytes differ")
    vectors: list[list[float]] = []
    scores: dict[int, float] = {}
    pixels: dict[int, float] = {}
    for index, start in enumerate(STARTS):
        window = Window.model_validate_json(inputs.read(f"{ROOT}/vjepa-{name}-01/window-{index:02d}.json"))
        expected = frames[start:start+16]
        if window.window != index or [(m.clip_ms, m.sha256) for m in window.frames] != [
            (round(f.clip_seconds*1000), f.sha256) for f in expected
        ]:
            raise ValueError("window membership differs")
        distance(window.embedding, window.embedding)
        if index == 0:
            if window.distance_from_previous is not None:
                raise ValueError("initial distance must be absent")
        else:
            actual = distance(vectors[-1], window.embedding)
            if window.distance_from_previous is None or abs(actual-window.distance_from_previous) > 1e-5:
                raise ValueError("forged distance")
            scores[index] = actual
            pixels[index] = sum((int(a.perceptual_hash, 16)^int(b.perceptual_hash, 16)).bit_count()
                                for a, b in zip(expected, expected[1:]))/15
        vectors.append(window.embedding)
    # Selection receives only features, never reference labels.
    arms = {"uniform": [2, 5], "pixel_change": choose(pixels), "vjepa": choose(scores)}
    return {"selections": arms, "vjepa_scores": scores, "pixel_scores": pixels,
            "historical_encoder_report": json.loads(inputs.read(f"{ROOT}/vjepa-{name}-01/report.json")),
            "encoder_image_presentations": 112,
            "encoder_unique_images": len({i for s in STARTS for i in range(s, s+16)}),
            "pixel_preprocessing_images": 61}


def run(repo: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    retain(output / "intent.json", {"commit": COMMIT, "protocol_sha256": hashlib.sha256(
        (Path(__file__).resolve().parents[1]/"proofs/vjepa-selection/PLAN.md").read_bytes()).hexdigest(),
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "kind": "retained-feature replay", "new_model_calls": 0})
    inputs = GitInputs(repo)
    started = time.perf_counter()
    try:
        cases = {"blender": case(inputs, "blender", "dense-repair-01"),
                 "heldout": case(inputs, "heldout", "heldout-repair-01")}
        # These independent references predate this experiment. Freeze exact bytes.
        inputs.read("proofs/watch-real-video/BLIND-REFERENCE.md")
        inputs.read("proofs/watch-repair/HELDOUT-REFERENCE.md")
        labels = {"blender": [(1,2.5),(2.5,6),(6.5,9.5),(9.5,10),(10.5,12.5),
                              (12.5,13),(14,14.5),(15.5,16),(16.5,17.5),(19,21)],
                  "heldout": [(14.5,15),(15,16),(16,17),(17,17.5),(20,20.5)]}
        for name, result in cases.items():
            result["reference_intervals"] = labels[name]
            result["coverage"] = {}
            for arm, indices in result["selections"].items():
                windows = [(STARTS[i]/2, (STARTS[i]+15)/2) for i in indices]
                images = {f for i in indices for f in range(STARTS[i], STARTS[i]+16)}
                hits = [i+1 for i, interval in enumerate(labels[name]) if covered(interval, windows)]
                result["coverage"][arm] = {"windows_seconds": windows, "reference_hits": hits,
                    "count": len(hits), "total": len(labels[name]), "review_presentations": 32,
                    "unique_review_images": len(images)}
        totals = {arm: sum(c["coverage"][arm]["count"] for c in cases.values())
                  for arm in ("uniform", "pixel_change", "vjepa")}
        passed = all(totals["vjepa"] > totals[a] for a in ("uniform", "pixel_change")) and all(
            c["coverage"]["vjepa"]["count"] >= c["coverage"][a]["count"]
            for c in cases.values() for a in ("uniform", "pixel_change"))
        retain(output/"inputs.json", inputs.inventory)
        retain(output/"report.json", {"cases": cases, "total_reference_coverage": totals,
            "vjepa_selection_graduation": "PASS" if passed else "FAIL", "reference_total": 15,
            "replay_wall_seconds": time.perf_counter()-started, "new_gpu_calls": 0,
            "semantic_verdicts": 0, "procedure_promotions": 0, "provider_cost_usd": 0})
    except Exception as exc:
        retain(output/"failure.json", {"type": type(exc).__name__, "message": str(exc)})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.source_repo, args.output)
