"""Operational transport tests for canonical SafeSearch/Web extractors."""

import json
from pathlib import Path

import pytest
from jsonschema import validate
from safe_search import SafeSearchExtractor
from watch.evidence.contracts import EvidenceContractError
from watch.evidence.google_vision_client import GoogleVisionClient
from web_entities import WebDetectionExtractor


def _image(tmp_path: Path) -> Path:
    path = tmp_path / "frame.jpg"
    path.write_bytes(b"exact-image-bytes")
    return path


def _validate_canonical(event: dict) -> None:
    schema_path = Path(__file__).resolve().parents[1] / "schema" / "evidence_event.schema.json"
    validate(event, json.loads(schema_path.read_text(encoding="utf-8")))


def test_client_requires_explicit_authorization_before_injected_transport():
    calls = []
    client = GoogleVisionClient(
        api_key=None,
        requester=lambda feature, content: calls.append((feature, content)) or {},
    )
    with pytest.raises(EvidenceContractError, match="explicit authorization"):
        client.request("SAFE_SEARCH_DETECTION", b"image",
                       authorize_cloud_call=False)
    assert calls == []


def test_canonical_safe_search_uses_real_shared_transport(tmp_path):
    image = _image(tmp_path)
    calls = []

    def requester(feature, content):
        calls.append((feature, content))
        return {"safeSearchAnnotation": {
            "adult": "VERY_UNLIKELY", "violence": "VERY_UNLIKELY",
            "racy": "VERY_UNLIKELY", "medical": "UNLIKELY",
            "spoof": "VERY_UNLIKELY",
        }}

    extractor = SafeSearchExtractor(
        authorize_cloud_call=True,
        vision_client=GoogleVisionClient(api_key=None, requester=requester),
    )
    events = extractor.extract(
        {"timestamp_ms": 1000, "image_path": str(image)}, "sha256:source")
    assert calls == [("SAFE_SEARCH_DETECTION", b"exact-image-bytes")]
    assert events[0]["kind"] == "safe_search_verdict"
    assert events[0]["content"]["quarantined"] is False
    _validate_canonical(events[0])


def test_canonical_safe_search_without_permission_quarantines(tmp_path):
    image = _image(tmp_path)
    events = SafeSearchExtractor().extract(
        {"timestamp_ms": 1000, "image_path": str(image)}, "sha256:source")
    assert events[0]["kind"] == "safe_search_unavailable"
    assert events[0]["content"]["quarantined"] is True


def test_canonical_web_detection_parses_without_fetching_returned_urls(tmp_path):
    image = _image(tmp_path)
    calls = []

    def requester(feature, content):
        calls.append((feature, content))
        return {"webDetection": {
            "webEntities": [{"description": "example object", "score": 0.8}],
            "pagesWithMatchingImages": [{
                "url": "https://example.test/page",
                "pageTitle": "Example",
                "fullMatchingImages": [{"url": "https://example.test/full.jpg"}],
            }],
            "fullMatchingImages": [{"url": "https://example.test/full.jpg"}],
            "partialMatchingImages": [{"url": "https://example.test/partial.jpg"}],
            "visuallySimilarImages": [{"url": "https://example.test/similar.jpg"}],
        }}

    extractor = WebDetectionExtractor(
        authorize_cloud_call=True,
        vision_client=GoogleVisionClient(api_key=None, requester=requester),
    )
    events = extractor.extract(
        {"timestamp_ms": 1000, "image_path": str(image),
         "contains_person": False},
        "sha256:source",
    )
    assert calls == [("WEB_DETECTION", b"exact-image-bytes")]
    assert [event["kind"] for event in events] == [
        "web_entity", "matching_page", "full_matching_image",
        "partial_matching_image", "similar_image"]
    assert events[1]["content"]["url"] == "https://example.test/page"
    for event in events:
        _validate_canonical(event)


def test_canonical_web_detection_without_permission_fails_closed(tmp_path):
    image = _image(tmp_path)
    events = WebDetectionExtractor().extract(
        {"timestamp_ms": 1000, "image_path": str(image),
         "contains_person": False},
        "sha256:source",
    )
    assert events[0]["kind"] == "web_detection_unavailable"
    assert events[0]["content"]["blocked"] is True
    assert events[0]["review_state"] == "uncertain"
