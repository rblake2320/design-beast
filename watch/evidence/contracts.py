"""Strict media custody, evidence, claim, replay, and dataset-rights contracts.

The module intentionally performs its own validation instead of treating JSON
Schema conformance as proof. Every promotion-relevant hash and reference is
checked again at the execution boundary.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

SOURCE_SCHEMA = "beast.evidence.source-manifest/v1"
EVENT_SCHEMA = "beast.evidence.event/v1"
CLAIM_SCHEMA = "beast.evidence.procedure-claim/v1"
RECEIPT_SCHEMA = "beast.evidence.execution-receipt/v1"
BUNDLE_SCHEMA = "beast.evidence.procedure-bundle/v1"
DATASET_RIGHTS_SCHEMA = "beast.evidence.dataset-rights/v1"

AUTHORIZATION_STATUSES = {
    "owned", "licensed", "public_domain", "fair_use_research", "unverified",
}
ALLOWED_USES = {
    "evidence_analysis", "procedure_learning", "cloud_analysis",
    "dataset_training", "redistribution",
}
REVIEW_STATES = {
    "observed", "inferred", "uncertain", "verified_by_execution", "rejected",
}
EVENT_REVIEW_STATES = REVIEW_STATES - {"verified_by_execution"}
MODALITIES = {
    "frame", "transcript", "screen_text", "ui_state", "object", "pose",
    "landmark", "scene_change", "force_estimate", "location_hypothesis",
    "reflection_clue", "document", "safety_assessment", "web_detection",
}
DERIVED_WITH_UNCERTAINTY = {"force_estimate", "location_hypothesis"}
HYPOTHESIS_ONLY_MODALITIES = {"web_detection", "location_hypothesis"}
ARTIFACT_ROLES = {
    "original_media", "original_frame", "deterministic_derivative",
    "generative_derivative",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class EvidenceContractError(ValueError):
    """A custody or claim boundary was violated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceContractError(message)


