"""
Tests for the safety/web extractors closing the Google-feature gap
(SAFE_SEARCH_DETECTION, WEB_DETECTION, video EXPLICIT_CONTENT_DETECTION).

Injection-style: each test plants one adverse condition (flagged content,
API failure, person in frame, unscreened frame) and asserts the extractor
fails CLOSED with an attributable, human-gated event — never a silent pass
or a silent drop.
"""
import pytest

from explicit_content_video import ExplicitContentVideoExtractor
from safe_search import SafeSearchExtractor, likelihood_at_least
from web_entities import WebDetectionExtractor

FRAME = {"timestamp_ms": 1000, "image_path": "frames/f_0001.jpg"}
SEGMENT = {"start_ms": 0, "end_ms": 5000, "video_path": "clips/rec.mp4"}


class StubSafeSearch(SafeSearchExtractor):
    def __init__(self, likelihoods=None, error=None, **kwargs):
        super().__init__(**kwargs)
        self._likelihoods, self._error = likelihoods, error

    def _call_vision_api(self, image_path):
        if self._error:
            raise self._error
        return self._likelihoods


class StubWeb(WebDetectionExtractor):
    def __init__(self, raw=None, **kwargs):
        super().__init__(**kwargs)
        self._raw, self.api_called = raw or {}, False

    def _call_vision_api(self, image_path):
        self.api_called = True
        return self._raw


class StubExplicit(ExplicitContentVideoExtractor):
    def __init__(self, frames=None, error=None, **kwargs):
        super().__init__(**kwargs)
        self._frames, self._error = frames, error

    def _call_video_intelligence(self, video_path, start_ms, end_ms):
        if self._error:
            raise self._error
        return self._frames


def _clean_likelihoods(**overrides):
    base = {c: "VERY_UNLIKELY" for c in ("adult", "violence", "racy", "medical", "spoof")}
    base.update(overrides)
    return base


# --- likelihood ladder ------------------------------------------------------

def test_unknown_never_satisfies_a_threshold():
    assert not likelihood_at_least("UNKNOWN", "VERY_UNLIKELY")


def test_ladder_orders_correctly():
    assert likelihood_at_least("VERY_LIKELY", "LIKELY")
    assert likelihood_at_least("POSSIBLE", "POSSIBLE")
    assert not likelihood_at_least("UNLIKELY", "POSSIBLE")


# --- SafeSearch -------------------------------------------------------------

def test_clean_frame_passes_with_recorded_verdict():
    events = StubSafeSearch(_clean_likelihoods()).extract(FRAME, "src-1")
    assert len(events) == 1
    e = events[0]
    assert e["kind"] == "safe_search_verdict"
    assert e["content"]["quarantined"] is False
    assert e["review_state"] == "observed"
    assert e["frame_refs"] == [FRAME["image_path"]]


def test_likely_adult_content_is_quarantined_with_attribution():
    events = StubSafeSearch(_clean_likelihoods(adult="LIKELY")).extract(FRAME, "src-1")
    e = events[0]
    assert e["kind"] == "safe_search_quarantine"
    assert e["content"]["quarantined"] is True
    assert e["content"]["flagged_categories"] == ["adult"]
    assert e["content"]["requires_human_approval"] is True
    assert e["review_state"] == "uncertain"


def test_racy_quarantines_at_possible_by_default():
    events = StubSafeSearch(_clean_likelihoods(racy="POSSIBLE")).extract(FRAME, "src-1")
    assert events[0]["content"]["flagged_categories"] == ["racy"]


def test_unscored_category_is_not_treated_as_safe():
    events = StubSafeSearch(_clean_likelihoods(adult="UNKNOWN")).extract(FRAME, "src-1")
    e = events[0]
    assert e["content"]["quarantined"] is True
    assert e["content"]["unscored_categories"] == ["adult"]


def test_api_failure_fails_closed_not_open():
    events = StubSafeSearch(error=RuntimeError("quota")).extract(FRAME, "src-1")
    e = events[0]
    assert e["kind"] == "safe_search_unavailable"
    assert e["content"]["quarantined"] is True
    assert e["content"]["requires_human_approval"] is True
    assert e["review_state"] == "uncertain"


