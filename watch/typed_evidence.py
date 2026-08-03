"""Compile visual observations into typed, provenance-linked executable state.

The compiler is deliberately deterministic.  A vision model may propose raw
observations, but it cannot invent types, units, enum mappings, finality, or
source provenance here.  Missing or conflicting evidence produces an
``insufficient_evidence`` result rather than a guessed value.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image

TARGET_SCHEMA = "beast.watch.typed-target/v1"
OBSERVATION_SCHEMA = "beast.watch.typed-observations/v1"
OUTPUT_SCHEMA = "beast.watch.typed-state/v1"
FIELD_TYPES = {"string", "number", "integer", "boolean", "enum", "color_rgba"}
PHASES = {"transient", "final"}
METHODS = {"vision", "ocr", "manual_review", "application_probe"}
HEX_RGBA = re.compile(r"^#?([0-9a-fA-F]{8})$")
NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


class TypedEvidenceError(ValueError):
    """The target contract or evidence envelope is structurally invalid."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def document_fingerprint(value: Any) -> str:
    """Return the canonical fingerprint used to bind schemas and evidence."""
    return _fingerprint(value)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TypedEvidenceError(message)


def _validate_target(target: dict[str, Any]) -> dict[str, dict[str, Any]]:
    _require(target.get("schema") == TARGET_SCHEMA,
             f"target.schema must be {TARGET_SCHEMA}")
    _require(bool(str(target.get("application", "")).strip()),
             "target.application is required")
    _require(bool(str(target.get("version", "")).strip()),
             "target.version is required")
    fields = target.get("fields")
    _require(isinstance(fields, list) and fields, "target.fields must be non-empty")
    indexed: dict[str, dict[str, Any]] = {}
    for index, field in enumerate(fields):
        _require(isinstance(field, dict), f"target.fields[{index}] must be an object")
        name = str(field.get("name", "")).strip()
        _require(bool(name), f"target.fields[{index}].name is required")
        _require(name not in indexed, f"duplicate target field: {name}")
        kind = field.get("type")
        _require(kind in FIELD_TYPES, f"{name}: unsupported type {kind!r}")
        finality = field.get("finality", {})
        _require(isinstance(finality, dict), f"{name}: finality must be an object")
        confirmations = finality.get("min_confirmations", 1)
        threshold = finality.get("confidence_threshold", 0.9)
        span = finality.get("min_span_seconds", 0.0)
        _require(isinstance(confirmations, int) and confirmations >= 1,
                 f"{name}: min_confirmations must be a positive integer")
        _require(isinstance(threshold, (int, float)) and 0 <= threshold <= 1,
                 f"{name}: confidence_threshold must be 0..1")
        _require(isinstance(span, (int, float)) and span >= 0,
                 f"{name}: min_span_seconds must be non-negative")
        if kind == "enum":
            values = field.get("enum_values")
            _require(isinstance(values, list) and values and
                     all(isinstance(value, str) for value in values),
                     f"{name}: enum_values must be non-empty strings")
            _require(len(values) == len(set(values)), f"{name}: enum_values must be unique")
            aliases = field.get("aliases", {})
            _require(isinstance(aliases, dict), f"{name}: aliases must be an object")
            seen_aliases: set[str] = set()
            for label, mapping in aliases.items():
                folded = str(label).strip().casefold()
                _require(bool(folded) and folded not in seen_aliases,
                         f"{name}: duplicate or empty enum alias {label!r}")
                seen_aliases.add(folded)
                _require(isinstance(mapping, dict),
                         f"{name}: alias {label!r} must carry a mapping receipt")
                _require(mapping.get("canonical") in values,
                         f"{name}: alias {label!r} maps outside enum_values")
                _require(mapping.get("basis") in
                         {"official_spec", "application_probe", "source_artifact"},
                         f"{name}: alias {label!r} needs a recognized basis")
                _require(bool(str(mapping.get("evidence", "")).strip()),
                         f"{name}: alias {label!r} needs evidence")
        indexed[name] = field
    return indexed


