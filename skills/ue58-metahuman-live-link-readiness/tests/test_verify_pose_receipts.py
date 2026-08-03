from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
import verify_pose_receipts as verifier


def _write_pose(root: Path, label: str, value: float, color: int) -> Path:
    image_path = root / f"{label}.png"
    Image.new("RGB", (64, 64), (color, color, color)).save(image_path)
    image_bytes = image_path.read_bytes()
    receipt = {
        "schema": 1,
        "state": "POSE_CAPTURED",
        "engine_version": "5.8.1-test",
        "project": "c:/proof/MoodBuddyUE58Proof.uproject",
        "run_id": root.parent.name,
        "subject": "me",
        "curve": "jawOpen",
        "capture_label": label,
        "requested_samples": 10,
        "editor_view": {
            "location_x": 0.0,
            "location_y": 0.0,
            "location_z": 0.0,
            "rotation_pitch": 0.0,
            "rotation_yaw": 0.0,
            "rotation_roll": 0.0,
            "fov": 90.0,
        },
        "actor": {
            "path": "/Game/Proof.Proof:PersistentLevel.BP_AdaProof_C_0",
            "location_x": 0.0,
            "location_y": 0.0,
            "location_z": 0.0,
            "rotation_pitch": 0.0,
            "rotation_yaw": 0.0,
            "rotation_roll": 0.0,
            "scale_x": 1.0,
            "scale_y": 1.0,
            "scale_z": 1.0,
        },
        "samples": [
            {
                "captured_utc": f"2026-08-01T00:00:0{index}Z",
                "platform_seconds": float(index),
                "source_world_seconds": float(index),
                "frame_id": index,
                "value": value,
            }
            for index in range(10)
        ],
        "image": {
            "path": str(image_path.resolve()),
            "width": 64,
            "height": 64,
            "byte_count": len(image_bytes),
            "sha256": hashlib.sha256(image_bytes).hexdigest(),
        },
    }
    receipt_path = root / f"{label}.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return receipt_path


def test_trusted_receipts_measure_and_reject_tampering(tmp_path: Path) -> None:
    root = tmp_path / "RunTest001" / "deformation"
    root.mkdir(parents=True)
    neutral_a = _write_pose(root, "neutral-a", 0.0, 20)
    neutral_b = _write_pose(root, "neutral-b", 0.0, 20)
    expression = _write_pose(root, "expression", 1.0, 220)

    result = verifier.verify(neutral_a, neutral_b, expression, (0, 0, 64, 64))
    assert result["state"] == "DEFORMATION_MEASURED"
    assert result["promotion_allowed"] is False
    assert result["identity"]["run_id"] == "RunTest001"

    Image.new("RGB", (64, 64), (0, 0, 0)).save(root / "expression.png")
    with pytest.raises(ValueError, match="hash mismatch"):
        verifier.load_receipt(expression)


def test_receipt_path_must_match_run_id(tmp_path: Path) -> None:
    root = tmp_path / "RunTest001" / "deformation"
    root.mkdir(parents=True)
    receipt = _write_pose(root, "neutral-a", 0.0, 20)
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload["run_id"] = "AnotherRun"
    receipt.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="path does not match"):
        verifier.load_receipt(receipt)


def test_stale_livelink_frame_burst_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "RunTest001" / "deformation"
    root.mkdir(parents=True)
    receipt = _write_pose(root, "neutral-a", 0.1, 20)
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    for sample in payload["samples"]:
        sample["frame_id"] = 42537
        sample["source_world_seconds"] = 1234.5
    receipt.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Stale Live Link frame burst"):
        verifier.load_receipt(receipt)
