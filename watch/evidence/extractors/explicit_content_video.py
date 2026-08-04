"""
Explicit-content extractor for VIDEO segments — Google Video Intelligence
EXPLICIT_CONTENT_DETECTION. The video-native counterpart of safe_search.py:
per-frame pornography likelihood across a segment. Belongs next to the
google_video_intelligence OCR backend, for the same pre-filter reason —
screen recordings get screened before entering a training pipeline or
reaching a human reviewer.

FAIL-CLOSED: an API error quarantines the whole segment as unscreened.
Quarantine emits an event (never a silent drop) so review can see what was
excluded and why.
"""
from base import BaseExtractor
from safe_search import likelihood_at_least


class ExplicitContentVideoExtractor(BaseExtractor):
    name = "explicit_content_video"
    version = "1.0.0"

    def __init__(self, quarantine_threshold: str = "LIKELY"):
        self.quarantine_threshold = quarantine_threshold

    def extract(self, segment, source_id: str) -> list[dict]:
        """segment: dict with keys {start_ms, end_ms, video_path}."""
        try:
            frames = self._call_video_intelligence(
                segment["video_path"], segment["start_ms"], segment["end_ms"]
            )
        except Exception as exc:  # noqa: BLE001 — fail-closed by design
            return [self.make_event(
                source_id=source_id,
                start_ms=segment["start_ms"],
                end_ms=segment["end_ms"],
                modality="safety",
                kind="explicit_content_unavailable",
                content={
                    "quarantined": True,
                    "reason": f"screening failed: {type(exc).__name__}",
                    "requires_human_approval": True,
                },
                confidence=0.0,
                review_state="uncertain",
            )]

        flagged = [
            f for f in frames
            if likelihood_at_least(
                f.get("pornography_likelihood", "UNKNOWN"), self.quarantine_threshold
            )
        ]
        unknown = [
            f for f in frames
            if f.get("pornography_likelihood", "UNKNOWN") == "UNKNOWN"
        ]
        quarantined = bool(flagged) or bool(unknown) or not frames
        return [self.make_event(
            source_id=source_id,
            start_ms=segment["start_ms"],
            end_ms=segment["end_ms"],
            modality="safety",
            kind="explicit_content_quarantine" if quarantined
            else "explicit_content_verdict",
            content={
                "quarantined": quarantined,
                "frames_scored": len(frames),
                "frames_flagged": len(flagged),
                "frames_unscored": len(unknown),
                "flagged_timestamps_ms": [f["timestamp_ms"] for f in flagged],
                "requires_human_approval": quarantined,
            },
            confidence=1.0 if frames and not unknown else 0.0,
            review_state="uncertain" if quarantined else "observed",
        )]

    def _call_video_intelligence(
        self, video_path: str, start_ms: int, end_ms: int
    ) -> list[dict]:
        """Return [{timestamp_ms, pornography_likelihood}] per sampled frame."""
        raise NotImplementedError(
            "Wire Google Video Intelligence EXPLICIT_CONTENT_DETECTION here"
        )