def _normalize(raw: Any, field: dict[str, Any], source_unit: str | None = None) -> Any:
    kind = field["type"]
    aliases = field.get("aliases", {})
    if kind == "enum":
        _require(isinstance(raw, str), f"{field['name']}: enum input must be text")
        stripped = raw.strip()
        canonical = {value.casefold(): value for value in field["enum_values"]}
        if stripped.casefold() in canonical:
            return canonical[stripped.casefold()]
        alias_map = {str(label).strip().casefold(): mapping["canonical"]
                     for label, mapping in aliases.items()}
        _require(stripped.casefold() in alias_map,
                 f"{field['name']}: unknown enum label {raw!r}")
        return alias_map[stripped.casefold()]
    if kind == "color_rgba":
        _require(isinstance(raw, str), f"{field['name']}: RGBA input must be text")
        match = HEX_RGBA.fullmatch(raw.strip())
        _require(match is not None,
                 f"{field['name']}: RGBA must contain exactly 8 hexadecimal digits")
        return match.group(1).lower()
    if kind in {"number", "integer"}:
        _require(not isinstance(raw, bool), f"{field['name']}: boolean is not numeric")
        unit = field.get("unit")
        if isinstance(raw, str):
            text = raw.strip()
            if unit:
                if source_unit is not None:
                    _require(source_unit == unit,
                             f"{field['name']}: source unit does not match {unit!r}")
                else:
                    _require(text.endswith(unit),
                             f"{field['name']}: expected explicit unit {unit!r}")
                    text = text[:-len(unit)].strip()
            _require(NUMBER.fullmatch(text) is not None,
                     f"{field['name']}: invalid numeric value {raw!r}")
            value = float(text)
        else:
            _require(isinstance(raw, (int, float)),
                     f"{field['name']}: numeric input required")
            if unit:
                _require(source_unit == unit,
                         f"{field['name']}: numeric input needs explicit source_unit {unit!r}")
            value = float(raw)
        if kind == "integer":
            _require(value.is_integer(), f"{field['name']}: integer required")
            value = int(value)
        minimum, maximum = field.get("minimum"), field.get("maximum")
        _require(minimum is None or value >= minimum,
                 f"{field['name']}: value below minimum {minimum}")
        _require(maximum is None or value <= maximum,
                 f"{field['name']}: value above maximum {maximum}")
        return value
    if kind == "boolean":
        _require(isinstance(raw, bool),
                 f"{field['name']}: boolean must be true or false, not a label")
        return raw
    _require(isinstance(raw, str) and bool(raw.strip()),
             f"{field['name']}: non-empty string required")
    return raw.strip()


def _evidence_receipts(observation: dict[str, Any], frames: dict[str, dict[str, Any]],
                       bundle: Path) -> tuple[list[dict[str, Any]], set[str], list[float]]:
    evidence = observation.get("evidence")
    _require(isinstance(evidence, list) and evidence,
             f"{observation.get('field')}: evidence is required")
    receipts, frame_ids, times = [], set(), []
    for index, item in enumerate(evidence):
        _require(isinstance(item, dict), "evidence entries must be objects")
        frame_id = item.get("frame_id")
        _require(frame_id in frames,
                 f"{observation.get('field')}: unknown frame {frame_id!r}")
        method = item.get("method")
        _require(method in METHODS,
                 f"{observation.get('field')}: unsupported evidence method {method!r}")
        frame = frames[frame_id]
        path = (bundle / frame["file"]).resolve()
        _require(path.is_relative_to(bundle.resolve()) and path.is_file(),
                 f"{observation.get('field')}: frame file is missing or escapes bundle")
        region = item.get("region")
        _require(isinstance(region, list) and len(region) == 4 and
                 all(isinstance(value, int) for value in region),
                 f"{observation.get('field')}: region must be [x,y,width,height] integers")
        x, y, width, height = region
        _require(x >= 0 and y >= 0 and width > 0 and height > 0,
                 f"{observation.get('field')}: region must have positive area")
        with Image.open(path) as image:
            _require(x + width <= image.width and y + height <= image.height,
                     f"{observation.get('field')}: region is outside frame bounds")
            crop = image.convert("RGBA").crop((x, y, x + width, y + height))
            region_hash = hashlib.sha256(
                f"RGBA:{width}x{height}:".encode() + crop.tobytes()).hexdigest()
        ocr_confidence = item.get("ocr_confidence")
        if method == "ocr":
            _require(isinstance(ocr_confidence, (int, float)) and
                     0 <= ocr_confidence <= 1,
                     f"{observation.get('field')}: OCR evidence needs confidence 0..1")
            _require(bool(str(item.get("observed_text", "")).strip()),
                     f"{observation.get('field')}: OCR evidence needs observed_text")
        actual_frame_hash = _file_sha256(path)
        ingest_hash = frame.get("sha256")
        if ingest_hash is not None:
            _require(actual_frame_hash == ingest_hash,
                     f"{observation.get('field')}: frame hash changed since ingestion")
        seconds = float(frame["source_seconds"])
        receipts.append({
            "frame_id": frame_id,
            "source_seconds": seconds,
            "source_time": frame.get("source_time"),
            "frame_sha256": actual_frame_hash,
            "ingest_hash_verified": ingest_hash is not None,
            "region": region,
            "region_rgba_sha256": region_hash,
            "method": method,
            **({"ocr_confidence": float(ocr_confidence)} if method == "ocr" else {}),
            **({"observed_text": item["observed_text"]} if method == "ocr" else {}),
        })
        frame_ids.add(frame_id)
        times.append(seconds)
    return receipts, frame_ids, times


