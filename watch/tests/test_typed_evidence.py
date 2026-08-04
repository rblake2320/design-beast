import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

from watch.typed_evidence import compile_typed_state, document_fingerprint


def fixture(tmp_path: Path):
    frames = tmp_path / "frames"
    frames.mkdir()
    rows = []
    for index, seconds in enumerate((1.0, 2.0, 3.0), 1):
        path = frames / f"f{index}.png"
        Image.new("RGB", (100, 80), (index * 20, 30, 40)).save(path)
        rows.append({"id": f"frame-{index:04d}", "file": f"frames/f{index}.png",
                     "source_seconds": seconds, "source_time": f"00:00:0{index}.000"})
    timeline = {"bundle_fingerprint": "timeline-hash", "frames": rows}
    target = {
        "schema": "beast.watch.typed-target/v1",
        "application": "Vector App", "version": "1.0",
        "fields": [
            {"name": "spread_method", "type": "enum", "required": True,
             "enum_values": ["pad", "reflect", "repeat"],
             "aliases": {"Direct": {"canonical": "repeat",
                                      "basis": "application_probe",
                                      "evidence": "probe-001"}},
             "finality": {"confidence_threshold": 0.9,
                          "min_confirmations": 2, "min_span_seconds": 0.5}},
            {"name": "accent", "type": "color_rgba", "required": True,
             "finality": {"confidence_threshold": 0.95,
                          "min_confirmations": 1}},
            {"name": "gain", "type": "number", "unit": "dB", "required": True},
        ],
    }
    return target, timeline


def envelope(target, timeline, rows):
    return {"schema": "beast.watch.typed-observations/v1",
            "target_fingerprint": document_fingerprint(target),
            "timeline_fingerprint": timeline["bundle_fingerprint"],
            "observations": rows}


def observation(field, raw, frame, phase="final", confidence=0.99, **extra):
    return {"field": field, "raw_value": raw, "phase": phase,
            "confidence": confidence, "evidence": [{
                "frame_id": frame, "region": [0, 0, 20, 20], "method": "vision"
            }], **extra}


def test_compiles_enum_alias_color_unit_and_pixel_receipts(tmp_path):
    target, timeline = fixture(tmp_path)
    rows = [
        observation("spread_method", "Direct", "frame-0002",
                    source_ui_label="Direct"),
        observation("spread_method", "Direct", "frame-0003",
                    source_ui_label="Direct"),
        observation("accent", "#ec146eff", "frame-0003"),
        observation("gain", "-5 dB", "frame-0003"),
    ]
    result = compile_typed_state(target, envelope(target, timeline, rows),
                                 timeline, tmp_path)
    assert result["status"] == "answered"
    values = {row["name"]: row for row in result["values"]}
    assert values["spread_method"]["value"] == "repeat"
    assert values["accent"]["value"] == "ec146eff"
    assert values["gain"]["value"] == -5.0
    assert values["gain"]["unit"] == "dB"
    assert len(values["spread_method"]["evidence"]) == 2
    assert values["accent"]["evidence"][0]["region_rgba_sha256"]


def test_conflicting_final_values_fail_closed(tmp_path):
    target, timeline = fixture(tmp_path)
    rows = [
        observation("spread_method", "repeat", "frame-0002"),
        observation("spread_method", "reflect", "frame-0003"),
        observation("accent", "ec146eff", "frame-0003"),
        observation("gain", "-5 dB", "frame-0003"),
    ]
    result = compile_typed_state(target, envelope(target, timeline, rows),
                                 timeline, tmp_path)
    assert result["status"] == "insufficient_evidence"
    assert {row["field"]: row["reason"] for row in result["unresolved"]}[
        "spread_method"] == "conflicting final values"


def test_transient_after_final_and_bad_color_do_not_pass(tmp_path):
    target, timeline = fixture(tmp_path)
    rows = [
        observation("spread_method", "repeat", "frame-0001"),
        observation("spread_method", "repeat", "frame-0002"),
        observation("spread_method", "reflect", "frame-0003", phase="transient"),
        observation("accent", "ec1dbe", "frame-0003"),
        observation("gain", "-5", "frame-0003"),
    ]
    result = compile_typed_state(target, envelope(target, timeline, rows),
                                 timeline, tmp_path)
    assert result["status"] == "insufficient_evidence"
    assert any("exactly 8 hexadecimal" in error for error in result["errors"])
    assert any("explicit unit" in error for error in result["errors"])
    assert any(row["field"] == "spread_method" and
               "does not follow transient" in row["reason"]
               for row in result["unresolved"])


def test_low_confidence_or_single_confirmation_abstains(tmp_path):
    target, timeline = fixture(tmp_path)
    rows = [
        observation("spread_method", "Direct", "frame-0003", confidence=0.99),
        observation("accent", "ec146eff", "frame-0003", confidence=0.90),
        observation("gain", "-5 dB", "frame-0003"),
    ]
    result = compile_typed_state(target, envelope(target, timeline, rows),
                                 timeline, tmp_path)
    assert result["status"] == "insufficient_evidence"
    reasons = {row["field"]: row["reason"] for row in result["unresolved"]}
    assert "2 distinct frame" in reasons["spread_method"]
    assert reasons["accent"] == "no supported final value"


def test_wrong_target_or_timeline_cannot_compile(tmp_path):
    target, timeline = fixture(tmp_path)
    rows = [observation("accent", "ec146eff", "frame-0003")]
    observations = envelope(target, timeline, rows)
    observations["timeline_fingerprint"] = "some-other-video"
    import pytest
    with pytest.raises(ValueError, match="timeline_fingerprint"):
        compile_typed_state(target, observations, timeline, tmp_path)


def test_ocr_confidence_and_text_are_binding(tmp_path):
    target, timeline = fixture(tmp_path)
    row = observation("accent", "ec146eff", "frame-0003", confidence=0.99)
    row["evidence"][0].update({"method": "ocr", "ocr_confidence": 0.80,
                                "observed_text": "ec1dbeff"})
    result = compile_typed_state(target, envelope(target, timeline, [row]),
                                 timeline, tmp_path)
    assert result["status"] == "insufficient_evidence"
    assert any("confidence exceeds OCR" in error for error in result["errors"])


def test_documented_cli_runs_from_repo_root(tmp_path):
    target, timeline = fixture(tmp_path)
    rows = [
        observation("spread_method", "Direct", "frame-0002"),
        observation("spread_method", "Direct", "frame-0003"),
        observation("accent", "ec146eff", "frame-0003"),
        observation("gain", "-5 dB", "frame-0003"),
    ]
    paths = {
        "target": tmp_path / "target.json",
        "observations": tmp_path / "observations.json",
        "timeline": tmp_path / "timeline.json",
        "output": tmp_path / "typed-state.json",
    }
    paths["target"].write_text(json.dumps(target), encoding="utf-8")
    paths["observations"].write_text(
        json.dumps(envelope(target, timeline, rows)), encoding="utf-8")
    paths["timeline"].write_text(json.dumps(timeline), encoding="utf-8")
    repo = Path(__file__).resolve().parents[2]
    run = subprocess.run(
        [sys.executable, str(repo / "scripts" / "compile_visual_evidence.py"),
         str(paths["target"]), str(paths["observations"]),
         str(paths["timeline"]), str(paths["output"])],
        cwd=repo, capture_output=True, text=True,
    )
    assert run.returncode == 0, run.stderr + run.stdout
    assert json.loads(paths["output"].read_text())["status"] == "answered"
