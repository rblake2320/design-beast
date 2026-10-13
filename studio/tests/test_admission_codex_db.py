"""Independent admission baseline: real scheduler, controlled readings, no inference.

These tests preserve current default behavior while a separate candidate is
reviewed. Remote-generation activation needs additional stage/host contract
cases against the builder's pinned interface; these are not that activation GO.
"""
import threading
import time

import pytest
import jobs
import resource_guard
import server


@pytest.fixture(autouse=True)
def isolated_admission_store(monkeypatch, tmp_path):
    # Per-case storage prevents admission fixtures from filling the shared
    # recent-jobs listing and changing unrelated legacy-run tests.
    monkeypatch.setattr(jobs, "DB_PATH", tmp_path / "beast-test-admission.db")
    monkeypatch.setattr(jobs, "_LOCAL", threading.local())
    jobs.init()
    yield
    jobs._db().close()


@pytest.mark.parametrize("model", ["local:flux.1-schnell", "nim:flux.1-schnell"])
@pytest.mark.parametrize("reading", [
    {"available": True, "total_mib": 32607, "free_mib": 0},
    {"available": False, "error": "owned missing-measurement fixture"},
    {"available": True, "total_mib": 24000, "free_mib": 24000},
])
def test_unconfigured_default_denies_before_backend_and_cancel_recovers(
        monkeypatch, tmp_path, model, reading):
    """Default-on host policy cannot be bypassed by a cloud model spelling."""
    observed = threading.Event()
    backend_calls = []

    def measure(**kwargs):
        observed.set()
        return dict(reading)

    monkeypatch.setattr(jobs, "EXTERNAL_GPU_GUARD", True)
    monkeypatch.setattr(jobs, "LEASE_POLL_S", .01)
    monkeypatch.setattr(resource_guard, "measure_gpu", measure)
    monkeypatch.setattr(server, "_generate_one_inner",
                        lambda *args: backend_calls.append(args) or {"state": "done"})
    jid, _ = jobs.create("create", model, "owned admission baseline", {})
    jobs.update_progress(jid, phase="generating")
    run = tmp_path / jid
    run.mkdir()
    result = {}
    worker = threading.Thread(target=lambda: result.update(
        server._generate_one(run, 1, "owned fixture", server.RunReq(
            brief="owned admission baseline", model=model))))
    worker.start()
    try:
        assert observed.wait(2), "real admission path was not reached"
        assert backend_calls == []
        jobs.request_cancel(jid)
        worker.join(2)
        assert not worker.is_alive(), "denied waiter did not observe cancellation"
        assert result["state"] == "cancelled"
        assert jobs.get(jid)["phase"] == "cancelled"
        assert backend_calls == []
        assert not any(x["job_id"] == jid for x in jobs.gpu_leases())
    finally:
        jobs.request_cancel(jid)
        worker.join(2)
        jobs.release_gpu(jid + ":c1")


@pytest.mark.parametrize("model", ["local:flux.1-schnell", "nim:flux.1-schnell"])
def test_positive_default_control_enters_once_and_releases(monkeypatch, tmp_path, model):
    monkeypatch.setattr(jobs, "EXTERNAL_GPU_GUARD", True)
    monkeypatch.setattr(resource_guard, "measure_gpu", lambda **kw: {
        "available": True, "total_mib": 32607, "free_mib": 32607})
    seen = []

    def owned_backend(cand, run_dir, i, prompt, req):
        seen.append(jobs.gpu_leases())
        return {"i": i, "state": "done", "fixture": True}

    monkeypatch.setattr(server, "_generate_one_inner", owned_backend)
    jid, _ = jobs.create("create", model, "owned positive control", {})
    run = tmp_path / jid
    run.mkdir()
    result = server._generate_one(run, 1, "owned fixture", server.RunReq(
        brief="owned positive control", model=model))
    assert result["fixture"] is True
    assert len(seen) == 1
    assert any(x["job_id"] == jid for x in seen[0])
    assert not any(x["job_id"] == jid for x in jobs.gpu_leases())


@pytest.mark.parametrize("model", ["local:flux.1-schnell", "nim:flux.1-schnell"])
def test_expired_job_never_probes_or_enters_backend(monkeypatch, tmp_path, model):
    monkeypatch.setattr(jobs, "EXTERNAL_GPU_GUARD", True)

    def forbidden(*args, **kwargs):
        raise AssertionError("expired job crossed admission/backend boundary")

    monkeypatch.setattr(resource_guard, "measure_gpu", forbidden)
    monkeypatch.setattr(server, "_generate_one_inner", forbidden)
    jid, _ = jobs.create("create", model, "owned expired job", {})
    with jobs._WRITE_LOCK:
        jobs._db().execute("UPDATE jobs SET deadline=? WHERE id=?", (time.time()-1, jid))
        jobs._db().commit()
    run = tmp_path / jid
    run.mkdir()
    result = server._generate_one(run, 1, "owned fixture", server.RunReq(
        brief="owned expired job", model=model))
    assert result["state"] == "failed"
    assert result["error"] == "job deadline exceeded"
    assert jobs.get(jid)["error_code"] == jobs.E_TIMEOUT
    assert not any(x["job_id"] == jid for x in jobs.gpu_leases())
