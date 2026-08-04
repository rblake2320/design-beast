"""Optional Google Cloud Vision SafeSearch-first web detection adapter.

The adapter never fetches URLs returned by Web Detection. Live calls require an
explicit authorization flag and a source manifest that allows cloud analysis.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests

from .contracts import (
    EvidenceContractError,
    _file_sha256,
    _fingerprint,
    _require,
    _require_authorized_use,
    make_evidence_event,
    validate_evidence_event,
)

VISION_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"
LIKELIHOODS = {
    "UNKNOWN": 0,
    "VERY_UNLIKELY": 1,
    "UNLIKELY": 2,
    "POSSIBLE": 3,
    "LIKELY": 4,
    "VERY_LIKELY": 5,
}
BLOCK_CATEGORIES = {"adult", "violence", "racy"}
Requester = Callable[[str, bytes], dict[str, Any]]


class GoogleVisionExtractor:
    """Run SafeSearch, then optionally Web Detection, on exact local bytes."""

    def __init__(
        self,
        *,
        api_key: str | None,
        requester: Requester | None = None,
        timeout_seconds: float = 30.0,
        safe_search_threshold: str = "LIKELY",
        max_results: int = 20,
    ) -> None:
        _require(safe_search_threshold in LIKELIHOODS,
                 "invalid SafeSearch threshold")
        _require(1 <= max_results <= 50, "Google Vision max_results must be 1..50")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.safe_search_threshold = safe_search_threshold
        self.max_results = max_results
        self._requester = requester or self._request_live

    def _request_live(self, feature: str, content: bytes) -> dict[str, Any]:
        _require(bool(self.api_key),
                 "Google Cloud Vision API key is required for a live call")
        payload = {
            "requests": [{
                "image": {"content": base64.b64encode(content).decode("ascii")},
                "features": [{"type": feature, "maxResults": self.max_results}],
            }],
        }
        try:
            response = requests.post(
                VISION_ENDPOINT,
                params={"key": self.api_key},
                headers={"Content-Type": "application/json; charset=utf-8"},
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise EvidenceContractError(
                f"Google Vision request failed: {type(exc).__name__}") from exc
        _require(isinstance(body, dict), "Google Vision response must be an object")
        responses = body.get("responses")
        _require(isinstance(responses, list) and len(responses) == 1,
                 "Google Vision response must contain exactly one image result")
        result = responses[0]
        if isinstance(result.get("error"), dict):
            raise EvidenceContractError(
                f"Google Vision error: {result['error'].get('message', 'unknown error')}")
        return result

    def analyze(
        self,
        image_path: Path,
        manifest: dict[str, Any],
        parent_event: dict[str, Any],
        *,
        authorize_cloud_call: bool,
        allow_sensitive_review: bool = False,
    ) -> dict[str, Any]:
        _require_authorized_use(manifest, "cloud_analysis")
        _require(authorize_cloud_call,
                 "explicit authorization is required for a Google Vision cloud call")
        validate_evidence_event(parent_event, manifest)
        image_path = Path(image_path).resolve()
        _require(image_path.is_file(), f"image file does not exist: {image_path}")
        image_hash = _file_sha256(image_path)
        parent_hashes = {
            ref.get("sha256") for ref in parent_event.get("artifact_refs", [])
        }
        _require(image_hash in parent_hashes,
                 "image hash is not bound by the parent evidence event")
        content = image_path.read_bytes()
        config_fp = _fingerprint({
            "endpoint": VISION_ENDPOINT,
            "safe_search_threshold": self.safe_search_threshold,
            "max_results": self.max_results,
        })

        safe_result = self._requester("SAFE_SEARCH_DETECTION", content)
        if isinstance(safe_result.get("error"), dict):
            raise EvidenceContractError(
                f"Google Vision error: {safe_result['error'].get('message', 'unknown error')}")
        annotations = safe_result.get("safeSearchAnnotation")
        _require(isinstance(annotations, dict),
                 "Google Vision SafeSearch annotation is missing")
        normalized = {
            key: str(annotations.get(key, "UNKNOWN"))
            for key in ("adult", "spoof", "medical", "violence", "racy")
        }
        for key, value in normalized.items():
            _require(value in LIKELIHOODS,
                     f"unknown Google Vision likelihood for {key}: {value!r}")
        threshold = LIKELIHOODS[self.safe_search_threshold]
        reasons = sorted(
            key for key in BLOCK_CATEGORIES
            if LIKELIHOODS[normalized[key]] >= threshold
        )
        safe_event = make_evidence_event(
            manifest,
            start_ms=parent_event["source_time"]["start_ms"],
            end_ms=parent_event["source_time"]["end_ms"],
            modality="safety_assessment",
            kind="google_safe_search",
            content=json.dumps(normalized, sort_keys=True),
            confidence=1.0,
            extractor={"name": "google_cloud_vision",
                       "version": "v1/SAFE_SEARCH_DETECTION",
                       "config_fingerprint": config_fp},
            review_state="inferred",
            parent_event_ids=[parent_event["event_id"]],
        )
        if reasons and not allow_sensitive_review:
            return {
                "events": [safe_event],
                "gate": {"blocked": True, "reasons": reasons,
                         "web_detection_ran": False},
            }

        web_result = self._requester("WEB_DETECTION", content)
        if isinstance(web_result.get("error"), dict):
            raise EvidenceContractError(
                f"Google Vision error: {web_result['error'].get('message', 'unknown error')}")
        web = web_result.get("webDetection")
        _require(isinstance(web, dict), "Google Vision Web Detection result is missing")
        parsed = self._bounded_web_result(web)
        entity_scores = [item["score"] for item in parsed["web_entities"]]
        confidence = min(1.0, max(entity_scores, default=0.0))
        web_event = make_evidence_event(
            manifest,
            start_ms=parent_event["source_time"]["start_ms"],
            end_ms=parent_event["source_time"]["end_ms"],
            modality="web_detection",
            kind="google_web_references",
            content=json.dumps(parsed, sort_keys=True),
            confidence=confidence,
            extractor={"name": "google_cloud_vision",
                       "version": "v1/WEB_DETECTION",
                       "config_fingerprint": config_fp},
            review_state="inferred",
            parent_event_ids=[parent_event["event_id"], safe_event["event_id"]],
        )
        return {
            "events": [safe_event, web_event],
            "gate": {"blocked": False, "reasons": reasons,
                     "web_detection_ran": True},
        }

    def _bounded_web_result(self, web: dict[str, Any]) -> dict[str, Any]:
        limit = self.max_results

        def urls(key: str) -> list[str]:
            rows = web.get(key, [])
            _require(isinstance(rows, list), f"Google Vision {key} must be an array")
            return [str(row.get("url", ""))[:2048] for row in rows[:limit]
                    if isinstance(row, dict) and row.get("url")]

        entity_rows = web.get("webEntities", [])
        _require(isinstance(entity_rows, list),
                 "Google Vision webEntities must be an array")
        entities = []
        for row in entity_rows[:limit]:
            if not isinstance(row, dict):
                continue
            score = row.get("score", 0.0)
            if not isinstance(score, (int, float)):
                score = 0.0
            entities.append({
                "entity_id": str(row.get("entityId", ""))[:256],
                "score": float(score),
                "description": str(row.get("description", ""))[:1024],
            })
        labels = web.get("bestGuessLabels", [])
        _require(isinstance(labels, list),
                 "Google Vision bestGuessLabels must be an array")
        return {
            "web_entities": entities,
            "pages_with_matching_images": urls("pagesWithMatchingImages"),
            "full_matching_images": urls("fullMatchingImages"),
            "partial_matching_images": urls("partialMatchingImages"),
            "visually_similar_images": urls("visuallySimilarImages"),
            "best_guess_labels": [
                str(row.get("label", ""))[:1024] for row in labels[:limit]
                if isinstance(row, dict) and row.get("label")
            ],
        }
