"""A pixel-state adapter to the existing recommendation-only Watch policy contract."""
from __future__ import annotations

import math

from .inspection import BoundingBox, InspectionContext, InspectionDecision
from .visual_state import VisualState


class PixelInspectionPolicy:
    name = "watch-pixel-state-v1"

    def __init__(self, state: VisualState, *, ui_region_count: int = 0,
                 temporal_change_score: float = 0.0) -> None:
        if type(ui_region_count) is not int or not 0 <= ui_region_count <= 300:
            raise ValueError("invalid UI region count")
        if type(temporal_change_score) not in (int, float) or not math.isfinite(temporal_change_score) or not -1e-5 <= temporal_change_score <= 2.00001:
            raise ValueError("invalid temporal change score")
        self.state = state
        self.ui_region_count = ui_region_count
        self.temporal_change_score = temporal_change_score

    def decide(self, context: InspectionContext) -> InspectionDecision:
        if not context.candidate_interval.start_ms <= self.state.clip_ms <= context.candidate_interval.end_ms:
            raise ValueError("pixel state outside candidate interval")
        width, height = self.state.dimensions
        regions = tuple(BoundingBox(x=x/width, y=y/height, width=w/width, height=h/height)
                        for x, y, w, h in self.state.changed_regions[:8])
        if context.completed_inspections:
            action = "stop_inspection"
        elif self.state.tracking_reset or not self.state.motion_tracks:
            action = "increase_density"
        elif self.ui_region_count and not self.state.text_elements:
            action = "run_ocr"
        elif self.temporal_change_score > .1:
            action = "request_slow_review"
        elif regions:
            action = "compare_states"
        else:
            action = "request_slow_review" if context.missing_evidence else "stop_inspection"
        return InspectionDecision(requested_action=action, target_interval=context.candidate_interval,
            target_regions=regions, predicted_value_of_inspection=0.0,
            confidence=context.confidence,
            uncertainty_reasons=self.state.uncertainty + ("Scheduling heuristic is uncalibrated; no evidence promotion.",))
