"""
Scene-change / adaptive frame sampler. Wraps PySceneDetect's content-aware
detector to avoid OCR-ing near-identical consecutive frames. Reuses
Beast's existing adaptive-sampling philosophy (109 adaptive frames /
65 unique CUDA-indexed frames from the real proof run) rather than
introducing a second sampling implementation.
"""
from base import BaseExtractor


class SceneChangeExtractor(BaseExtractor):
    name = "scene_change_pyscenedetect"
    version = "1.0.0"

    def extract(self, video_path: str, source_id: str) -> list[dict]:
        cuts = self._detect_cuts(video_path)
        events = []
        for start_ms, end_ms in cuts:
            events.append(self.make_event(
                source_id=source_id,
                start_ms=start_ms,
                end_ms=end_ms,
                modality="scene_change",
                kind="content_aware_cut",
                content=None,
                confidence=1.0,
                review_state="observed",
            ))
        return events

    def _detect_cuts(self, video_path: str) -> list[tuple]:
        raise NotImplementedError("Wire scenedetect.detect() with ContentDetector here")
