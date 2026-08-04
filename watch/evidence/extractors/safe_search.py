"""
SafeSearch extractor — Google Cloud Vision SAFE_SEARCH_DETECTION.

This is a PRE-FILTER GATE, not an enrichment: run it before any other
extractor touches a frame, and record its verdict in provenance. Frames are
never silently dropped — a quarantined frame emits a quarantine event so the
review layer can see WHAT was excluded and WHY (silent truncation reads as
"covered everything" when it didn't).

FAIL-CLOSED: if the Vision call errors, the frame is quarantined as
unscreened, not passed through. Screening that fails open is not screening.

Piggybacks on the same images.annotate request as LANDMARK_DETECTION — add
SAFE_SEARCH_DETECTION to the feature list; it does not cost an extra call.
"""
from base import BaseExtractor

LIKELIHOOD_ORDER = [
    "UNKNOWN", "VERY_UNLIKELY", "UNLIKELY", "POSSIBLE", "LIKELY", "VERY_LIKELY",
]

_CATEGORIES = ("adult", "violence", "racy", "medical", "spoof")


def likelihood_at_least(value: str, threshold: str) -> bool:
    """UNKNOWN never satisfies a threshold — unknown is not evidence of safety."""
    if value == "UNKNOWN":
        return False
    return LIKELIHOOD_ORDER.index(value) >= LIKELIHOOD_ORDER.index(threshold)


class SafeSearchExtractor(BaseExtractor):
    name = "safe_search_detection"
    version = "1.0.0"

    def __init__(self, quarantine_thresholds: dict | None = None):
        # Default: quarantine on LIKELY+ adult/violence, POSSIBLE+ racy.
        # medical/spoof are recorded in the verdict but do not quarantine.
        self.quarantine_thresholds = quarantine_thresholds or {
            "adult": "LIKELY",
            "violence": "LIKELY",
            "racy": "POSSIBLE",
        }

    def extract(self, frame, source_id: str) -> list[dict]:
        """frame: dict with keys {timestamp_ms, image_path}."""
        try:
            likelihoods = self._call_vision_api(frame["image_path"])
        except Exception as exc:  # noqa: BLE001 — fail-closed by design
            return [self.make_event(
                source_id=source_id,
                start_ms=frame["timestamp_ms"],
                end_ms=frame["timestamp_ms"],
                modality="safety",
                kind="safe_search_unavailable",
                content={
                    "quarantined": True,
                    "reason": f"screening failed: {type(exc).__name__}",
                    "requires_human_approval": True,
                },
                confidence=0.0,
                review_state="uncertain",
                frame_refs=[frame["image_path"]],
            )]

        flagged = sorted(
            category
            for category, threshold in self.quarantine_thresholds.items()
            if likelihood_at_least(likelihoods.get(category, "UNKNOWN"), threshold)
        )
        unknown = sorted(
            category for category in self.quarantine_thresholds
            if likelihoods.get(category, "UNKNOWN") == "UNKNOWN"
        )
        quarantined = bool(flagged) or bool(unknown)
        return [self.make_event(
            source_id=source_id,
            start_ms=frame["timestamp_ms"],
            end_ms=frame["timestamp_ms"],
            modality="safety",
            kind="safe_search_quarantine" if quarantined else "safe_search_verdict",
            content={
                "quarantined": quarantined,
                "flagged_categories": flagged,
                "unscored_categories": unknown,
                "likelihoods": {c: likelihoods.get(c, "UNKNOWN") for c in _CATEGORIES},
                "requires_human_approval": quarantined,
            },
            confidence=1.0 if not unknown else 0.0,
            review_state="uncertain" if quarantined else "observed",
            frame_refs=[frame["image_path"]],
        )]

    def _call_vision_api(self, image_path: str) -> dict:
        """Return {category: LIKELIHOOD_STRING} for adult/violence/racy/medical/spoof."""
        raise NotImplementedError(
            "Wire Google Cloud Vision safeSearchAnnotation here "
            "(share the images.annotate request with LANDMARK_DETECTION)"
        )
