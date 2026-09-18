"""Replaceable inspection recommendations. No policy can promote evidence."""
from __future__ import annotations

from typing import Annotated, Literal, Protocol, Self
from fractions import Fraction
import math

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .seek import SEEK_LEVELS, escalation_for, seek_times

Probability = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
Milliseconds = Annotated[int, Field(strict=True, ge=0)]
Action = Literal["seek_before", "seek_after", "increase_density", "expand_region",
                 "run_ocr", "track_element", "compare_states", "request_slow_review",
                 "stop_inspection"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Interval(Contract):
    start_ms: Milliseconds
    end_ms: Milliseconds

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end_ms < self.start_ms:
            raise ValueError("reversed interval")
        return self


class BoundingBox(Contract):
    """Normalized source coordinates, not enhanced/cropped-image coordinates."""
    x: Probability
    y: Probability
    width: Annotated[float, Field(strict=True, gt=0, le=1, allow_inf_nan=False)]
    height: Annotated[float, Field(strict=True, gt=0, le=1, allow_inf_nan=False)]

    @model_validator(mode="after")
    def contained(self) -> Self:
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("region exceeds source")
        return self


class Confidence(Contract):
    perception: Probability
    transition: Probability
    procedure: Probability


class OptionScore(Contract):
    action: Action
    score: Probability


class OptionReadout(Contract):
    """SemIf-inspired audit metadata; conditional scores are NOT evidence confidence."""
    backend: Annotated[str, Field(min_length=1)]
    model_revision: Annotated[str, Field(min_length=1)]
    prompt_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    scores: Annotated[tuple[OptionScore, ...], Field(min_length=2)]
    input_tokens: Annotated[int, Field(strict=True, ge=1)]
    elapsed_seconds: Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
    probability_status: Literal["uncalibrated_conditional_option_score"] = "uncalibrated_conditional_option_score"

    @model_validator(mode="after")
    def distribution(self) -> Self:
        if len({item.action for item in self.scores}) != len(self.scores):
            raise ValueError("duplicate option action")
        if not math.isclose(sum(item.score for item in self.scores), 1.0, abs_tol=1e-6):
            raise ValueError("option scores must sum to one")
        return self


class InspectionDecision(Contract):
    schema_version: Literal["beast.watch.inspection/v1"] = "beast.watch.inspection/v1"
    requested_action: Action
    target_interval: Interval
    target_regions: tuple[BoundingBox, ...] = ()
    predicted_value_of_inspection: Probability
    confidence: Confidence
    uncertainty_reasons: tuple[str, ...]
    option_readout: OptionReadout | None = None


class InspectionContext(Contract):
    """Public observations only: no source path, case labels or ground truth."""
    source_interval: Interval
    candidate_interval: Interval
    confidence: Confidence
    missing_evidence: bool = True
    rapid_action: bool = False
    completed_inspections: Annotated[int, Field(strict=True, ge=0)] = 0

    @model_validator(mode="after")
    def contained(self) -> Self:
        if not (self.source_interval.start_ms <= self.candidate_interval.start_ms
                <= self.candidate_interval.end_ms <= self.source_interval.end_ms):
            raise ValueError("candidate outside source")
        return self


class InspectionPolicy(Protocol):
    name: str

    def decide(self, context: InspectionContext) -> InspectionDecision: ...


class DeterministicWatchPolicy:
    """Adapter for existing Watch escalation; no new visual interpretation."""
    name = "watch-deterministic-v1"

    def decide(self, context: InspectionContext) -> InspectionDecision:
        level = escalation_for(context.confidence.transition,
                               context.missing_evidence, context.rapid_action)
        center = (context.candidate_interval.start_ms + context.candidate_interval.end_ms) // 2
        preset = SEEK_LEVELS[level or 1]
        interval = Interval(start_ms=max(context.source_interval.start_ms,
                                         center - int(preset.before * 1000)),
                            end_ms=min(context.source_interval.end_ms,
                                       center + int(preset.after * 1000)))
        return InspectionDecision(
            requested_action="stop_inspection" if level is None or context.completed_inspections else "increase_density",
            target_interval=interval, predicted_value_of_inspection=0.0 if level is None else 0.5,
            confidence=context.confidence,
            uncertainty_reasons=("Causality and reproducibility require independent evidence.",))


class SeekPlan(Contract):
    level: Annotated[int, Field(strict=True, ge=1, le=3)]
    center_seconds: float
    before_seconds: float
    after_seconds: float
    fps: float
    direction: Literal["back", "forward", "both"]
    timestamps: tuple[float, ...]


def plan_seek(decision: InspectionDecision, context: InspectionContext,
              remaining_frames: int, *, fixed_fps: float | None = None) -> SeekPlan | None:
    """Fail closed before Watch touches a bundle. Unsupported actions stay unexecuted."""
    if type(remaining_frames) is not int or remaining_frames < 0:
        raise ValueError("invalid budget")
    interval = decision.target_interval
    source = context.source_interval
    if not source.start_ms <= interval.start_ms <= interval.end_ms <= source.end_ms:
        raise ValueError("request outside source")
    if decision.requested_action == "stop_inspection":
        return None
    if decision.target_regions or decision.requested_action not in (
            "seek_before", "seek_after", "increase_density"):
        raise ValueError("inspection executor unavailable for requested action/region")
    level = escalation_for(context.confidence.transition, context.missing_evidence,
                           context.rapid_action) or 1
    fps = SEEK_LEVELS[level].fps if fixed_fps is None else fixed_fps
    if isinstance(fps, bool) or not math.isfinite(fps) or not 0 < fps <= 30:
        raise ValueError("invalid sampling rate")
    duration_ms = interval.end_ms - interval.start_ms
    divisor = 2000 if decision.requested_action in ("seek_before", "seek_after") else 1000
    minimum_count = int(Fraction(duration_ms, divisor) * Fraction(fps)) + 1
    if minimum_count > remaining_frames:
        raise ValueError("inspection exceeds remaining frame budget")
    center = (interval.start_ms + interval.end_ms) / 2000
    before = center - interval.start_ms / 1000
    after = interval.end_ms / 1000 - center
    direction = {"seek_before": "back", "seek_after": "forward"}.get(decision.requested_action, "both")
    timestamps = tuple(seek_times(center, source.start_ms / 1000, source.end_ms / 1000,
                                 before=before, after=after, fps=fps, direction=direction))
    if len(timestamps) > remaining_frames:
        raise ValueError("inspection exceeds remaining frame budget")
    return SeekPlan(level=level, center_seconds=center, before_seconds=before,
                    after_seconds=after, fps=fps, direction=direction, timestamps=timestamps)


class EvidenceGates(Contract):
    """Watch-owned gate results, NEVER policy probability thresholds."""
    transition_passed: bool
    action_supports_cause: bool = False
    reproducibility_passed: bool = False
    transition_evidence: tuple[str, ...] = ()
    causal_evidence: tuple[str, ...] = ()
    reproducibility_evidence: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_references(self) -> Self:
        for passed, refs in ((self.transition_passed, self.transition_evidence),
                             (self.action_supports_cause, self.causal_evidence),
                             (self.reproducibility_passed, self.reproducibility_evidence)):
            if passed and (not refs or any(not ref.strip() for ref in refs)):
                raise ValueError("passed gates require independent evidence references")
        return self

    @property
    def evidence_class(self) -> str:
        if self.transition_passed and self.action_supports_cause and self.reproducibility_passed:
            return "verified_procedure_step"
        if self.transition_passed:
            return "evidence_supported_transition"
        return "uncertain_observation"