def compile_typed_state(target: dict[str, Any], observations: dict[str, Any],
                        timeline: dict[str, Any], bundle: Path) -> dict[str, Any]:
    """Return a typed state or a receipt-backed insufficient-evidence result."""
    fields = _validate_target(target)
    _require(observations.get("schema") == OBSERVATION_SCHEMA,
             f"observations.schema must be {OBSERVATION_SCHEMA}")
    rows = observations.get("observations")
    _require(isinstance(rows, list), "observations.observations must be an array")
    _require(observations.get("target_fingerprint") == _fingerprint(target),
             "observations target_fingerprint does not match target")
    _require(observations.get("timeline_fingerprint") == timeline.get("bundle_fingerprint"),
             "observations timeline_fingerprint does not match timeline")
    frame_rows = timeline.get("frames", [])
    _require(len(frame_rows) == len({row.get("id") for row in frame_rows}),
             "timeline frame IDs must be unique")
    frames = {row["id"]: row for row in frame_rows}
    _require(bool(frames), "timeline contains no frames")

    compiled: dict[str, list[dict[str, Any]]] = {name: [] for name in fields}
    errors: list[str] = []
    history: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        try:
            _require(isinstance(row, dict), f"observations[{index}] must be an object")
            name = row.get("field")
            _require(name in fields, f"observations[{index}]: unknown field {name!r}")
            phase = row.get("phase")
            _require(phase in PHASES, f"{name}: phase must be transient or final")
            confidence = row.get("confidence")
            _require(isinstance(confidence, (int, float)) and 0 <= confidence <= 1,
                     f"{name}: confidence must be 0..1")
            normalized = _normalize(row.get("raw_value"), fields[name], row.get("source_unit"))
            receipts, frame_ids, times = _evidence_receipts(row, frames, bundle)
            ocr_receipts = [receipt for receipt in receipts if receipt["method"] == "ocr"]
            if ocr_receipts:
                _require(confidence <= min(receipt["ocr_confidence"]
                                           for receipt in ocr_receipts),
                         f"{name}: confidence exceeds OCR confidence")
                for receipt in ocr_receipts:
                    observed = _normalize(receipt["observed_text"], fields[name],
                                          row.get("source_unit"))
                    _require(observed == normalized,
                             f"{name}: OCR observed_text disagrees with raw_value")
            item = {
                "field": name,
                "raw_value": row.get("raw_value"),
                "value": normalized,
                "phase": phase,
                "confidence": float(confidence),
                "source_ui_label": row.get("source_ui_label"),
                "evidence": receipts,
                "frame_ids": sorted(frame_ids),
                "times": times,
            }
            compiled[name].append(item)
            history.append(item)
        except (TypedEvidenceError, OSError, ValueError) as exc:
            errors.append(str(exc))

    values: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for name, field in fields.items():
        finality = field.get("finality", {})
        threshold = float(finality.get("confidence_threshold", 0.9))
        candidates = [row for row in compiled[name]
                      if row["phase"] == "final" and row["confidence"] >= threshold]
        by_value: dict[str, list[dict[str, Any]]] = {}
        for row in candidates:
            by_value.setdefault(json.dumps(row["value"], sort_keys=True), []).append(row)
        if len(by_value) != 1:
            reason = "no supported final value" if not by_value else "conflicting final values"
            if field.get("required", True) or by_value:
                unresolved.append({"field": name, "reason": reason})
            continue
        group = next(iter(by_value.values()))
        frame_ids = {frame_id for row in group for frame_id in row["frame_ids"]}
        times = sorted(time for row in group for time in row["times"])
        confirmations = int(finality.get("min_confirmations", 1))
        min_span = float(finality.get("min_span_seconds", 0.0))
        if len(frame_ids) < confirmations:
            unresolved.append({"field": name, "reason":
                               f"needs {confirmations} distinct frame confirmations"})
            continue
        if times[-1] - times[0] < min_span:
            unresolved.append({"field": name, "reason":
                               f"final evidence span is below {min_span} seconds"})
            continue
        transient_times = [time for row in compiled[name] if row["phase"] == "transient"
                           for time in row["times"]]
        if transient_times and min(times) <= max(transient_times):
            unresolved.append({"field": name,
                               "reason": "final evidence does not follow transient evidence"})
            continue
        supporting = [receipt for row in group for receipt in row["evidence"]]
        values.append({
            "name": name,
            "type": field["type"],
            "value": group[0]["value"],
            **({"unit": field["unit"]} if field.get("unit") else {}),
            "confidence": min(row["confidence"] for row in group),
            "source_ui_labels": sorted({str(row["source_ui_label"]) for row in group
                                         if row.get("source_ui_label")}),
            "evidence": supporting,
        })

    status = "answered" if not errors and not unresolved else "insufficient_evidence"
    output = {
        "schema": OUTPUT_SCHEMA,
        "status": status,
        "application": target["application"],
        "version": target["version"],
        "target_fingerprint": _fingerprint(target),
        "timeline_fingerprint": timeline.get("bundle_fingerprint"),
        "values": sorted(values, key=lambda row: row["name"]),
        "unresolved": unresolved,
        "errors": errors,
        "history": sorted(history, key=lambda row: min(row["times"])),
    }
    output["compilation_fingerprint"] = _fingerprint(output)
    return output
