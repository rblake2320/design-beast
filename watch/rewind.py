"""Bounded evidence-debt scheduling. Pixel surprise is not an action verdict."""
from __future__ import annotations

from typing import Annotated, Literal
from pydantic import Field
from .inspection import Contract, Confidence, InspectionDecision, Interval, Probability


class EvidenceDebt(Contract):
    control: Literal["unresolved"] = "unresolved"
    action: Literal["unresolved"] = "unresolved"
    reproducibility: Literal["untested"] = "untested"
    perception_confidence: Probability | None = None
    transition_confidence: Probability | None = None
    procedure_confidence: Probability | None = None


class ChangeSample(Contract):
    start_ms: Annotated[int, Field(ge=0)]
    end_ms: Annotated[int, Field(gt=0)]
    mean_absolute_difference: Annotated[float, Field(ge=0, le=255, allow_inf_nan=False)]


def request(interval: Interval, reason: str) -> InspectionDecision:
    return InspectionDecision(requested_action="increase_density", target_interval=interval,
        predicted_value_of_inspection=0.0,
        confidence=Confidence(perception=0.0, transition=0.0, procedure=0.0),
        uncertainty_reasons=(reason, "Zero confidence placeholders are uncalibrated, not evidence scores.",
                             "Forward replay checks sequence, not reproducibility."))


def rewind_window(result_ms: int, lookback_ms: int, duration_ms: int) -> Interval:
    if any(type(v) is not int for v in (result_ms, lookback_ms, duration_ms)):
        raise ValueError("timestamps must be integers")
    if not 0 < result_ms < duration_ms or not 500 <= lookback_ms <= 10000:
        raise ValueError("invalid result anchor or lookback")
    return Interval(start_ms=max(0, result_ms-lookback_ms), end_ms=result_ms)


def refinement(window: Interval, samples: tuple[ChangeSample, ...]) -> InspectionDecision | None:
    if not samples:
        return None
    for sample in samples:
        if not window.start_ms <= sample.start_ms < sample.end_ms <= window.end_ms:
            raise ValueError("change sample outside search window")
    # Tie-break closest to the observed consequence. Never call this causal proof.
    best = max(samples, key=lambda s: (s.mean_absolute_difference, s.end_ms))
    if best.mean_absolute_difference <= 0:
        return None
    return request(Interval(start_ms=best.start_ms, end_ms=best.end_ms),
                   "Refine highest measured pixel-change interval; action and control still unresolved.")


def budget_fps(interval: Interval, frames: int) -> float:
    if type(frames) is not int or not 2 <= frames <= 96 or interval.end_ms <= interval.start_ms:
        raise ValueError("invalid inspection budget or interval")
    return min(30.0, (frames-1)*1000/(interval.end_ms-interval.start_ms))
