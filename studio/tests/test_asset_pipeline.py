"""Fault-boundary and receiving-identity regressions, with owned real subprocesses."""
import base64
import json
import io
import os
import struct
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import asset_api
import asset_pipeline as pipeline
import jobs
from file_access import resolve_media


def glb(document=None):
    binary = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    default = {"asset": {"version": "2.0"}, "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "buffers": [{"byteLength": len(binary)}], "bufferViews": [{"buffer": 0, "byteLength": len(binary)}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "type": "VEC3", "count": 3}],
        "nodes": [{"mesh": 0}], "scenes": [{"nodes": [0]}], "scene": 0}
    if document is not None: default.update(document)
    document = default
    body = json.dumps(document).encode()
    body += b" " * (-len(body) % 4)
    length = 28 + len(body) + len(binary)
    return (struct.pack("<4sIIII", b"glTF", 2, length, len(body), 0x4E4F534A) + body
            + struct.pack("<II", len(binary), 0x004E4942) + binary)


@pytest.mark.parametrize("data", [b"glTF", b"junk" * 6, glb()[:-1],
    glb({"asset": {"version": "2.0"}, "meshes": [{}], "images": [{"uri": "file:///secret"}]}),
    glb({"asset": {"version": "2.0"}, "meshes": [{}], "skins": [{}]}),
    glb({"asset": []}), glb({"buffers": None}), glb({"meshes": "not meshes"}),
    glb({"meshes": [{"primitives": []}]}),
    glb({"bufferViews": [{"buffer": 0, "byteLength": 999}]}),
    glb({"accessors": [{"bufferView": 0, "componentType": 5126, "type": "VEC3", "count": 999}]}),
    glb({"nodes": [{"mesh": 0, "scale": [float('nan'), 1, 1]}]})])
def test_invalid_external_or_rigged_glb_is_rejected(tmp_path, data):
    path = tmp_path / "model.glb"
    path.write_bytes(data)
    with pytest.raises(pipeline.AssetError):
        pipeline.validate_glb(path)


def test_download_rejects_non_meshy_hosts_without_network(tmp_path, monkeypatch):
    monkeypatch.setenv("MESHY_API_KEY", "synthetic-test-credential")
    client = pipeline.Meshy()
    monkeypatch.setattr(client, "read", lambda *a, **kw: pytest.fail("network must not be called"))
    for url in ["http://assets.meshy.ai/x", "https://127.0.0.1/x",
                "https://assets.meshy.ai.evil/x", "https://user@assets.meshy.ai/x"]:
        with pytest.raises(pipeline.AssetError):
            client.download({"status": "SUCCEEDED", "model_urls": {"glb": url}}, tmp_path / "out.glb")


def test_invalid_download_never_lands_partial_model(tmp_path, monkeypatch):
    monkeypatch.setenv("MESHY_API_KEY", "synthetic-test-credential")
    client = pipeline.Meshy()
    monkeypatch.setattr(client, "read", lambda *a, **kw: b"bad")
    with pytest.raises(pipeline.AssetError):
        client.download({"status": "SUCCEEDED", "model_urls": {"glb": "https://assets.meshy.ai/x"}},
                        tmp_path / "model.glb")
    assert not list(tmp_path.iterdir())


def test_cancel_terminates_owned_subprocess(tmp_path):
    marker = tmp_path / "late.txt"
    script = tmp_path / "slow.py"
    script.write_text("import time,pathlib;time.sleep(3);pathlib.Path(" + repr(str(marker)) + ").write_text('late')")
    calls = 0
    def checkpoint():
        nonlocal calls
        calls += 1
        if calls >= 4:
            raise jobs.JobCancelled("owned")
    start = time.monotonic()
    with pytest.raises(jobs.JobCancelled):
        pipeline.run_owned([sys.executable, str(script)], tmp_path, "child.log", checkpoint=checkpoint)
    assert time.monotonic() - start < 2
    assert not marker.exists()


@pytest.fixture
def api(tmp_path, monkeypatch):
    jobs.init()
    monkeypatch.setattr(pipeline, "preflight_blender", lambda: None)
    uploads, runs = tmp_path / "uploads", tmp_path / "runs"
    uploads.mkdir(); runs.mkdir()
    app = FastAPI()
    def new_run(brief, model, kind, params, key=None):
        jid, created = jobs.create(kind, model, brief, params, key)
        folder = runs / jid
        if created: folder.mkdir()
        return folder, created
    asset_api.register(app, runs=runs, uploads=uploads,
        resolve=lambda ref: resolve_media(ref, uploads, runs), new_run=new_run,
        status=lambda folder, **kw: jobs.update_progress(folder.name, **kw))
    class Immediate:
        def __init__(self, target, args=(), **kw): self.target, self.args = target, args
        def start(self): self.target(*self.args)
    monkeypatch.setattr(asset_api, "threading", SimpleNamespace(Thread=Immediate))
    yield TestClient(app), uploads, runs
    with jobs._WRITE_LOCK:
        for folder in runs.iterdir():
            jobs._db().execute("DELETE FROM jobs WHERE id=?", (folder.name,))
        jobs._db().commit()


