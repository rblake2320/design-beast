"""
OCR extractor. Two selectable backends: local NVIDIA NeMo Retriever OCR
(runs on DGX Spark, no network required) or Google Video Intelligence
TEXT_DETECTION (cloud). Emits EvidenceEvent dicts via BaseExtractor.

CORRECTION FROM PRIOR DRAFT: this class only extracts text. It must never
be reused as a generic object/hand/reflection detector — different models,
different training targets. Only the output SHAPE is shared.
"""
from base import BaseExtractor


class OCRExtractor(BaseExtractor):
    name = "ocr"

    def __init__(self, backend: str = "nemo_retriever_local", version: str = "1.0.0"):
        self.backend = backend
        self.version = version

    def extract(self, frame, source_id: str) -> list[dict]:
        """frame: dict with keys {timestamp_ms, image_path}.
        Wire in real backend call here — this defines the contract only."""
        raw_detections = self._call_backend(frame["image_path"])
        events = []
        for det in raw_detections:
            events.append(self.make_event(
                source_id=source_id,
                start_ms=frame["timestamp_ms"],
                end_ms=frame["timestamp_ms"],
                modality="screen_text",
                kind=det.get("kind", "unknown_text"),
                content=det["text"],
                confidence=det["confidence"],
                bbox=det.get("bbox"),
                frame_refs=[frame["image_path"]],
            ))
        return events

    def _call_backend(self, image_path: str) -> list[dict]:
        if self.backend == "nemo_retriever_local":
            return self._call_nemo(image_path)
        elif self.backend == "google_video_intelligence":
            return self._call_google(image_path)
        raise ValueError(f"Unknown OCR backend: {self.backend}")

    def _call_nemo(self, image_path: str) -> list[dict]:
        raise NotImplementedError("Wire NVIDIA NeMo Retriever OCR NIM endpoint here")

    def _call_google(self, image_path: str) -> list[dict]:
        raise NotImplementedError("Wire Google Video Intelligence TEXT_DETECTION here")
