import hashlib
import json
from pathlib import Path

import pytest
from watch.evidence import (
    EvidenceContractError,
    build_source_manifest,
    check_dataset_export,
    compile_procedure_bundle,
    create_execution_receipt,
    create_procedure_claim,
    events_from_timeline,
    make_evidence_event,
    validate_source_manifest,
)
from watch.evidence.contracts import _fingerprint
from watch.evidence.google_vision import GoogleVisionExtractor

NOW = "2026-08-04T21:00:00Z"
ENVIRONMENT = "e" * 64


def _manifest(tmp_path: Path, *, status: str = "owned",
              allowed_uses: list[str] | None = None) -> tuple[Path, dict]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"real source bytes")
    manifest = build_source_manifest(
        source,
        authorization_status=status,
        approved_by="user:owner",
        authorization_basis="owner supplied the local source",
        allowed_uses=(allowed_uses if allowed_uses is not None
                      else ["procedure_learning", "evidence_analysis"]),
        approved_at=NOW,
        source_uri="https://example.invalid/tutorial",
    )
    return source, manifest


def _timeline(tmp_path: Path, manifest: dict) -> tuple[Path, dict]:
    bundle = tmp_path / "bundle"
    frames = bundle / "frames"
    frames.mkdir(parents=True)
    frame = frames / "f_000000001000.jpg"
    frame.write_bytes(b"retained frame pixels")
    phash = "0123456789abcdef"
    timeline = {
        "schema": "beast.watch.timeline/v3",
        "source": {
            "input": "local",
            "is_url": False,
            "local_video": "source.mp4",
            "sha256": manifest["source"]["sha256"],
            "range": {"start_seconds": 0.0, "end_seconds": 2.0},
            "media": {"duration_seconds": 2.0},
        },
        "sampling": {"strategy": "test"},
        "frames": [{
            "id": "frame-0001",
            "file": "frames/f_000000001000.jpg",
            "source_seconds": 1.0,
            "source_time": "00:00:01.000",
            "reasons": ["periodic"],
            "perceptual_hash": phash,
            "sha256": hashlib.sha256(frame.read_bytes()).hexdigest(),
        }],
        "transcript": {"method": "fixture", "segments": [{
            "id": "speech-0001", "time_seconds": 1.1,
            "time": "00:00:01.100", "text": "Open the panel",
        }]},
        "bundle_fingerprint": hashlib.sha256(f"1.0:{phash}".encode()).hexdigest(),
    }
    return bundle, timeline


def _observed_event(manifest: dict) -> dict:
    return make_evidence_event(
        manifest,
        start_ms=1000,
        end_ms=1000,
        modality="screen_text",
        kind="setting_label",
        content="Exposure Compensation = 15",
        confidence=0.99,
        extractor={"name": "fixture", "version": "1.0", "config_fingerprint": "c" * 64},
        review_state="observed",
    )


def _reseal_event(event: dict) -> None:
    event.pop("event_id", None)
    event.pop("event_fingerprint", None)
    event["event_id"] = f"event-{_fingerprint(event)[:24]}"
    event["event_fingerprint"] = _fingerprint(event)


def test_source_manifest_binds_authorization_to_exact_bytes(tmp_path):
    source, manifest = _manifest(tmp_path)
    validate_source_manifest(manifest, source)
    assert manifest["source_id"] == f"sha256:{hashlib.sha256(source.read_bytes()).hexdigest()}"
    assert len(manifest["manifest_fingerprint"]) == 64

    source.write_bytes(b"changed after approval")
    with pytest.raises(EvidenceContractError, match="source hash"):
        validate_source_manifest(manifest, source)


def test_unverified_source_cannot_emit_timeline_events(tmp_path):
    _, manifest = _manifest(tmp_path, status="unverified", allowed_uses=[])
    bundle, timeline = _timeline(tmp_path, manifest)
    with pytest.raises(EvidenceContractError, match="not authorized"):
        events_from_timeline(manifest, timeline, bundle)