def test_paid_path_requires_both_authorizations_before_provider(api, monkeypatch):
    from PIL import Image
    client, uploads, _ = api
    Image.new("RGB", (8, 8)).save(uploads / "consent-control.png")
    monkeypatch.setattr(pipeline, "meshy_key", lambda: "synthetic-test-credential")
    monkeypatch.setattr(pipeline, "Meshy", lambda: pytest.fail("provider called before authorization"))
    for consent, credits in [(False, 0), (True, 0), (False, 120), (True, 30)]:
        response = client.post("/api/assets/prepare", json={"source": "meshy-generate",
            "file": "consent-control.png", "allow_cloud": consent, "max_credits": credits},
            headers={"Idempotency-Key": "consent-" + str(time.time_ns())})
        assert response.status_code == 400
        assert "Confirm image upload" in response.json()["error"]


def test_cross_origin_write_is_rejected(api):
    client, _, _ = api
    response = client.post("/api/assets/upload", json={"data": base64.b64encode(glb()).decode()},
                           headers={"Origin": "https://other.example"})
    assert response.status_code == 400


def test_failed_blender_spawn_becomes_terminal_failure(api, monkeypatch):
    client, uploads, runs = api
    (uploads / "model.glb").write_bytes(glb())
    monkeypatch.setattr(pipeline, "prepare", lambda *a: (_ for _ in ()).throw(FileNotFoundError()))
    result = client.post("/api/assets/prepare", json={"file": "model.glb"}).json()
    out = jobs.get_status(result["id"])
    assert out["phase"] == "failed"
    assert "FileNotFoundError" in out["error"]


def test_existing_task_is_retrieval_only(api, monkeypatch):
    client, _, runs = api
    monkeypatch.setattr(pipeline, "meshy_key", lambda: "synthetic-test-credential")
    calls = []
    class Provider:
        def task(self, kind, task_id, checkpoint):
            calls.append((kind, task_id)); return {"id": task_id, "status": "SUCCEEDED"}
        def download(self, task, path, checkpoint): path.write_bytes(glb())
        def api(self, *a, **kw): pytest.fail("retrieval must not submit or poll balance")
    monkeypatch.setattr(pipeline, "Meshy", Provider)
    monkeypatch.setattr(pipeline, "prepare", lambda *a: {"blender": {"triangles": 12}})
    result = client.post("/api/assets/prepare", json={"source": "meshy-task", "task_id": "existing"}).json()
    assert jobs.get_status(result["id"])["phase"] == "done"
    assert calls == [("image-to-3d", "existing")]


def test_no_unreal_invocation_after_cancellation(api, monkeypatch):
    client, uploads, _ = api
    (uploads / "model.glb").write_bytes(glb())
    monkeypatch.setattr(pipeline, "unreal_target", lambda: (Path("unused"), Path("unused")))
    monkeypatch.setattr(pipeline, "import_unreal", lambda *a: pytest.fail("canceled import was invoked"))
    original = jobs.create
    def create(*args, **kwargs):
        jid, created = original(*args, **kwargs)
        jobs.request_cancel(jid)
        return jid, created
    monkeypatch.setattr(jobs, "create", create)
    out = client.post("/api/assets/unreal", json={"file": "model.glb"}).json()
    assert jobs.get_status(out["id"])["phase"] == "cancelled"


def test_unreal_requires_fresh_identity_bound_receipt(tmp_path, monkeypatch):
    source = tmp_path / "source.glb"; source.write_bytes(glb())
    folder = tmp_path / "newjob"; folder.mkdir()
    project = tmp_path / "project" / "BeastAssets.uproject"
    monkeypatch.setattr(pipeline, "unreal_target", lambda: (Path("fake"), project))
    monkeypatch.setattr(pipeline, "run_owned", lambda *a, **kw: None)
    with pytest.raises(pipeline.AssetError, match="receiving-side receipt"):
        pipeline.import_unreal(source, folder)
    (folder / "unreal-receipt.json").write_text('{}')
    with pytest.raises(pipeline.AssetError, match="already exists"):
        pipeline.import_unreal(source, folder)


