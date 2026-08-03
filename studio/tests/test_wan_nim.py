"""GPU-free contract and routing tests for the official local Wan2.2 NIM."""
import base64
import hashlib
import json
import time
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

import jobs as jobs_mod

assert "beast-test" in str(jobs_mod.DB_PATH), \
    "conftest.py must redirect jobs.DB_PATH before server is imported"

import server  # noqa: E402


def _mp4() -> bytes:
    return b"\x00\x00\x00\x18ftyp" + b"isom" + (b"\0" * 1100)


class _Response:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._body


def _run_paths(tmp_path: Path, kind="animate"):
    jid, _ = jobs_mod.create(kind, "wan2.2-nim-i2v-nvfp4", "motion", {})
    run_dir = tmp_path / jid
    run_dir.mkdir()
    src = tmp_path / f"{jid}-source.png"
    return jid, run_dir, src


@pytest.mark.parametrize(
    ("dimensions", "expected_size"),
    [((96, 48), "832x480"), ((48, 96), "480x832")],
)
def test_wan_nim_payload_seed_source_and_atomic_mp4(
        monkeypatch, tmp_path, dimensions, expected_size):
    _, run_dir, src = _run_paths(tmp_path)
    Image.new("RGBA", dimensions, (20, 40, 60, 128)).save(src)
    captured = {}

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        encoded = base64.b64encode(_mp4()).decode("ascii")
        return _Response(body={"data": {"b64_json": encoded}})

    monkeypatch.setattr(server.requests, "post", post)
    monkeypatch.setattr(server.random, "randrange", lambda start, stop: 424242)
    out = run_dir / "clip.mp4"

    result = server.wan_nim_animate(src, "slow orbit", out, 3)

    assert result == {
        "file": "clip.mp4",
        "seed": 424242,
        "source": "local-nim:wan2.2-i2v:nvfp4",
        "steps": server.WAN_FAST_STEPS,
        "size": expected_size,
        "seconds": 3,
    }
    assert out.read_bytes() == _mp4()
    assert not (run_dir / ".clip.mp4.part").exists()
    assert captured["url"] == server.WAN_LOCAL
    assert captured["timeout"] == (30, 1200)
    payload = captured["json"]
    assert payload == {
        "model": "wan-ai/wan2.2",
        "prompt": "slow orbit",
        "input_reference": payload["input_reference"],
        "size": expected_size,
        "seconds": 3,
        "seed": 424242,
        "steps": server.WAN_FAST_STEPS,
        "cfg_scale": 5.0,
    }
    assert payload["input_reference"].startswith("data:image/png;base64,")
    normalized = base64.b64decode(payload["input_reference"].split(",", 1)[1])
    assert normalized.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize(
    "encoded",
    ["not-valid-base64!", base64.b64encode(b"x" * 1500).decode("ascii")],
)
def test_wan_nim_invalid_base64_or_ftyp_leaves_no_artifact(
        monkeypatch, tmp_path, encoded):
    _, run_dir, src = _run_paths(tmp_path)
    Image.new("RGB", (64, 32), "navy").save(src)
    monkeypatch.setattr(
        server.requests, "post",
        lambda *a, **kw: _Response(body={"data": {"b64_json": encoded}}))
    out = run_dir / "clip.mp4"

    result = server.wan_nim_animate(src, "pan", out, 3)

    assert result == {"error": "Wan2.2 returned an invalid MP4"}
    assert not out.exists()
    assert not (run_dir / ".clip.mp4.part").exists()


def test_wan_nim_422_is_filtered_and_publishes_nothing(monkeypatch, tmp_path):
    _, run_dir, src = _run_paths(tmp_path)
    Image.new("RGB", (64, 32), "navy").save(src)
    monkeypatch.setattr(server.requests, "post",
                        lambda *a, **kw: _Response(status=422))
    out = run_dir / "clip.mp4"

    result = server.wan_nim_animate(src, "pan", out, 3)

    assert result["filtered"] is True
    assert "safety filter" in result["error"]
    assert not out.exists()
    assert not (run_dir / ".clip.mp4.part").exists()


def test_wan_nim_cancel_after_blocking_response_wins(monkeypatch, tmp_path):
    jid, run_dir, src = _run_paths(tmp_path)
    Image.new("RGB", (64, 32), "navy").save(src)

    def post(*args, **kwargs):
        jobs_mod.request_cancel(jid)
        encoded = base64.b64encode(_mp4()).decode("ascii")
        return _Response(body={"data": {"b64_json": encoded}})

    monkeypatch.setattr(server.requests, "post", post)
    out = run_dir / "clip.mp4"

    with pytest.raises(jobs_mod.JobCancelled):
        server.wan_nim_animate(src, "pan", out, 3)
    assert jobs_mod.get(jid)["phase"] == "cancelled"
    assert not out.exists()
    assert not (run_dir / ".clip.mp4.part").exists()


