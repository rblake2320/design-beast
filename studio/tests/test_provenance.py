import hashlib
import json
from pathlib import Path

import pytest

from provenance import artifact_record, write_manifest


def test_manifest_records_checksum_and_replay_fields(tmp_path):
    out = tmp_path / "final.png"
    out.write_bytes(b"image bytes")
    path = write_manifest(
        tmp_path,
        run_id="run-1",
        kind="create",
        model="local:flux.1-schnell",
        params={"aspect_ratio": "1:1", "steps": 4},
        artifacts=["final.png"],
        engine={"provider": "comfyui", "version": "0.28.0", "local": True},
        seed=123,
        workflow="flux-schnell-v1",
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert data["seed"] == 123
    assert data["params"]["steps"] == 4
    assert data["artifacts"] == [{
        "file": "final.png",
        "bytes": 11,
        "sha256": hashlib.sha256(b"image bytes").hexdigest(),
        "media_type": "image/png",
    }]


def test_manifest_redacts_nested_credentials(tmp_path):
    (tmp_path / "clip.mp4").write_bytes(b"x")
    path = write_manifest(
        tmp_path,
        run_id="run-2",
        kind="animate",
        model="ltx",
        params={"token": "do-not-write", "nested": {"api_key": "secret", "safe": 1}},
        engine={"authorization": "Bearer secret"},
        artifacts=["clip.mp4"],
    )
    text = path.read_text(encoding="utf-8")
    assert "do-not-write" not in text
    assert "Bearer secret" not in text
    assert json.loads(text)["params"]["nested"]["safe"] == 1


def test_artifact_must_be_inside_run_directory(tmp_path):
    outside = tmp_path.parent / "outside.bin"
    outside.write_bytes(b"x")
    try:
        with pytest.raises(ValueError):
            artifact_record(tmp_path, outside)
    finally:
        outside.unlink(missing_ok=True)


def test_atomic_rewrite_replaces_manifest_without_temp_files(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"a")
    write_manifest(tmp_path, run_id="r", kind="create", model="m",
                   artifacts=["a.bin"], seed=1)
    write_manifest(tmp_path, run_id="r", kind="create", model="m",
                   artifacts=["a.bin"], seed=2)
    assert json.loads((tmp_path / "manifest.json").read_text())["seed"] == 2
    assert not list(tmp_path.glob(".manifest.json.*.tmp"))