def test_timeline_events_bind_frame_hash_and_transcript_document(tmp_path):
    _, manifest = _manifest(tmp_path)
    bundle, timeline = _timeline(tmp_path, manifest)
    events = events_from_timeline(manifest, timeline, bundle)
    assert [event["modality"] for event in events] == ["frame", "transcript"]
    assert all(event["source_manifest_fingerprint"] == manifest["manifest_fingerprint"]
               for event in events)
    assert all(len(event["event_fingerprint"]) == 64 for event in events)

    (bundle / "frames" / "f_000000001000.jpg").write_bytes(b"tampered")
    with pytest.raises(EvidenceContractError, match="frame hash"):
        events_from_timeline(manifest, timeline, bundle)


def test_derived_measurement_requires_uncertainty(tmp_path):
    _, manifest = _manifest(tmp_path)
    with pytest.raises(EvidenceContractError, match="uncertainty"):
        make_evidence_event(
            manifest,
            start_ms=1000,
            end_ms=1100,
            modality="force_estimate",
            kind="impact_force",
            content="1200 N",
            confidence=0.8,
            extractor={"name": "force", "version": "0.1", "config_fingerprint": "c" * 64},
            review_state="inferred",
        )


def test_recomputed_fingerprint_cannot_make_invalid_event_valid(tmp_path):
    _, manifest = _manifest(tmp_path)
    event = _observed_event(manifest)
    event["confidence"] = 4.2
    _reseal_event(event)
    with pytest.raises(EvidenceContractError, match="confidence"):
        compile_procedure_bundle(
            manifest,
            [event],
            [create_procedure_claim(
                "Use a forged confidence", [event["event_id"]],
                review_state="observed")],
            [],
        )


def test_parent_events_and_receipt_claims_must_resolve(tmp_path):
    _, manifest = _manifest(tmp_path)
    parentless = make_evidence_event(
        manifest,
        start_ms=0,
        end_ms=0,
        modality="screen_text",
        kind="child",
        content="child",
        confidence=0.8,
        extractor={"name": "fixture", "version": "1.0",
                   "config_fingerprint": "c" * 64},
        review_state="observed",
        parent_event_ids=["event-" + "f" * 24],
    )
    claim = create_procedure_claim(
        "Use the child", [parentless["event_id"]], review_state="observed")
    with pytest.raises(EvidenceContractError, match="unknown parent"):
        compile_procedure_bundle(manifest, [parentless], [claim], [])

    event = _observed_event(manifest)
    valid_claim = create_procedure_claim(
        "Observed only", [event["event_id"]], review_state="observed")
    artifact = tmp_path / "orphan.txt"
    artifact.write_text("orphan", encoding="utf-8")
    orphan = create_execution_receipt(
        ["claim-" + "a" * 24],
        success=True,
        environment_fingerprint=ENVIRONMENT,
        artifacts=[("orphan", artifact)],
        checks=[{"name": "orphan", "passed": True, "evidence": "fixture"}],
        executed_at=NOW,
    )
    with pytest.raises(EvidenceContractError, match="unknown claim"):
        compile_procedure_bundle(manifest, [event], [valid_claim], [orphan])


def test_generative_derivative_cannot_support_observed_fact(tmp_path):
    _, manifest = _manifest(tmp_path)
    event = make_evidence_event(
        manifest,
        start_ms=1000,
        end_ms=1000,
        modality="screen_text",
        kind="enhanced_text",
        content="possibly reconstructed text",
        confidence=0.6,
        extractor={"name": "enhancer", "version": "1.0", "config_fingerprint": "c" * 64},
        review_state="inferred",
        artifact_refs=[{
            "role": "generative_derivative",
            "sha256": "d" * 64,
            "parent_sha256": "a" * 64,
            "operation": "generative super-resolution",
        }],
    )
    claim = create_procedure_claim(
        "Read the displayed value as recovered fact",
        [event["event_id"]],
        review_state="observed",
    )
    with pytest.raises(EvidenceContractError, match="generative"):
        compile_procedure_bundle(manifest, [event], [claim], [])


