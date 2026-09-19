"""Evidence-qualified instruction triage; never a procedure publication authority."""
from __future__ import annotations
from typing import Annotated, Literal, Self
from pydantic import Field, model_validator
from .inspection import Contract
from .training_draft import FrameRef


class InstructionUnit(Contract):
    unit_id: Annotated[str, Field(min_length=1, max_length=100)]
    kind: Literal["observable_action", "observable_result", "ambiguous_transition", "scene_change"]
    start_ms: Annotated[int, Field(ge=0)]
    end_ms: Annotated[int, Field(gt=0)]
    sentence: Annotated[str, Field(min_length=1, max_length=500)]
    frame_refs: Annotated[tuple[FrameRef, ...], Field(min_length=1, max_length=96)]
    control_evidence: Annotated[str, Field(max_length=1000)] = ""
    action_evidence: Annotated[str, Field(max_length=1000)] = ""
    result_evidence: Annotated[str, Field(max_length=1000)] = ""
    reviewer: Annotated[str, Field(max_length=100)] = ""
    verdict: Literal["pending", "accepted", "rejected"] = "pending"
    perception_confidence: Annotated[float, Field(ge=0, le=1)] | None = None
    transition_confidence: Annotated[float, Field(ge=0, le=1)] | None = None
    procedure_confidence: Annotated[float, Field(ge=0, le=1)] | None = None

    @model_validator(mode="after")
    def contained(self) -> Self:
        if self.end_ms-self.start_ms < 500 or not self.sentence.strip():
            raise ValueError("invalid instruction interval or sentence")
        if any(not self.start_ms <= ref.clip_ms <= self.end_ms for ref in self.frame_refs):
            raise ValueError("evidence outside instruction interval")
        if self.verdict != "pending" and not self.reviewer.strip():
            raise ValueError("review verdict needs named reviewer")
        return self


def gate(unit: InstructionUnit) -> dict[str, object]:
    decision = "review_required"
    reason = "classification and evidence need semantic review"
    if unit.kind == "scene_change":
        decision, reason = "omit", "no declared instructional value"
    elif unit.verdict == "rejected":
        decision, reason = "needs_author_annotation", "reviewer rejected the proposed instruction"
    elif unit.verdict == "accepted" and unit.kind == "observable_action":
        if all(text.strip() for text in (unit.control_evidence, unit.action_evidence, unit.result_evidence)):
            decision, reason = "eligible_draft", "reviewed control, action and result evidence declared"
        else:
            decision, reason = "needs_recapture", "causal action chain missing; a changed state alone is insufficient"
    elif unit.verdict == "accepted" and unit.kind == "observable_result" and unit.result_evidence.strip():
        decision, reason = "eligible_draft", "reviewed result description only; do not imply its cause"
    return {"unit_id": unit.unit_id, "decision": decision, "reason": reason,
        "verified_procedure": False, "publication_allowed": False}
