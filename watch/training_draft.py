"""Draft-only source interval contracts. Editorial text is not procedure proof."""
from __future__ import annotations

from typing import Annotated, Literal, Self
from pydantic import Field, model_validator
from .inspection import Contract


class FrameRef(Contract):
    clip_ms: Annotated[int, Field(ge=0)]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class DraftStep(Contract):
    start_ms: Annotated[int, Field(ge=0)]
    end_ms: Annotated[int, Field(gt=0)]
    caption: Annotated[str, Field(min_length=1, max_length=500)]
    frame_refs: Annotated[tuple[FrameRef, ...], Field(min_length=1, max_length=96)]
    review_state: Literal["uncertain"]
    requires_human_approval: Literal[True]

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if self.end_ms-self.start_ms < 500 or not self.caption.strip():
            raise ValueError("draft interval must last >=500ms and caption must not be blank")
        if any(not self.start_ms <= f.clip_ms <= self.end_ms for f in self.frame_refs):
            raise ValueError("frame outside draft interval")
        return self


class TrainingDraft(Contract):
    schema_version: Literal["beast.watch.training-draft/v1"]
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    source_duration_ms: Annotated[int, Field(gt=0)]
    visual_policy: Literal["original_source_only"]
    publication_allowed: Literal[False]
    steps: Annotated[tuple[DraftStep, ...], Field(min_length=1, max_length=50)]

    @model_validator(mode="after")
    def contained(self) -> Self:
        if any(step.end_ms > self.source_duration_ms for step in self.steps):
            raise ValueError("draft exceeds source duration")
        return self