def test_failed_execution_receipt_cannot_verify_claim(tmp_path):
    _, manifest = _manifest(tmp_path)
    event = _observed_event(manifest)
    claim = create_procedure_claim(
        "Set Exposure Compensation to 15",
        [event["event_id"]],
        review_state="verified_by_execution",
        execution_receipt_id="receipt-failed",
    )
    artifact = tmp_path / "result.txt"
    artifact.write_text("failed output", encoding="utf-8")
    receipt = create_execution_receipt(
        [claim["claim_id"]],
        success=False,
        environment_fingerprint=ENVIRONMENT,
        artifacts=[("result", artifact)],
        checks=[{"name": "value_readback", "passed": False,
                 "evidence": "readback was 14, expected 15"}],
        executed_at=NOW,
        receipt_id="receipt-failed",
    )
    with pytest.raises(EvidenceContractError, match="successful execution"):
        compile_procedure_bundle(manifest, [event], [claim], [receipt])


def test_successful_hashed_receipt_promotes_only_fully_verified_bundle(tmp_path):
    _, manifest = _manifest(tmp_path)
    event = _observed_event(manifest)
    claim = create_procedure_claim(
        "Set Exposure Compensation to 15",
        [event["event_id"]],
        review_state="verified_by_execution",
        execution_receipt_id="receipt-pass",
    )
    artifact = tmp_path / "result.txt"
    artifact.write_text("readback=15", encoding="utf-8")
    receipt = create_execution_receipt(
        [claim["claim_id"]],
        success=True,
        environment_fingerprint=ENVIRONMENT,
        artifacts=[("result", artifact)],
        checks=[{"name": "value_readback", "passed": True,
                 "evidence": "readback exactly 15"}],
        executed_at=NOW,
        receipt_id="receipt-pass",
    )
    bundle = compile_procedure_bundle(manifest, [event], [claim], [receipt])
    assert bundle["gates"] == {
        "source_authorized": True,
        "evidence_linked": True,
        "execution_verified": True,
        "promotion_allowed": True,
    }
    assert len(bundle["bundle_fingerprint"]) == 64


def test_dataset_export_requires_training_rights_and_excludes_fair_use(tmp_path):
    _, fair_use = _manifest(
        tmp_path / "fair", status="fair_use_research",
        allowed_uses=["procedure_learning", "evidence_analysis"])
    rights = {
        "schema": "beast.evidence.dataset-rights/v1",
        "reviewer_id": "user:owner",
        "license_id": "owner-approved-v1",
        "rights_basis": "owner authorization",
        "training_allowed": True,
        "label_schema_version": "labels/v1",
        "split": "train",
        "source_manifest_fingerprints": [fair_use["manifest_fingerprint"]],
    }
    denied = check_dataset_export([fair_use], rights)
    assert denied["ready"] is False
    assert any("fair_use_research" in error for error in denied["errors"])

    _, owned = _manifest(
        tmp_path / "owned", status="owned",
        allowed_uses=["procedure_learning", "dataset_training"])
    rights["source_manifest_fingerprints"] = [owned["manifest_fingerprint"]]
    allowed = check_dataset_export([owned], rights)
    assert allowed == {"ready": True, "errors": [], "source_count": 1}


def _image_parent_event(manifest: dict, image: Path) -> dict:
    return make_evidence_event(
        manifest,
        start_ms=0,
        end_ms=0,
        modality="frame",
        kind="source_image",
        content=None,
        confidence=1.0,
        extractor={"name": "source_intake", "version": "1.0",
                   "config_fingerprint": "c" * 64},
        review_state="observed",
        artifact_refs=[{"role": "original_media",
                        "sha256": hashlib.sha256(image.read_bytes()).hexdigest()}],
    )


