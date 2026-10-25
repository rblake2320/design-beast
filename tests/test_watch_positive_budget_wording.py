"""Report-contract checks only: no media extraction or OCR execution."""
import json
from pathlib import Path

import pytest

from scripts import compare_watch_positive_controls as comparison


def test_emitted_protocol_charges_output_requests_not_internal_decode(tmp_path, monkeypatch):
    seeds = tmp_path / "seeds"
    seeds.mkdir()
    (seeds / "BLIND-LABELS.json").write_text("{}", encoding="utf-8")

    def stop_before_media(*args, **kwargs):
        raise RuntimeError("report-only test: media deliberately not executed")

    monkeypatch.setattr(comparison, "evaluate", stop_before_media)
    output = tmp_path / "output"
    with pytest.raises(RuntimeError, match="media deliberately not executed"):
        comparison.run(tmp_path, seeds, output, "not-executed")
    protocol = json.loads((output / "protocol.json").read_bytes())
    assert protocol["request_cap_per_arm"] == 16
    assert protocol["requested_output_frame_cap_per_arm"] == 16
    assert "repeated endpoints are charged again" in protocol["frame_charge_unit"]
    assert "decode_cap_per_arm" not in protocol
    assert protocol["internal_decoder_frames_measured"] is False
    assert protocol["internal_decoder_frame_cap"] is None
    assert protocol["ocr_cap_per_arm"] == 16
    assert protocol["model_token_cap"] == 0
    assert protocol["sampling_seconds_cap"] == protocol["ocr_seconds_cap"] == 60
    assert not (output / "report.json").exists()
    assert json.loads((output / "failure.json").read_bytes())["status"] == "incomplete_do_not_score"


def test_active_document_discloses_unmeasured_decoder_work():
    root = Path(__file__).resolve().parents[1]
    document = (root / "docs/WATCH-POSITIVE-CONTROLS.md").read_text(encoding="utf-8")
    assert "16decodes" not in document
    assert "Internal decoder frames are not measured or capped." in document
    assert "BUDGET-CORRECTION.md" in document