def _require_keys(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(value) - allowed
    _require(not unknown, f"{label} contains unknown fields: {sorted(unknown)}")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _without(value: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key not in keys}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _validate_hex64(value: Any, label: str) -> str:
    _require(isinstance(value, str) and HEX64.fullmatch(value) is not None,
             f"{label} must be 64 lowercase hexadecimal characters")
    return value


def build_source_manifest(
    source_path: Path,
    *,
    authorization_status: str,
    approved_by: str,
    authorization_basis: str,
    allowed_uses: Iterable[str],
    approved_at: str,
    source_uri: str | None = None,
) -> dict[str, Any]:
    """Admit exact source bytes under an explicit, bounded authorization."""
    source_path = Path(source_path).resolve()
    _require(source_path.is_file(), f"source file does not exist: {source_path}")
    digest = _file_sha256(source_path)
    manifest: dict[str, Any] = {
        "schema": SOURCE_SCHEMA,
        "source_id": f"sha256:{digest}",
        "source": {
            "sha256": digest,
            "bytes": source_path.stat().st_size,
            "original_name": source_path.name,
            **({"source_uri": source_uri} if source_uri else {}),
        },
        "authorization": {
            "status": authorization_status,
            "approved_by": approved_by,
            "approved_at": approved_at,
            "basis": authorization_basis,
            "allowed_uses": sorted(set(allowed_uses)),
        },
    }
    manifest["manifest_fingerprint"] = _fingerprint(manifest)
    validate_source_manifest(manifest, source_path)
    return manifest


def validate_source_manifest(
    manifest: dict[str, Any], source_path: Path | None = None,
) -> None:
    _require(isinstance(manifest, dict), "source manifest must be an object")
    _require_keys(manifest,
                  {"schema", "source_id", "source", "authorization",
                   "manifest_fingerprint"}, "source manifest")
    _require(manifest.get("schema") == SOURCE_SCHEMA,
             f"source manifest schema must be {SOURCE_SCHEMA}")
    expected = _fingerprint(_without(manifest, "manifest_fingerprint"))
    _require(manifest.get("manifest_fingerprint") == expected,
             "source manifest fingerprint does not match its content")
    source = manifest.get("source")
    _require(isinstance(source, dict), "source manifest source is required")
    _require_keys(source, {"sha256", "bytes", "original_name", "source_uri"},
                  "source manifest source")
    digest = _validate_hex64(source.get("sha256"), "source hash")
    _require(manifest.get("source_id") == f"sha256:{digest}",
             "source_id does not match source hash")
    _require(isinstance(source.get("bytes"), int) and source["bytes"] >= 0,
             "source bytes must be a non-negative integer")
    _require(bool(str(source.get("original_name", "")).strip()),
             "source original_name is required")

    auth = manifest.get("authorization")
    _require(isinstance(auth, dict), "source authorization is required")
    _require_keys(auth, {"status", "approved_by", "approved_at", "basis",
                         "allowed_uses"}, "source authorization")
    status = auth.get("status")
    _require(status in AUTHORIZATION_STATUSES,
             f"unsupported authorization status: {status!r}")
    uses = auth.get("allowed_uses")
    _require(isinstance(uses, list) and len(uses) == len(set(uses)),
             "authorization allowed_uses must be a unique array")
    _require(set(uses) <= ALLOWED_USES, "authorization contains an unknown use")
    _require(bool(str(auth.get("approved_by", "")).strip()),
             "authorization approved_by is required")
    _require(bool(str(auth.get("basis", "")).strip()),
             "authorization basis is required")
    _require(_valid_timestamp(auth.get("approved_at")),
             "authorization approved_at must include a timezone")
    if status == "unverified":
        _require(not uses, "unverified source cannot have authorized uses")
    if status == "fair_use_research":
        _require(not ({"dataset_training", "redistribution"} & set(uses)),
                 "fair_use_research cannot authorize training or redistribution")

    if source_path is not None:
        source_path = Path(source_path).resolve()
        _require(source_path.is_file(), f"source file does not exist: {source_path}")
        _require(_file_sha256(source_path) == digest,
                 "source hash changed after authorization")
        _require(source_path.stat().st_size == source["bytes"],
                 "source byte length changed after authorization")


def _require_authorized_use(manifest: dict[str, Any], use: str) -> None:
    validate_source_manifest(manifest)
    auth = manifest["authorization"]
    _require(auth["status"] != "unverified" and use in auth["allowed_uses"],
             f"source is not authorized for {use}")


def _validate_artifact_ref(ref: dict[str, Any], manifest: dict[str, Any]) -> None:
    _require(isinstance(ref, dict), "artifact reference must be an object")
    _require_keys(ref, {"role", "sha256", "parent_sha256", "operation", "path"},
                  "artifact reference")
    role = ref.get("role")
    _require(role in ARTIFACT_ROLES, f"unsupported artifact role: {role!r}")
    digest = _validate_hex64(ref.get("sha256"), "artifact sha256")
    if role == "original_media":
        _require(digest == manifest["source"]["sha256"],
                 "original_media artifact does not match source hash")
    if role in {"deterministic_derivative", "generative_derivative"}:
        _validate_hex64(ref.get("parent_sha256"), "artifact parent_sha256")
        _require(bool(str(ref.get("operation", "")).strip()),
                 "derived artifact operation is required")
    if "path" in ref:
        path = Path(str(ref["path"]))
        _require(not path.is_absolute() and ".." not in path.parts,
                 "artifact path must be relative and cannot traverse parents")


def make_evidence_event(
    manifest: dict[str, Any],
    *,
    start_ms: int,
    end_ms: int,
    modality: str,
    kind: str,
    content: str | None,
    confidence: float,
    extractor: dict[str, Any],
    review_state: str,
    artifact_refs: Iterable[dict[str, Any]] = (),
    parent_event_ids: Iterable[str] = (),
    uncertainty: dict[str, Any] | None = None,
    timeline_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Create a deterministic event only after validating its claim boundary."""
    validate_source_manifest(manifest)
    _require(isinstance(start_ms, int) and isinstance(end_ms, int)
             and 0 <= start_ms <= end_ms,
             "event source time must be non-negative and ordered")
    _require(modality in MODALITIES, f"unsupported evidence modality: {modality!r}")
    _require(bool(str(kind).strip()), "event kind is required")
    _require(isinstance(confidence, (int, float)) and not isinstance(confidence, bool)
             and 0 <= float(confidence) <= 1,
             "event confidence must be 0..1")
    _require(review_state in EVENT_REVIEW_STATES,
             f"invalid evidence review state: {review_state!r}")
    _require(isinstance(extractor, dict), "event extractor is required")
    _require(bool(str(extractor.get("name", "")).strip()),
             "extractor name is required")
    _require(bool(str(extractor.get("version", "")).strip()),
             "extractor version is required")
    _validate_hex64(extractor.get("config_fingerprint"),
                    "extractor config_fingerprint")

    refs = list(artifact_refs)
    for ref in refs:
        _validate_artifact_ref(ref, manifest)
    if any(ref["role"] == "generative_derivative" for ref in refs):
        _require(review_state in {"inferred", "uncertain", "rejected"},
                 "generative derivative cannot be observed factual evidence")

    if modality in DERIVED_WITH_UNCERTAINTY:
        _require(isinstance(uncertainty, dict),
                 f"{modality} requires an uncertainty record")
        interval = uncertainty.get("interval_95_percent")
        _require(isinstance(interval, list) and len(interval) == 2
                 and all(isinstance(value, (int, float)) for value in interval)
                 and interval[0] <= interval[1],
                 f"{modality} uncertainty needs an ordered 95% interval")
        _require(bool(str(uncertainty.get("method", "")).strip()),
                 f"{modality} uncertainty method is required")

    payload: dict[str, Any] = {
        "schema": EVENT_SCHEMA,
        "source_id": manifest["source_id"],
        "source_manifest_fingerprint": manifest["manifest_fingerprint"],
        "source_time": {"start_ms": start_ms, "end_ms": end_ms},
        "modality": modality,
        "kind": kind,
        "content": content,
        "confidence": float(confidence),
        "extractor": extractor,
        "review_state": review_state,
        "artifact_refs": refs,
        "parent_event_ids": sorted(set(parent_event_ids)),
        **({"uncertainty": uncertainty} if uncertainty is not None else {}),
        **({"timeline_fingerprint": timeline_fingerprint}
           if timeline_fingerprint is not None else {}),
    }
    event_seed = _fingerprint(payload)
    payload["event_id"] = f"event-{event_seed[:24]}"
    payload["event_fingerprint"] = _fingerprint(payload)
    validate_evidence_event(payload, manifest)
    return payload


def validate_evidence_event(event: dict[str, Any], manifest: dict[str, Any]) -> None:
    _require(isinstance(event, dict) and event.get("schema") == EVENT_SCHEMA,
             f"evidence event schema must be {EVENT_SCHEMA}")
    _require_keys(event, {
        "schema", "source_id", "source_manifest_fingerprint", "source_time",
        "modality", "kind", "content", "confidence", "extractor",
        "review_state", "artifact_refs", "parent_event_ids", "uncertainty",
        "timeline_fingerprint", "event_id", "event_fingerprint",
    }, "evidence event")
    _require(event.get("source_id") == manifest.get("source_id"),
             "evidence event source_id does not match manifest")
    _require(event.get("source_manifest_fingerprint")
             == manifest.get("manifest_fingerprint"),
             "evidence event manifest fingerprint does not match")
    expected = _fingerprint(_without(event, "event_fingerprint"))
    _require(event.get("event_fingerprint") == expected,
             "evidence event fingerprint does not match its content")
    seed = _fingerprint(_without(event, "event_id", "event_fingerprint"))
    _require(event.get("event_id") == f"event-{seed[:24]}",
             "evidence event ID does not match its content")
    # Recreate validation-sensitive fields without changing deterministic IDs.
    _require(event.get("modality") in MODALITIES, "invalid evidence modality")
    _require(event.get("review_state") in EVENT_REVIEW_STATES,
             "invalid evidence review state")
    _require(bool(str(event.get("kind", "")).strip()), "event kind is required")
    _require(event.get("content") is None or isinstance(event.get("content"), str),
             "event content must be text or null")
    confidence = event.get("confidence")
    _require(isinstance(confidence, (int, float)) and not isinstance(confidence, bool)
             and 0 <= float(confidence) <= 1,
             "event confidence must be 0..1")
    extractor = event.get("extractor")
    _require(isinstance(extractor, dict), "event extractor is required")
    _require_keys(extractor, {"name", "version", "config_fingerprint"},
                  "event extractor")
    _require(bool(str(extractor.get("name", "")).strip()),
             "extractor name is required")
    _require(bool(str(extractor.get("version", "")).strip()),
             "extractor version is required")
    _validate_hex64(extractor.get("config_fingerprint"),
                    "extractor config_fingerprint")
    time = event.get("source_time")
    _require(isinstance(time, dict) and isinstance(time.get("start_ms"), int)
             and isinstance(time.get("end_ms"), int)
             and 0 <= time["start_ms"] <= time["end_ms"],
             "event source time must be non-negative and ordered")
    for ref in event.get("artifact_refs", []):
        _validate_artifact_ref(ref, manifest)
    parents = event.get("parent_event_ids")
    _require(isinstance(parents, list) and len(parents) == len(set(parents))
             and all(isinstance(parent, str)
                     and re.fullmatch(r"event-[0-9a-f]{24}", parent)
                     for parent in parents),
             "parent_event_ids must be unique event IDs")
    if any(ref.get("role") == "generative_derivative"
           for ref in event.get("artifact_refs", [])):
        _require(event["review_state"] in {"inferred", "uncertain", "rejected"},
                 "generative derivative cannot be observed factual evidence")
    if event["modality"] in DERIVED_WITH_UNCERTAINTY:
        uncertainty = event.get("uncertainty")
        _require(isinstance(uncertainty, dict),
                 f"{event['modality']} requires an uncertainty record")
        _require_keys(uncertainty, {"interval_95_percent", "method"},
                      "event uncertainty")
        interval = uncertainty.get("interval_95_percent")
        _require(isinstance(interval, list) and len(interval) == 2
                 and all(isinstance(value, (int, float)) for value in interval)
                 and interval[0] <= interval[1],
                 f"{event['modality']} uncertainty needs an ordered 95% interval")
        _require(bool(str(uncertainty.get("method", "")).strip()),
                 f"{event['modality']} uncertainty method is required")
    if "timeline_fingerprint" in event:
        _validate_hex64(event["timeline_fingerprint"], "timeline fingerprint")


def _timeline_fingerprint(timeline: dict[str, Any]) -> str:
    return _fingerprint(timeline)


def events_from_timeline(
    manifest: dict[str, Any], timeline: dict[str, Any], bundle_dir: Path,
) -> list[dict[str, Any]]:
    """Convert a Watch v3 bundle into hash-checked cross-modal events."""
    _require_authorized_use(manifest, "evidence_analysis")
    _require(timeline.get("schema") == "beast.watch.timeline/v3",
             "timeline must use beast.watch.timeline/v3 with ingestion hashes")
    _require(timeline.get("source", {}).get("sha256")
             == manifest["source"]["sha256"],
             "timeline source hash does not match admitted source")
    frames = timeline.get("frames")
    _require(isinstance(frames, list) and frames, "timeline frames are required")
    ids = [frame.get("id") for frame in frames]
    _require(len(ids) == len(set(ids)), "timeline frame IDs must be unique")
    fingerprint_input = "\n".join(
        f"{frame['source_seconds']}:{frame['perceptual_hash']}" for frame in frames
    )
    expected_bundle = hashlib.sha256(fingerprint_input.encode()).hexdigest()
    _require(timeline.get("bundle_fingerprint") == expected_bundle,
             "timeline bundle fingerprint does not match frame plan")

    bundle_dir = Path(bundle_dir).resolve()
    timeline_fp = _timeline_fingerprint(timeline)
    config_fp = _fingerprint(timeline.get("sampling", {}))
    events: list[dict[str, Any]] = []
    for frame in frames:
        relative = Path(frame.get("file", ""))
        path = (bundle_dir / relative).resolve()
        _require(path.is_relative_to(bundle_dir) and path.is_file(),
                 f"timeline frame is missing or escapes bundle: {relative}")
        actual_hash = _file_sha256(path)
        _require(actual_hash == frame.get("sha256"),
                 f"frame hash changed after ingestion: {frame.get('id')}")
        source_ms = round(float(frame["source_seconds"]) * 1000)
        events.append(make_evidence_event(
            manifest,
            start_ms=source_ms,
            end_ms=source_ms,
            modality="frame",
            kind="sampled_frame",
            content=json.dumps({"frame_id": frame["id"],
                                "reasons": frame.get("reasons", [])},
                               sort_keys=True),
            confidence=1.0,
            extractor={"name": "beast.watch", "version": timeline["schema"],
                       "config_fingerprint": config_fp},
            review_state="observed",
            artifact_refs=[{
                "role": "deterministic_derivative",
                "sha256": actual_hash,
                "parent_sha256": manifest["source"]["sha256"],
                "operation": "watch-v3 retained frame extraction",
                "path": relative.as_posix(),
            }],
            timeline_fingerprint=timeline_fp,
        ))

    transcript = timeline.get("transcript", {})
    transcript_config = _fingerprint({"method": transcript.get("method")})
    for segment in transcript.get("segments", []):
        source_ms = round(float(segment["time_seconds"]) * 1000)
        events.append(make_evidence_event(
            manifest,
            start_ms=source_ms,
            end_ms=source_ms,
            modality="transcript",
            kind=str(transcript.get("method") or "unknown_transcription"),
            content=str(segment.get("text", "")),
            confidence=1.0,
            extractor={"name": "beast.watch.transcript",
                       "version": timeline["schema"],
                       "config_fingerprint": transcript_config},
            review_state="observed",
            timeline_fingerprint=timeline_fp,
        ))
    return events


def create_procedure_claim(
    description: str,
    evidence_event_ids: Iterable[str],
    *,
    review_state: str,
    requires_human_review: bool = False,
    execution_receipt_id: str | None = None,
) -> dict[str, Any]:
    ids = sorted(set(evidence_event_ids))
    _require(bool(description.strip()), "procedure claim description is required")
    _require(ids, "procedure claim requires evidence event IDs")
    _require(review_state in REVIEW_STATES, "invalid procedure claim review state")
    if review_state in {"inferred", "uncertain"}:
        _require(requires_human_review,
                 "inferred or uncertain claim requires human review")
    payload: dict[str, Any] = {
        "schema": CLAIM_SCHEMA,
        "description": description.strip(),
        "evidence_event_ids": ids,
        "review_state": review_state,
        "requires_human_review": bool(requires_human_review),
        **({"execution_receipt_id": execution_receipt_id}
           if execution_receipt_id else {}),
    }
    seed = _fingerprint(payload)
    payload["claim_id"] = f"claim-{seed[:24]}"
    payload["claim_fingerprint"] = _fingerprint(payload)
    return payload


def _validate_claim_fingerprint(claim: dict[str, Any]) -> None:
    _require(claim.get("schema") == CLAIM_SCHEMA,
             f"procedure claim schema must be {CLAIM_SCHEMA}")
    _require_keys(claim, {"schema", "description", "evidence_event_ids",
                          "review_state", "requires_human_review",
                          "execution_receipt_id", "claim_id",
                          "claim_fingerprint"}, "procedure claim")
    expected = _fingerprint(_without(claim, "claim_fingerprint"))
    _require(claim.get("claim_fingerprint") == expected,
             "procedure claim fingerprint does not match its content")
    seed = _fingerprint(_without(claim, "claim_id", "claim_fingerprint"))
    _require(claim.get("claim_id") == f"claim-{seed[:24]}",
             "procedure claim ID does not match its content")
    _require(claim.get("review_state") in REVIEW_STATES,
             "invalid procedure claim review state")
    _require(bool(str(claim.get("description", "")).strip()),
             "procedure claim description is required")
    ids = claim.get("evidence_event_ids")
    _require(isinstance(ids, list) and ids and len(ids) == len(set(ids)),
             "procedure claim evidence IDs must be a unique non-empty array")
    if claim["review_state"] in {"inferred", "uncertain"}:
        _require(claim.get("requires_human_review") is True,
                 "inferred or uncertain claim requires human review")
    if claim["review_state"] == "verified_by_execution":
        _require(bool(str(claim.get("execution_receipt_id", "")).strip()),
                 "verified claim requires an execution receipt ID")


def create_execution_receipt(
    claim_ids: Iterable[str],
    *,
    success: bool,
    environment_fingerprint: str,
    artifacts: Iterable[tuple[str, Path]],
    checks: Iterable[dict[str, Any]],
    executed_at: str,
    receipt_id: str | None = None,
    artifact_base: Path | None = None,
) -> dict[str, Any]:
    ids = sorted(set(claim_ids))
    _require(ids, "execution receipt requires claim IDs")
    _validate_hex64(environment_fingerprint, "environment fingerprint")
    _require(_valid_timestamp(executed_at),
             "execution receipt timestamp must include a timezone")
    artifact_rows = []
    base = Path(artifact_base).resolve() if artifact_base else None
    for label, raw_path in artifacts:
        path = Path(raw_path).resolve()
        _require(path.is_file(), f"execution artifact does not exist: {path}")
        if base is not None:
            _require(path.is_relative_to(base),
                     f"execution artifact escapes artifact base: {path}")
            stored_path = path.relative_to(base).as_posix()
        else:
            stored_path = str(path)
        artifact_rows.append({
            "label": str(label), "path": stored_path,
            "sha256": _file_sha256(path), "bytes": path.stat().st_size,
        })
    _require(artifact_rows, "execution receipt requires at least one artifact")
    check_rows = list(checks)
    _require(check_rows, "execution receipt requires checks")
    for check in check_rows:
        _require(isinstance(check, dict) and bool(str(check.get("name", "")).strip()),
                 "execution check name is required")
        _require(isinstance(check.get("passed"), bool),
                 "execution check passed must be boolean")
        _require(bool(str(check.get("evidence", "")).strip()),
                 "execution check evidence is required")
    _require(success == all(check["passed"] for check in check_rows),
             "execution success must equal the check results")
    payload: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "receipt_id": receipt_id or f"receipt-{_fingerprint(ids)[:24]}",
        "claim_ids": ids,
        "success": success,
        "environment_fingerprint": environment_fingerprint,
        "executed_at": executed_at,
        "artifacts": artifact_rows,
        "checks": check_rows,
    }
    payload["receipt_fingerprint"] = _fingerprint(payload)
    return payload


def _validate_execution_receipt(
    receipt: dict[str, Any], artifact_root: Path | None = None,
) -> None:
    _require(receipt.get("schema") == RECEIPT_SCHEMA,
             f"execution receipt schema must be {RECEIPT_SCHEMA}")
    _require_keys(receipt, {"schema", "receipt_id", "claim_ids", "success",
                            "environment_fingerprint", "executed_at", "artifacts",
                            "checks", "receipt_fingerprint"}, "execution receipt")
    expected = _fingerprint(_without(receipt, "receipt_fingerprint"))
    _require(receipt.get("receipt_fingerprint") == expected,
             "execution receipt fingerprint does not match its content")
    _validate_hex64(receipt.get("environment_fingerprint"),
                    "environment fingerprint")
    _require(_valid_timestamp(receipt.get("executed_at")),
             "execution receipt timestamp must include a timezone")
    checks = receipt.get("checks")
    _require(isinstance(checks, list) and checks, "execution receipt checks required")
    for check in checks:
        _require(isinstance(check, dict), "execution receipt check must be an object")
        _require_keys(check, {"name", "passed", "evidence"}, "execution check")
        _require(bool(str(check.get("name", "")).strip()),
                 "execution check name is required")
        _require(isinstance(check.get("passed"), bool),
                 "execution check passed must be boolean")
        _require(bool(str(check.get("evidence", "")).strip()),
                 "execution check evidence is required")
    _require(receipt.get("success") == all(check.get("passed") is True for check in checks),
             "execution success does not match check results")
    artifacts = receipt.get("artifacts")
    _require(isinstance(artifacts, list) and artifacts,
             "execution receipt artifacts required")
    for artifact in artifacts:
        _require(isinstance(artifact, dict),
                 "execution receipt artifact must be an object")
        _require_keys(artifact, {"label", "path", "sha256", "bytes"},
                      "execution artifact")
        _require(bool(str(artifact.get("label", "")).strip()),
                 "execution artifact label is required")
        digest = _validate_hex64(artifact.get("sha256"), "execution artifact sha256")
        raw_path = Path(str(artifact.get("path", "")))
        path = raw_path if raw_path.is_absolute() else (Path(artifact_root or ".") / raw_path)
        path = path.resolve()
        _require(path.is_file(), f"execution artifact is missing: {path}")
        _require(_file_sha256(path) == digest,
                 f"execution artifact hash changed: {artifact.get('label')}")
        _require(path.stat().st_size == artifact.get("bytes"),
                 f"execution artifact byte length changed: {artifact.get('label')}")


def compile_procedure_bundle(
    manifest: dict[str, Any],
    events: Iterable[dict[str, Any]],
    claims: Iterable[dict[str, Any]],
    receipts: Iterable[dict[str, Any]],
    *,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    """Compile records while deriving every gate from validated evidence."""
    _require_authorized_use(manifest, "procedure_learning")
    event_rows = list(events)
    claim_rows = list(claims)
    receipt_rows = list(receipts)
    _require(event_rows and claim_rows, "procedure bundle requires events and claims")
    event_map = {event.get("event_id"): event for event in event_rows}
    _require(None not in event_map and len(event_map) == len(event_rows),
             "procedure bundle event IDs must be unique")
    for event in event_rows:
        validate_evidence_event(event, manifest)
    for event in event_rows:
        for parent_id in event.get("parent_event_ids", []):
            _require(parent_id in event_map,
                     f"evidence event cites unknown parent event: {parent_id}")
    receipt_map = {receipt.get("receipt_id"): receipt for receipt in receipt_rows}
    _require(None not in receipt_map and len(receipt_map) == len(receipt_rows),
             "procedure bundle receipt IDs must be unique")
    for receipt in receipt_rows:
        _validate_execution_receipt(receipt, artifact_root)

    claim_map = {claim.get("claim_id"): claim for claim in claim_rows}
    _require(None not in claim_map and len(claim_map) == len(claim_rows),
             "procedure bundle claim IDs must be unique")
    for receipt in receipt_rows:
        for claim_id in receipt["claim_ids"]:
            _require(claim_id in claim_map,
                     f"execution receipt cites unknown claim: {claim_id}")

    execution_verified = True
    has_rejected = False
    for claim in claim_rows:
        _validate_claim_fingerprint(claim)
        cited = []
        for event_id in claim["evidence_event_ids"]:
            _require(event_id in event_map,
                     f"procedure claim cites unknown evidence event: {event_id}")
            cited.append(event_map[event_id])
        contains_generative = any(
            ref.get("role") == "generative_derivative"
            for event in cited for ref in event.get("artifact_refs", [])
        )
        if contains_generative:
            _require(claim["review_state"] in {"inferred", "uncertain", "rejected"},
                     "generative evidence cannot support observed or verified fact")
        if all(event["modality"] in HYPOTHESIS_ONLY_MODALITIES for event in cited):
            _require(claim["review_state"] in {"inferred", "uncertain", "rejected"},
                     "hypothesis-only evidence cannot support observed or verified fact")

        if claim["review_state"] == "verified_by_execution":
            receipt_id = claim.get("execution_receipt_id")
            _require(receipt_id in receipt_map,
                     "verified claim requires a known execution receipt")
            receipt = receipt_map[receipt_id]
            _require(receipt["success"] is True and claim["claim_id"] in receipt["claim_ids"],
                     "verified claim requires a successful execution receipt")
        else:
            execution_verified = False
        has_rejected = has_rejected or claim["review_state"] == "rejected"

    gates = {
        "source_authorized": True,
        "evidence_linked": True,
        "execution_verified": execution_verified,
        "promotion_allowed": execution_verified and not has_rejected,
    }
    bundle: dict[str, Any] = {
        "schema": BUNDLE_SCHEMA,
        "source_manifest": manifest,
        "events": event_rows,
        "claims": claim_rows,
        "execution_receipts": receipt_rows,
        "gates": gates,
    }
    bundle["bundle_fingerprint"] = _fingerprint(bundle)
    return bundle


def check_dataset_export(
    manifests: Iterable[dict[str, Any]], rights: dict[str, Any],
) -> dict[str, Any]:
    """Return a bounded readiness report; fair-use-only input never qualifies."""
    rows = list(manifests)
    errors: list[str] = []
    if rights.get("schema") != DATASET_RIGHTS_SCHEMA:
        errors.append(f"rights schema must be {DATASET_RIGHTS_SCHEMA}")
    for field in ("reviewer_id", "license_id", "rights_basis", "label_schema_version"):
        if not bool(str(rights.get(field, "")).strip()):
            errors.append(f"rights {field} is required")
    if rights.get("training_allowed") is not True:
        errors.append("rights training_allowed must be true")
    if rights.get("split") not in {"train", "validation", "test"}:
        errors.append("rights split must be train, validation, or test")
    declared = rights.get("source_manifest_fingerprints")
    if not isinstance(declared, list) or len(declared) != len(set(declared)):
        errors.append("rights source fingerprints must be a unique array")
        declared = []

    actual = []
    for index, manifest in enumerate(rows):
        try:
            validate_source_manifest(manifest)
        except EvidenceContractError as exc:
            errors.append(f"source[{index}]: {exc}")
            continue
        actual.append(manifest["manifest_fingerprint"])
        auth = manifest["authorization"]
        if auth["status"] == "fair_use_research":
            errors.append("fair_use_research source is not eligible for dataset training")
        elif auth["status"] not in {"owned", "licensed", "public_domain"}:
            errors.append(f"{auth['status']} source is not eligible for dataset training")
        if "dataset_training" not in auth["allowed_uses"]:
            errors.append("source lacks dataset_training authorization")
    if sorted(declared) != sorted(actual):
        errors.append("rights source fingerprints do not match admitted sources")
    return {"ready": not errors, "errors": errors, "source_count": len(rows)}
