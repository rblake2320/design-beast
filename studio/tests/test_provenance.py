import hashlib
import json
from pathlib import Path

import pytest

from provenance import artifact_record, write_manifest
import jobs
import server


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


def test_terminal_status_writes_artifact_manifest(tmp_path):
    jid, _ = jobs.create("create", "local:flux.1-schnell", "a test",
                         {"aspect_ratio": "1:1"})
    run_dir = tmp_path / jid
    run_dir.mkdir()
    (run_dir / "final.png").write_bytes(b"final pixels")
    # A fallback may truthfully update the live snapshot model while the
    # immutable submission row retains the originally requested model.
    server._status(run_dir, phase="generating", model="nano_banana_2")

    server._status(
        run_dir,
        phase="done",
        candidates=[{"i": 1, "state": "done", "file": "final.png",
                     "seed": 42, "source": "local-nim:8018"}],
        winner=1,
        final="final.png",
    )

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == jid
    assert manifest["model"] == "nano_banana_2"
    assert manifest["params"]["aspect_ratio"] == "1:1"
    assert manifest["seed"] == {"1": 42}
    assert manifest["outcome"] == {"phase": "done", "error": None, "trusted": True}
    assert manifest["engine"]["candidates"][0]["source"] == "local-nim:8018"
    assert manifest["artifacts"][0]["file"] == "final.png"
    jobs._db().execute("DELETE FROM jobs WHERE id=?", (jid,))
    jobs._db().commit()


def test_manifest_export_failure_cannot_change_terminal_state(tmp_path, monkeypatch):
    jid, _ = jobs.create("create", "local:flux.1-schnell", "a test", {})
    run_dir = tmp_path / jid
    run_dir.mkdir()
    monkeypatch.setattr(server, "write_manifest",
                        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk")))

    server._status(run_dir, phase="done", final="final.png")

    assert jobs.get_status(jid)["phase"] == "done"
    jobs._db().execute("DELETE FROM jobs WHERE id=?", (jid,))
    jobs._db().commit()


def test_to3d_preserves_backend_seed_and_source(tmp_path, monkeypatch):
    src = tmp_path / "source.png"
    src.write_bytes(b"png")
    monkeypatch.setattr(server, "RUNS", tmp_path)
    monkeypatch.setattr(server, "_resolve", lambda _: src)
    monkeypatch.setattr(server, "ensure_backend", lambda *args, **kwargs: True)

    def fake_trellis(_src, out, _allow_hosted):
        out.write_bytes(b"glTF" + b"\0" * 20)
        return {"file": out.name, "seed": 1234, "source": "local RTX NIM"}

    class ImmediateThread:
        def __init__(self, target, daemon=True):
            self.target = target

        def start(self):
            self.target()

    class ThreadingStub:
        Thread = ImmediateThread

    monkeypatch.setattr(server, "trellis_3d", fake_trellis)
    monkeypatch.setattr(server, "threading", ThreadingStub)
    jid = server.to_3d(server.To3DReq(file="source.png"))["id"]
    status = jobs.get_status(jid)
    manifest = json.loads((tmp_path / jid / "manifest.json").read_text())

    assert status["phase"] == "done"
    assert status["candidates"][0]["seed"] == 1234
    assert status["candidates"][0]["source"] == "local RTX NIM"
    assert manifest["seed"] == {"1": 1234}
    jobs._db().execute("DELETE FROM jobs WHERE id=?", (jid,))
    jobs._db().commit()