def test_generation_normalizes_jpeg_and_does_not_retry_unknown_submission(api, monkeypatch):
    from PIL import Image
    client, uploads, runs = api
    Image.new("RGB", (8, 8), "orange").save(uploads / "photo.jpg", "JPEG")
    monkeypatch.setattr(pipeline, "meshy_key", lambda: "synthetic-test-credential")
    submissions = []
    class Provider:
        def api(self, route, *, data=None, **kwargs):
            if route == "/balance": return {"balance": 120}
            submissions.append(data)
            raise pipeline.AssetError("Submission response was lost")
    monkeypatch.setattr(pipeline, "Meshy", Provider)
    body = {"source": "meshy-generate", "file": "photo.jpg", "allow_cloud": True, "max_credits": 120}
    headers = {"Idempotency-Key": "asset-test-" + str(time.time_ns())}
    result = client.post("/api/assets/prepare", json=body, headers=headers).json()
    assert jobs.get_status(result["id"])["phase"] == "failed"
    payload = base64.b64decode(submissions[0]["image_url"].split(",", 1)[1])
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    with Image.open(io.BytesIO(payload)) as image: assert image.format == "PNG"
    replay = client.post("/api/assets/prepare", json=body, headers=headers).json()
    assert replay["id"] == result["id"] and replay["idempotent_replay"]
    assert len(submissions) == 1
    intent = json.loads((runs / result["id"] / "provider-state.json").read_text())
    assert intent["state"] == "submission_outcome_unknown" and "uploaded_image_sha256" in intent
    body["max_triangles"] = 10000
    assert client.post("/api/assets/prepare", json=body, headers=headers).status_code == 409


def test_paid_submission_is_denied_when_blender_cannot_start(api, monkeypatch):
    from PIL import Image
    client, uploads, _ = api
    Image.new("RGB", (8, 8)).save(uploads / "source.png")
    monkeypatch.setattr(pipeline, "meshy_key", lambda: "synthetic-test-credential")
    monkeypatch.setattr(pipeline, "Meshy", lambda: pytest.fail("provider called despite missing Blender"))
    def unavailable(): raise pipeline.AssetError("Blender unavailable")
    monkeypatch.setattr(pipeline, "preflight_blender", unavailable)
    response = client.post("/api/assets/prepare", json={"source": "meshy-generate", "file": "source.png",
        "allow_cloud": True, "max_credits": 120}, headers={"Idempotency-Key": "no-blender"})
    assert response.status_code == 400 and "Blender unavailable" in response.json()["error"]


def test_unreal_rejects_fresh_receipt_for_other_assets(tmp_path, monkeypatch):
    source = tmp_path / "source.glb"; source.write_bytes(glb())
    folder = tmp_path / "newjob"; folder.mkdir()
    project = tmp_path / "project" / "BeastAssets.uproject"
    monkeypatch.setattr(pipeline, "unreal_target", lambda: (Path("fake"), project))
    def run(*args, **kwargs):
        pipeline.atomic_json(folder / "unreal-receipt.json", {
            "source_sha256": pipeline.sha256(source), "run_id": folder.name,
            "engine_version": "5.8.1", "project": str(project), "reloaded": True,
            "destination": "/Game/OtherProject/OldAsset", "meshes": [{"asset": "/Game/OtherProject/OldAsset"}]})
    monkeypatch.setattr(pipeline, "run_owned", run)
    with pytest.raises(pipeline.AssetError, match="different asset destination"):
        pipeline.import_unreal(source, folder)


def test_nested_asset_exports_are_manifested_as_drafts(tmp_path):
    import server
    folder = tmp_path / ("asset-manifest-" + str(time.time_ns()))
    folder.mkdir()
    jid, _ = jobs.create("asset", "asset-pipeline", "control", {})
    folder = tmp_path / jid; folder.mkdir()
    slot = folder / "candidate_1"; slot.mkdir()
    (slot / "model.glb").write_bytes(glb())
    (slot / "asset.blend").write_bytes(b"test source")
    try:
        server._status(folder, phase="done", candidates=[], final="candidate_1/model.glb")
        out = json.loads((folder / "manifest.json").read_text())
        assert {a["file"] for a in out["artifacts"]} == {"candidate_1/model.glb", "candidate_1/asset.blend"}
        assert out["outcome"]["review_required"] and not out["outcome"]["trusted"]
    finally:
        jobs._db().execute("DELETE FROM jobs WHERE id=?", (jid,)); jobs._db().commit()


def test_schema_inspection_preserves_running_asset_job():
    import generate_openapi
    jid, _ = jobs.create("asset", "asset-pipeline", "schema preservation", {})
    jobs.set_phase(jid, "running")
    try:
        before = jobs.get(jid)
        conn = jobs._db()
        generate_openapi.generate()
        assert jobs.get(jid) == before
        assert jobs._db() is conn
    finally:
        jobs._db().execute("DELETE FROM jobs WHERE id=?", (jid,)); jobs._db().commit()
