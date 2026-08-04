"""
Landmark extractor — Google Cloud Vision LANDMARK_DETECTION. Returns
landmark name, lat/lng, bbox. This is ONE clue signal only — never treat
a single landmark match as confirmed location. See review/evidence_gate.py
for the 2-independent-clue enforcement.
"""
from base import BaseExtractor


class LandmarkExtractor(BaseExtractor):
    name = "landmark_detection"
    version = "1.0.0"

    def extract(self, frame, source_id: str) -> list[dict]:
        raw = self._call_vision_api(frame["image_path"])
        events = []
        for lm in raw:
            events.append(self.make_event(
                source_id=source_id,
                start_ms=frame["timestamp_ms"],
                end_ms=frame["timestamp_ms"],
                modality="landmark",
                kind="named_landmark",
                content=lm["description"],
                confidence=lm["score"],
                bbox=lm.get("bbox"),
                geo=lm.get("geo"),
                review_state="observed",
                frame_refs=[frame["image_path"]],
            ))
        return events

    def _call_vision_api(self, image_path: str) -> list[dict]:
        raise NotImplementedError("Wire Google Cloud Vision landmarkAnnotation call here")
