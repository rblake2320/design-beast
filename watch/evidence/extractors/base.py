"""
Base extractor interface. Every Watch extractor (OCR, ASR, pose, landmark,
UI-state, scene-change) MUST subclass this and emit EvidenceEvent-shaped
dicts. This is what stops every new capability from inventing its own JSON.
"""
from abc import ABC, abstractmethod
import hashlib
import uuid


class BaseExtractor(ABC):
    name: str = "base"
    version: str = "0.0.0"

    @abstractmethod
    def extract(self, frame_or_segment, source_id: str) -> list[dict]:
        """Returns a list of EvidenceEvent-shaped dicts."""
        raise NotImplementedError

    def make_event(self, source_id, start_ms, end_ms, modality, content,
                    confidence, bbox=None, geo=None, kind=None,
                    review_state="observed", frame_refs=None) -> dict:
        return {
            "event_id": str(uuid.uuid4()),
            "source_id": source_id,
            "source_time_start_ms": start_ms,
            "source_time_end_ms": end_ms,
            "modality": modality,
            "kind": kind,
            "content": content,
            "bbox": bbox,
            "geo": geo,
            "confidence": confidence,
            "extractor": {"name": self.name, "version": self.version,
                          "config_hash": self._config_hash()},
            "frame_refs": frame_refs or [],
            "review_state": review_state,
            "reviewer": None,
        }

    def _config_hash(self) -> str:
        return hashlib.sha256(f"{self.name}{self.version}".encode()).hexdigest()[:12]
