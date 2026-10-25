import json
import hashlib
import shutil
from pathlib import Path

import pytest

pytest.importorskip("cv2")
from scripts.watch_perception import run
from scripts.fuse_watch_state import fuse

ROOT = Path(__file__).resolve().parents[2]


def test_tiny_budget_cannot_publish_success(tmp_path):
    output = tmp_path / "result"
    with pytest.raises(TimeoutError):
        run(ROOT / "proofs/watch-repair/inputs/dense-repair-01", output,
            ROOT / "proofs/watch-repair/dense-ocr-recovery-01", max_seconds=1e-12)
    assert not (output / "report.json").exists()
    assert json.loads((output / "failure.json").read_text())["status"] == "incomplete"


def test_frame_path_escape_is_denied(tmp_path):
    source = ROOT / "proofs/watch-repair/inputs/dense-repair-01/timeline.json"
    timeline = json.loads(source.read_text())
    timeline["frames"][0]["file"] = "../outside.jpg"
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "timeline.json").write_text(json.dumps(timeline))
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="escapes"):
        run(bundle, output, None)
    assert not (output / "report.json").exists()


def test_foreign_detector_frame_cannot_be_fused(tmp_path):
    source = ROOT / "proofs/watch-pixel-state"
    ui = tmp_path / "ui"
    ui.mkdir()
    shutil.copyfile(source / "omniparser-blender-01/report.json", ui / "report.json")
    row = json.loads((source / "omniparser-blender-01/frame-000.json").read_text())
    row["sha256"] = "0"*64
    (ui / "frame-000.json").write_text(json.dumps(row))
    output = tmp_path / "out"
    with pytest.raises(ValueError, match="foreign"):
        fuse(source / "blender-02", ui, source / "vjepa-blender-01", output)
    assert not (output / "report.json").exists()


def test_report_identity_must_match_actual_state(tmp_path):
    source = ROOT / "proofs/watch-pixel-state"
    pixels = tmp_path / "pixels"
    (pixels / "frame-000").mkdir(parents=True)
    row = json.loads((source / "blender-02/frame-000/state.json").read_text())
    row["frame_sha256"] = "d"*64
    data = json.dumps(row).encode()
    (pixels / "frame-000/state.json").write_bytes(data)
    report = json.loads((source / "blender-02/report.json").read_text())
    report["frames"][0]["state_sha256"] = hashlib.sha256(data).hexdigest()
    (pixels / "report.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="pixel report"):
        fuse(pixels, source / "omniparser-blender-01", source / "vjepa-blender-01", tmp_path / "output")


def test_temporal_distance_cannot_be_forged(tmp_path):
    source = ROOT / "proofs/watch-pixel-state"
    temporal = tmp_path / "temporal"
    temporal.mkdir()
    for name in ("report.json", "window-00.json"):
        shutil.copyfile(source / "vjepa-blender-01" / name, temporal / name)
    row = json.loads((source / "vjepa-blender-01/window-01.json").read_text())
    row["distance_from_previous"] = .99
    (temporal / "window-01.json").write_text(json.dumps(row))
    with pytest.raises(ValueError, match="distance disagrees"):
        fuse(source / "blender-02", source / "omniparser-blender-01", temporal, tmp_path / "output")
