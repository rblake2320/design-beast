"""CPU-only synthetic video control experiment, not a visual-understanding benchmark."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Annotated, Literal, Self

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageStat
from pydantic import Field, model_validator

from watch.inspection import (Confidence, Contract, DeterministicWatchPolicy, EvidenceGates,
                              InspectionContext, InspectionDecision, Interval)
from watch.inspection_runtime import digest, execute_inspection, retain

CASES = (
    ("case-01", "silent_action", "persistent", True),
    ("case-02", "brief_transition", "brief", True),
    ("case-03", "ambiguous_cause", "persistent", True),
    ("case-04", "visual_occlusion", "static", False),
)


class Truth(Contract):
    pixel_transition: bool
    causal_procedure: bool


class Case(Contract):
    id: Annotated[str, Field(pattern=r"^case-[0-9]{2}$")]
    source_kind: Literal["prerecorded"]
    synthetic: Literal[True]
    stratum: Literal["silent_action", "brief_transition", "ambiguous_cause", "visual_occlusion"]
    file: Annotated[str, Field(pattern=r"^case-[0-9]{2}\.mkv$")]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    ground_truth: Truth


class Corpus(Contract):
    schema_version: Literal["beast.watch.inspection-corpus/v1"] = Field(alias="schema")
    cases: Annotated[tuple[Case, ...], Field(min_length=1)]
    boundary: str
    frame_budget: Annotated[int, Field(strict=True, ge=1, le=100)]
    inspection_budget: Literal[1]
    max_seconds_per_case: Annotated[int, Field(strict=True, ge=1, le=60)]
    unsupported_strata: tuple[str, ...]
    absent_test_sets: tuple[str, ...]

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("duplicate case IDs")
        return self


def prepare(root: Path, ffmpeg: str) -> dict[str, object]:
    """Generate owner-authored test media; never overwrite a frozen corpus."""
    root.mkdir(parents=True, exist_ok=False)
    cases = []
    for case_id, stratum, pattern, changed in CASES:
        video = root / f"{case_id}.mkv"
        frames = bytearray()
        for index in range(157):
            active = (pattern == "persistent" and index >= 75) or (pattern == "brief" and 52 <= index <= 57)
            frames.extend(bytes([220 if active else 30]) * (96 * 64 * 3))
        subprocess.run([ffmpeg, "-v", "error", "-nostdin", "-n", "-f", "rawvideo",
                        "-pixel_format", "rgb24", "-video_size", "96x64", "-framerate", "25",
                        "-i", "pipe:0", "-an", "-c:v", "ffv1", "-threads", "1", str(video)],
                       input=bytes(frames), check=True, timeout=30, capture_output=True)
        cases.append({"id": case_id, "source_kind": "prerecorded", "synthetic": True,
                      "stratum": stratum, "file": video.name, "sha256": digest(video),
                      "ground_truth": {"pixel_transition": changed, "causal_procedure": False}})
    manifest = {"schema": "beast.watch.inspection-corpus/v1", "cases": cases,
                "boundary": "Synthetic luminance clips only; no application actions or live telemetry.",
                "frame_budget": 25, "inspection_budget": 1, "max_seconds_per_case": 60,
                "unsupported_strata": ["misleading_narration", "version_drift"],
                "absent_test_sets": ["live_capture", "real_training_video"]}
    retain(root / "manifest.json", manifest)
    return {"manifest": str(root / "manifest.json"), "sha256": digest(root / "manifest.json")}


class FixedPolicy:
    name = "fixed-1fps-v1"

    def decide(self, context: InspectionContext) -> InspectionDecision:
        return InspectionDecision(requested_action="increase_density",
                                  target_interval=context.source_interval,
                                  predicted_value_of_inspection=0.5, confidence=context.confidence,
                                  uncertainty_reasons=("Uniform sampling; cause remains unproven.",))


def evaluate(root: Path, expected_sha256: str, output: Path, ffmpeg: str) -> dict[str, object]:
    """Policies receive only public typed context, not the manifest, labels or video path.

    This is a cooperative in-process interface, NOT an OS sandbox for hostile backends.
    External backends must be isolated before secrets/held-out evaluation are used.
    """
    manifest_path = root / "manifest.json"
    if digest(manifest_path) != expected_sha256:
        raise ValueError("frozen manifest hash mismatch")
    manifest = Corpus.model_validate_json(manifest_path.read_text(encoding="utf-8")).model_dump(mode="json", by_alias=True)
    sources = []
    for case in manifest["cases"]:
        source = (root / case["file"]).resolve()
        if not source.is_relative_to(root.resolve()) or digest(source) != case["sha256"]:
            raise ValueError("source containment/integrity failure")
        if case["source_kind"] != "prerecorded" or case["synthetic"] is not True:
            raise ValueError("this evaluator supports synthetic prerecorded controls only")
        sources.append(source)
    output.mkdir(parents=True, exist_ok=False)
    retain(output / "protocol.json", {
        "manifest_sha256": expected_sha256, "frame_budget": manifest["frame_budget"],
        "inspection_budget": manifest["inspection_budget"],
        "max_seconds_per_case": manifest["max_seconds_per_case"],
        "gate": "absolute mean luminance difference > 20 between requested frames",
        "unit": "case-level pixel-change detection, NOT event/action recall",
        "fixed_fps": 1.0, "adaptive": "existing Watch escalation_for",
        "confidence_labels": "perception=decoded requested frames; transition=case pixel change; procedure=causal proof",
        "confidence_boundary": "Untrained constants; calibration is logging plumbing, not calibrated probabilities.",
        "code_sha256": {path.name: digest(path) for path in (
            Path(__file__), Path(__file__).resolve().parents[1] / "watch" / "inspection.py",
            Path(__file__).resolve().parents[1] / "watch" / "inspection_runtime.py",
            Path(__file__).resolve().parents[1] / "watch" / "seek.py",
            Path(__file__).resolve().parents[1] / "watch" / "core.py")},
    })
    results = []
    for policy in (FixedPolicy(), DeterministicWatchPolicy()):
        for case, source in zip(manifest["cases"], sources, strict=True):
            bundle = output / policy.name / case["id"]
            bundle.mkdir(parents=True)
            shutil.copyfile(source, bundle / "video.mkv")
            if digest(bundle / "video.mkv") != case["sha256"]:
                raise ValueError("copied source differs from frozen corpus")
            retain(bundle / "timeline.json", {
                "schema": "beast.watch.timeline/v3",
                "source": {"local_video": "video.mkv", "range": {
                    "start_seconds": 0, "end_seconds": 6, "start": "00:00", "end": "00:06"}},
                "sampling": {"height": 64}, "frames": [],
            })
            ctx = InspectionContext(source_interval=Interval(start_ms=0, end_ms=6000),
                                    candidate_interval=Interval(start_ms=2500, end_ms=3500),
                                    confidence=Confidence(perception=0.5, transition=0.5, procedure=0.0))
            start = time.perf_counter()
            decision = policy.decide(ctx)
            receipt = execute_inspection(bundle, ffmpeg, decision, ctx, manifest["frame_budget"],
                                         bundle / "inspection.json",
                                         fixed_fps=1.0 if isinstance(policy, FixedPolicy) else None,
                                         max_seconds=float(manifest["max_seconds_per_case"]),
                                         expected_source_sha256=case["sha256"])
            means = []
            refs = []
            for frame in receipt["frames"]:
                path = bundle / frame["file"]
                with Image.open(path) as image:
                    means.append(ImageStat.Stat(image.convert("L")).mean[0])
                refs.append(f"{frame['file']}#sha256={frame['sha256']}")
            pair = next(((i - 1, i) for i in range(1, len(means)) if abs(means[i] - means[i - 1]) > 20), None)
            gates = EvidenceGates(transition_passed=pair is not None,
                                  transition_evidence=tuple(refs[i] for i in pair) if pair else ())
            elapsed = time.perf_counter() - start
            truth = case["ground_truth"]
            scores = decision.confidence
            result = {
                "backend": policy.name, "case_id": case["id"], "stratum": case["stratum"],
                "source_kind": case["source_kind"], "source_sha256": case["sha256"],
                "evidence_class": gates.evidence_class, "gates": gates.model_dump(mode="json"),
                "confidence": scores.model_dump(), "inspections": 1,
                "frames": receipt["charged_frames"], "elapsed_seconds": elapsed,
                "provider_cost": 0, "provider_cost_unit": "USD", "gpu_calls": 0,
                "compute_budget_exceeded": elapsed > manifest["max_seconds_per_case"],
                "true_positive": gates.transition_passed and truth["pixel_transition"],
                "false_acceptance": gates.transition_passed and not truth["pixel_transition"],
                "miss": not gates.transition_passed and truth["pixel_transition"],
                "procedure_false_acceptance": gates.evidence_class == "verified_procedure_step" and not truth["causal_procedure"],
                "brier": {"perception": (scores.perception - bool(means)) ** 2,
                          "transition": (scores.transition - truth["pixel_transition"]) ** 2,
                          "procedure": (scores.procedure - truth["causal_procedure"]) ** 2},
                "inspection_receipt": (bundle / "inspection.result.json").relative_to(output).as_posix(),
            }
            retain(bundle / "evaluation.json", result)
            results.append(result)
    safety = not any(row["false_acceptance"] or row["procedure_false_acceptance"] or row["compute_budget_exceeded"] for row in results)
    report = {"schema": "beast.watch.inspection-evaluation/v1", "manifest_sha256": expected_sha256,
              "safety_gate_passed": safety, "results": results,
              "not_run": ["slow_vlm", "jev", "trained_local_policy", "live_capture", "real_training_video"],
              "claim": "Synthetic control extraction, receipt and evidence separation only.",
              "not_claimed": "No policy efficiency win, event recall, causal recovery or video-understanding result."}
    retain(output / "report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "evaluate"))
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        result = prepare(args.corpus, args.ffmpeg)
    else:
        if not args.manifest_sha256 or args.output is None:
            parser.error("evaluate requires --manifest-sha256 and --output")
        result = evaluate(args.corpus, args.manifest_sha256, args.output, args.ffmpeg)
    sys.stdout.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return 0 if result.get("safety_gate_passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
