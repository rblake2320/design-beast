"""
UI-state / procedure classifier. This is the piece that turns raw OCR +
scene-change events into an actual learnable procedure step, per the
council's 'screen procedure recovery' recommendation. Classifies:
application identity, before/after UI state, user action type
(click/type/select/drag/menu), command entered, result, error->repair.
"""
from base import BaseExtractor


class UIStateExtractor(BaseExtractor):
    name = "ui_state_classifier"
    version = "1.0.0"

    ACTION_TYPES = ["click", "type", "select", "drag", "menu_navigate",
                    "command_entered", "error_observed", "result_observed"]

    def extract(self, frame_window: list, source_id: str) -> list[dict]:
        """frame_window: list of consecutive frames + their OCR events,
        used to infer a single UI action across time (not one frame)."""
        action = self._classify_window(frame_window)
        if action is None:
            return []
        return [self.make_event(
            source_id=source_id,
            start_ms=frame_window[0]["timestamp_ms"],
            end_ms=frame_window[-1]["timestamp_ms"],
            modality="ui_state",
            kind=action["action_type"],
            content=action["description"],
            confidence=action["confidence"],
            review_state="inferred",
            frame_refs=[f["image_path"] for f in frame_window],
        )]

    def _classify_window(self, frame_window: list) -> dict | None:
        raise NotImplementedError("Wire temporal UI-action classifier here — "
                                   "requires a frame WINDOW, not a single frame")
