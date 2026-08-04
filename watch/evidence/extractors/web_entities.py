"""
Web/entity detection extractor — Google Cloud Vision WEB_DETECTION.

This is the capability that answers "where else does this image appear
online" — distinct from LANDMARK_DETECTION (which only knows famous places)
and the signal that usually breaks open a non-famous location.

SCENES AND PLACES, NOT PEOPLE. Reverse-searching imagery of identifiable
people is person-tracking, not geolocation. This extractor therefore
requires each frame to have been screened for people BEFORE the web call:

- frame["contains_person"] is False  -> API call allowed
- frame["contains_person"] is True   -> call REFUSED; human-gated event
- flag missing (unscreened)          -> call REFUSED by default (fail-closed)

Pass require_person_screening=False only for pipelines whose sources are
known person-free by construction (e.g. synthetic renders).

Like landmark: every emitted match is ONE clue signal only — the
2-independent-clue gate in review/evidence_gate.py decides location claims.
"""
import os
from pathlib import Path

from base import BaseExtractor
from watch.evidence.google_vision_client import GoogleVisionClient


class WebDetectionExtractor(BaseExtractor):
    name = "web_detection"
    version = "1.0.0"

    def __init__(
        self,
        require_person_screening: bool = True,
        max_results: int = 10,
        *,
        api_key: str | None = None,
        authorize_cloud_call: bool = False,
        vision_client: GoogleVisionClient | None = None,
    ):
        self.require_person_screening = require_person_screening
        self.max_results = max_results
        self.authorize_cloud_call = authorize_cloud_call
        self.vision_client = vision_client or GoogleVisionClient(
            api_key=api_key or os.environ.get("GOOGLE_CLOUD_VISION_API_KEY"),
            max_results=max_results,
        )

    def extract(self, frame, source_id: str) -> list[dict]:
        """frame: dict with keys {timestamp_ms, image_path, contains_person?}."""
        blocked_reason = self._person_boundary_block(frame)
        if blocked_reason:
            return [self.make_event(
                source_id=source_id,
                start_ms=frame["timestamp_ms"],
                end_ms=frame["timestamp_ms"],
                modality="web_match",
                kind="web_detection_blocked",
                content={
                    "blocked": True,
                    "reason": blocked_reason,
                    "requires_human_approval": True,
                },
                confidence=0.0,
                review_state="uncertain",
                frame_refs=[frame["image_path"]],
            )]

        try:
            raw = self._call_vision_api(frame["image_path"])
        except Exception as exc:  # noqa: BLE001 - fail-closed by design
            return [self.make_event(
                source_id=source_id,
                start_ms=frame["timestamp_ms"],
                end_ms=frame["timestamp_ms"],
                modality="web_match",
                kind="web_detection_unavailable",
                content={
                    "blocked": True,
                    "reason": f"web detection failed: {type(exc).__name__}",
                    "requires_human_approval": True,
                },
                confidence=0.0,
                review_state="uncertain",
                frame_refs=[frame["image_path"]],
            )]
        events = []
        for entity in raw.get("web_entities", [])[: self.max_results]:
            if not str(entity.get("description", "")).strip():
                continue
            events.append(self.make_event(
                source_id=source_id,
                start_ms=frame["timestamp_ms"],
                end_ms=frame["timestamp_ms"],
                modality="web_match",
                kind="web_entity",
                content=entity["description"],
                confidence=entity.get("score", 0.0),
                review_state="inferred",
                frame_refs=[frame["image_path"]],
            ))
        for page in raw.get("pages_with_matching_images", [])[: self.max_results]:
            events.append(self.make_event(
                source_id=source_id,
                start_ms=frame["timestamp_ms"],
                end_ms=frame["timestamp_ms"],
                modality="web_match",
                kind="matching_page",
                content={"url": page["url"], "title": page.get("title", "")},
                confidence=1.0 if page.get("full_match") else 0.5,
                review_state="inferred",
                frame_refs=[frame["image_path"]],
            ))
        for match_kind, confidence in (
            ("full_matching_images", 1.0),
            ("partial_matching_images", 0.8),
        ):
            for url in raw.get(match_kind, [])[: self.max_results]:
                events.append(self.make_event(
                    source_id=source_id,
                    start_ms=frame["timestamp_ms"],
                    end_ms=frame["timestamp_ms"],
                    modality="web_match",
                    kind=match_kind.removesuffix("s"),
                    content={"url": url},
                    confidence=confidence,
                    review_state="inferred",
                    frame_refs=[frame["image_path"]],
                ))
        for url in raw.get("visually_similar_images", [])[: self.max_results]:
            events.append(self.make_event(
                source_id=source_id,
                start_ms=frame["timestamp_ms"],
                end_ms=frame["timestamp_ms"],
                modality="web_match",
                kind="similar_image",
                content={"url": url},
                confidence=0.3,  # similarity is the weakest clue class
                review_state="inferred",
                frame_refs=[frame["image_path"]],
            ))
        return events

    def _person_boundary_block(self, frame) -> str | None:
        if not self.require_person_screening:
            return None
        if "contains_person" not in frame:
            return "frame not screened for people; web detection is fail-closed"
        if frame["contains_person"]:
            return "frame contains a person; reverse search of people is refused"
        return None

    def _call_vision_api(self, image_path: str) -> dict:
        """Return {web_entities: [{description, score}],
        pages_with_matching_images: [{url, title, full_match}],
        visually_similar_images: [url, ...]}."""
        result = self.vision_client.request(
            "WEB_DETECTION",
            Path(image_path).read_bytes(),
            authorize_cloud_call=self.authorize_cloud_call,
        )
        web = result.get("webDetection")
        if not isinstance(web, dict):
            raise ValueError("Google Vision Web Detection result is missing")
        return {
            "web_entities": [
                {"description": row.get("description", ""),
                 "score": row.get("score", 0.0)}
                for row in web.get("webEntities", []) if isinstance(row, dict)
            ],
            "pages_with_matching_images": [
                {"url": row.get("url", ""), "title": row.get("pageTitle", ""),
                 "full_match": bool(row.get("fullMatchingImages"))}
                for row in web.get("pagesWithMatchingImages", [])
                if isinstance(row, dict) and row.get("url")
            ],
            "full_matching_images": [
                row["url"] for row in web.get("fullMatchingImages", [])
                if isinstance(row, dict) and row.get("url")
            ],
            "partial_matching_images": [
                row["url"] for row in web.get("partialMatchingImages", [])
                if isinstance(row, dict) and row.get("url")
            ],
            "visually_similar_images": [
                row["url"] for row in web.get("visuallySimilarImages", [])
                if isinstance(row, dict) and row.get("url")
            ],
        }