# --- Web detection: the person boundary ------------------------------------

def test_person_flagged_frame_refuses_api_call():
    stub = StubWeb(raw={"web_entities": [{"description": "x", "score": 1.0}]})
    events = stub.extract({**FRAME, "contains_person": True}, "src-1")
    assert stub.api_called is False
    assert events[0]["kind"] == "web_detection_blocked"
    assert "person" in events[0]["content"]["reason"]
    assert events[0]["content"]["requires_human_approval"] is True


def test_unscreened_frame_is_blocked_by_default():
    stub = StubWeb()
    events = stub.extract(dict(FRAME), "src-1")
    assert stub.api_called is False
    assert events[0]["kind"] == "web_detection_blocked"
    assert "not screened" in events[0]["content"]["reason"]


def test_screened_person_free_frame_emits_clue_events():
    stub = StubWeb(raw={
        "web_entities": [{"description": "Eiffel Tower replica", "score": 0.9}],
        "pages_with_matching_images": [
            {"url": "https://example.test/page", "title": "Park guide", "full_match": True}
        ],
        "visually_similar_images": ["https://example.test/similar.jpg"],
    })
    events = stub.extract({**FRAME, "contains_person": False}, "src-1")
    kinds = [e["kind"] for e in events]
    assert kinds == ["web_entity", "matching_page", "similar_image"]
    assert all(e["review_state"] == "observed" for e in events)
    full_match = next(e for e in events if e["kind"] == "matching_page")
    assert full_match["confidence"] == 1.0


def test_screening_opt_out_must_be_explicit():
    stub = StubWeb(raw={}, require_person_screening=False)
    events = stub.extract(dict(FRAME), "src-1")
    assert stub.api_called is True
    assert events == []


# --- Video explicit content -------------------------------------------------

def test_clean_segment_passes():
    frames = [{"timestamp_ms": t, "pornography_likelihood": "VERY_UNLIKELY"}
              for t in (0, 1000, 2000)]
    events = StubExplicit(frames).extract(SEGMENT, "src-1")
    e = events[0]
    assert e["kind"] == "explicit_content_verdict"
    assert e["content"]["quarantined"] is False
    assert e["content"]["frames_scored"] == 3


def test_flagged_frames_quarantine_segment_with_timestamps():
    frames = [
        {"timestamp_ms": 0, "pornography_likelihood": "VERY_UNLIKELY"},
        {"timestamp_ms": 1000, "pornography_likelihood": "VERY_LIKELY"},
    ]
    events = StubExplicit(frames).extract(SEGMENT, "src-1")
    e = events[0]
    assert e["kind"] == "explicit_content_quarantine"
    assert e["content"]["flagged_timestamps_ms"] == [1000]
    assert e["content"]["requires_human_approval"] is True


def test_zero_scored_frames_is_not_a_pass():
    events = StubExplicit([]).extract(SEGMENT, "src-1")
    assert events[0]["content"]["quarantined"] is True


def test_video_api_failure_fails_closed():
    events = StubExplicit(error=ConnectionError()).extract(SEGMENT, "src-1")
    e = events[0]
    assert e["kind"] == "explicit_content_unavailable"
    assert e["content"]["quarantined"] is True


# --- schema conformance -----------------------------------------------------

@pytest.mark.parametrize("extractor,payload", [
    (StubSafeSearch(_clean_likelihoods()), FRAME),
    (StubExplicit([{"timestamp_ms": 0, "pornography_likelihood": "VERY_UNLIKELY"}]), SEGMENT),
])
def test_events_carry_extractor_provenance(extractor, payload):
    event = extractor.extract(payload, "src-1")[0]
    assert event["extractor"]["name"] == extractor.name
    assert event["extractor"]["version"] == extractor.version
    assert event["extractor"]["config_hash"]
    assert event["event_id"] and event["source_id"] == "src-1"