def test_google_vision_requires_explicit_cloud_authorization_and_scope(tmp_path):
    image, manifest = _manifest(tmp_path, allowed_uses=["procedure_learning"])
    parent = _image_parent_event(manifest, image)
    extractor = GoogleVisionExtractor(api_key="test", requester=lambda *_: {})
    with pytest.raises(EvidenceContractError, match="cloud_analysis"):
        extractor.analyze(image, manifest, parent, authorize_cloud_call=True)

    _, scoped = _manifest(
        tmp_path / "scoped", allowed_uses=["procedure_learning", "cloud_analysis"])
    scoped_image = tmp_path / "scoped" / "source.mp4"
    scoped_parent = _image_parent_event(scoped, scoped_image)
    with pytest.raises(EvidenceContractError, match="explicit authorization"):
        extractor.analyze(scoped_image, scoped, scoped_parent,
                          authorize_cloud_call=False)


def test_safe_search_blocks_web_detection_before_second_cloud_call(tmp_path):
    image, manifest = _manifest(
        tmp_path, allowed_uses=["procedure_learning", "cloud_analysis"])
    parent = _image_parent_event(manifest, image)
    calls = []

    def requester(feature, _content):
        calls.append(feature)
        assert feature == "SAFE_SEARCH_DETECTION"
        return {"safeSearchAnnotation": {
            "adult": "LIKELY", "violence": "VERY_UNLIKELY",
            "racy": "UNLIKELY", "medical": "UNKNOWN", "spoof": "UNKNOWN",
        }}

    result = GoogleVisionExtractor(api_key="test", requester=requester).analyze(
        image, manifest, parent, authorize_cloud_call=True)
    assert calls == ["SAFE_SEARCH_DETECTION"]
    assert result["gate"]["blocked"] is True
    assert result["gate"]["web_detection_ran"] is False
    assert [event["modality"] for event in result["events"]] == ["safety_assessment"]


def test_web_detection_records_matches_without_fetching_or_promoting_claim(tmp_path):
    image, manifest = _manifest(
        tmp_path, allowed_uses=["procedure_learning", "cloud_analysis"])
    parent = _image_parent_event(manifest, image)
    calls = []

    def requester(feature, _content):
        calls.append(feature)
        if feature == "SAFE_SEARCH_DETECTION":
            return {"safeSearchAnnotation": {
                "adult": "VERY_UNLIKELY", "violence": "UNLIKELY",
                "racy": "UNLIKELY", "medical": "UNKNOWN", "spoof": "UNKNOWN",
            }}
        return {"webDetection": {
            "webEntities": [{"entityId": "/m/test", "score": 0.9,
                              "description": "Example entity"}],
            "pagesWithMatchingImages": [{"url": "https://example.invalid/page"}],
            "fullMatchingImages": [{"url": "https://example.invalid/full.jpg"}],
            "partialMatchingImages": [],
            "visuallySimilarImages": [{"url": "https://example.invalid/similar.jpg"}],
            "bestGuessLabels": [{"label": "example"}],
        }}

    result = GoogleVisionExtractor(api_key="test", requester=requester).analyze(
        image, manifest, parent, authorize_cloud_call=True)
    assert calls == ["SAFE_SEARCH_DETECTION", "WEB_DETECTION"]
    assert result["gate"] == {"blocked": False, "reasons": [],
                              "web_detection_ran": True}
    safe_event, web_event = result["events"]
    assert web_event["modality"] == "web_detection"
    assert json.loads(web_event["content"])["full_matching_images"] == [
        "https://example.invalid/full.jpg"]

    claim = create_procedure_claim(
        "The image proves the subject's identity",
        [web_event["event_id"]],
        review_state="observed",
    )
    with pytest.raises(EvidenceContractError, match="hypothesis-only"):
        compile_procedure_bundle(manifest, [parent, safe_event, web_event], [claim], [])