def test_wan_nim_deadline_after_blocking_response_wins(monkeypatch, tmp_path):
    jid, run_dir, src = _run_paths(tmp_path)
    Image.new("RGB", (64, 32), "navy").save(src)

    def post(*args, **kwargs):
        jobs_mod._db().execute(
            "UPDATE jobs SET deadline=? WHERE id=?", (time.time() - 1, jid))
        jobs_mod._db().commit()
        encoded = base64.b64encode(_mp4()).decode("ascii")
        return _Response(body={"data": {"b64_json": encoded}})

    monkeypatch.setattr(server.requests, "post", post)
    out = run_dir / "clip.mp4"

    with pytest.raises(jobs_mod.JobTimeout):
        server.wan_nim_animate(src, "pan", out, 3)
    assert jobs_mod.get(jid)["error_code"] == jobs_mod.E_TIMEOUT
    assert not out.exists()
    assert not (run_dir / ".clip.mp4.part").exists()


def _route_setup(monkeypatch, tmp_path):
    runs = tmp_path / "runs"
    uploads = tmp_path / "uploads"
    runs.mkdir()
    uploads.mkdir()
    Image.new("RGB", (64, 32), "navy").save(uploads / "source.png")
    monkeypatch.setattr(server, "RUNS", runs)
    monkeypatch.setattr(server, "UPLOADS", uploads)
    monkeypatch.setattr(server.sys, "platform", "linux")
    monkeypatch.setattr(server, "_backend_created", lambda name: name == "nim-wan")
    monkeypatch.setattr(server, "ensure_backend", lambda *a, **kw: True)
    monkeypatch.setattr(server, "_quiesce_wan_aux_services",
                        lambda *a, **kw: True)
    # This is a routing contract test, not a Docker integration test. Mock the
    # complete backend context so clean CI runners cannot block in the real
    # `docker inspect` performed before ensure_backend() is reached.
    monkeypatch.setattr(server, "job_backend",
                        lambda *a, **kw: nullcontext(True))
    monkeypatch.setattr(jobs_mod, "gpu_lease",
                        lambda *a, **kw: nullcontext())
    return runs


def _wait_terminal(jid, timeout=3):
    end = time.time() + timeout
    while time.time() < end:
        row = jobs_mod.get(jid)
        if row and row["phase"] in jobs_mod.TERMINAL:
            return row
        time.sleep(0.01)
    raise AssertionError(f"job {jid} did not become terminal")


def _wait_manifest(run_dir: Path, timeout=3):
    """Wait for the derived manifest export after terminal DB commit."""
    path = run_dir / "manifest.json"
    end = time.time() + timeout
    while time.time() < end:
        if path.exists():
            return json.loads(path.read_text())
        time.sleep(0.01)
    raise AssertionError(f"manifest was not exported for {run_dir.name}")


def test_animate_routes_fast_to_wan_nim_with_truthful_manifest(
        monkeypatch, tmp_path):
    runs = _route_setup(monkeypatch, tmp_path)

    def generate(src, motion, out, duration):
        out.write_bytes(_mp4())
        return {"file": out.name, "seed": 77,
                "source": "local-nim:wan2.2-i2v:nvfp4",
                "steps": 8, "size": "832x480", "seconds": 3}

    monkeypatch.setattr(server, "wan_nim_animate", generate)
    monkeypatch.setattr(
        server, "wan_animate",
        lambda *a, **kw: pytest.fail("Comfy route must not be selected"))

    jid = server.animate(server.AnimateReq(
        file="source.png", motion="slow orbit", duration=3, quality="fast"))["id"]
    row = _wait_terminal(jid)

    assert row["phase"] == "done"
    assert row["model"] == "wan2.2-nim-i2v-nvfp4"
    status = jobs_mod.get_status(jid)
    assert status["candidates"][0]["source"] == \
        "local-nim:wan2.2-i2v:nvfp4"
    assert status["candidates"][0]["seed"] == 77
    manifest = _wait_manifest(runs / jid)
    assert manifest["model"] == "wan2.2-nim-i2v-nvfp4"
    assert manifest["outcome"]["trusted"] is True
    assert manifest["engine"]["candidates"][0]["source"] == \
        "local-nim:wan2.2-i2v:nvfp4"
    assert manifest["engine"]["candidates"][0]["steps"] == 8
    assert manifest["engine"]["candidates"][0]["size"] == "832x480"
    assert manifest["engine"]["candidates"][0]["seconds"] == 3
    assert manifest["seed"] == {"1": 77}
    artifact = manifest["artifacts"][0]
    assert artifact["file"] == "clip.mp4"
    assert artifact["sha256"] == hashlib.sha256(_mp4()).hexdigest()


@pytest.mark.parametrize("mode", ["cancel", "filtered"])
def test_animate_cancel_or_filter_never_spends_cloud(
        monkeypatch, tmp_path, mode):
    runs = _route_setup(monkeypatch, tmp_path)

    def generate(src, motion, out, duration):
        if mode == "cancel":
            jobs_mod.request_cancel(out.parent.name)
            return {"error": "engine response raced cancellation"}
        return {"error": "rejected by local safety filter", "filtered": True}

    monkeypatch.setattr(server, "wan_nim_animate", generate)
    monkeypatch.setattr(
        server, "hf_generate",
        lambda *a, **kw: pytest.fail("cloud fallback must not run"))

    jid = server.animate(server.AnimateReq(
        file="source.png", motion="slow orbit", duration=3, quality="fast",
        allow_cloud_fallback=True))["id"]
    row = _wait_terminal(jid)

    assert row["phase"] == ("cancelled" if mode == "cancel" else "failed")
    assert not (runs / jid / "clip.mp4").exists()
    manifest = _wait_manifest(runs / jid)
    assert manifest["outcome"]["trusted"] is False
    assert manifest["model"] == "wan2.2-nim-i2v-nvfp4"


def test_animate_seedance_fallback_stages_valid_mp4_and_records_truth(
        monkeypatch, tmp_path):
    runs = _route_setup(monkeypatch, tmp_path)
    monkeypatch.setattr(
        server, "wan_nim_animate",
        lambda *a, **kw: {"error": "local Wan NIM unavailable"})
    seen = {}

    def cloud_generate(model, motion, out, extra):
        seen.update(model=model, motion=motion, out=out, extra=extra)
        assert out.name == ".clip.cloud.mp4"
        assert not (out.parent / "clip.mp4").exists(), \
            "cloud output must be staged before atomic publication"
        out.write_bytes(_mp4())
        return {"url": "https://example.invalid/seedance.mp4",
                "file": out.name}

    monkeypatch.setattr(server, "hf_generate", cloud_generate)

    jid = server.animate(server.AnimateReq(
        file="source.png", motion="slow orbit", duration=3, quality="fast",
        allow_cloud_fallback=True))["id"]
    row = _wait_terminal(jid)
    run_dir = runs / jid

    assert row["phase"] == "done"
    assert seen["model"] == "seedance_2_0"
    assert seen["motion"] == "slow orbit"
    assert seen["extra"][-2:] == ["--duration", "3"]
    assert (run_dir / "clip.mp4").read_bytes() == _mp4()
    assert not (run_dir / ".clip.cloud.mp4").exists()

    status = jobs_mod.get_status(jid)
    assert status["model"] == "seedance_2_0"
    assert status["candidates"][0]["source"] == "cloud:seedance_2_0"
    manifest = _wait_manifest(run_dir)
    assert manifest["model"] == "seedance_2_0"
    assert manifest["outcome"] == {
        "phase": "done", "error": None, "trusted": True}
    assert manifest["engine"]["candidates"][0]["source"] == \
        "cloud:seedance_2_0"
    assert manifest["artifacts"][0]["file"] == "clip.mp4"
    assert manifest["artifacts"][0]["sha256"] == \
        hashlib.sha256(_mp4()).hexdigest()


@pytest.mark.parametrize(
    "bad_video",
    [
        b"\x00\x00\x00\x18ftyp" + b"x" * 100,
        b"\x00\x00\x00\x18nope" + b"x" * 1100,
    ],
    ids=["partial", "invalid-container"],
)
def test_animate_seedance_invalid_or_partial_mp4_is_never_trusted(
        monkeypatch, tmp_path, bad_video):
    runs = _route_setup(monkeypatch, tmp_path)
    monkeypatch.setattr(
        server, "wan_nim_animate",
        lambda *a, **kw: {"error": "local Wan NIM unavailable"})

    def cloud_generate(model, motion, out, extra):
        assert out.name == ".clip.cloud.mp4"
        out.write_bytes(bad_video)
        return {"url": "https://example.invalid/bad.mp4", "file": out.name}

    monkeypatch.setattr(server, "hf_generate", cloud_generate)

    jid = server.animate(server.AnimateReq(
        file="source.png", motion="slow orbit", duration=3, quality="fast",
        allow_cloud_fallback=True))["id"]
    row = _wait_terminal(jid)
    run_dir = runs / jid

    assert row["phase"] == "failed"
    assert "invalid MP4" in row["error"]
    assert not (run_dir / "clip.mp4").exists()
    assert not (run_dir / ".clip.cloud.mp4").exists()
    manifest = _wait_manifest(run_dir)
    assert manifest["outcome"]["phase"] == "failed"
    assert manifest["outcome"]["trusted"] is False
    assert not any(a["file"] == "clip.mp4"
                   for a in manifest.get("artifacts", []))
