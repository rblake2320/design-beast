"""GPU scheduler / lease / deadline tests — GPU-free, no live server.

    cd design-beast && python -m pytest studio/tests/test_gpu_lease.py -q

conftest.py redirects jobs.DB_PATH to a throwaway SQLite file before server.py
is imported; nothing here touches the live studio/jobs.db or any GPU backend.
"""
import sqlite3
import threading
import time

import jobs as jobs_mod  # noqa: E402  (path + DB redirect done in conftest.py)

assert "beast-test" in str(jobs_mod.DB_PATH), \
    "conftest.py must redirect jobs.DB_PATH before server is imported"

import server  # noqa: E402


def _new_job(kind="create", brief="lease test") -> str:
    jid, created = jobs_mod.create(kind, "local:flux.1-schnell", brief, {})
    assert created
    return jid


def _clear_leases():
    with jobs_mod._WRITE_LOCK:
        jobs_mod._db().execute("DELETE FROM gpu_leases")
        jobs_mod._db().commit()


def setup_function(_):
    _clear_leases()


def _backdate_deadline(jid, seconds_ago=10):
    with jobs_mod._WRITE_LOCK:
        jobs_mod._db().execute("UPDATE jobs SET deadline=? WHERE id=?",
                               (time.time() - seconds_ago, jid))
        jobs_mod._db().commit()


# ---- resource classes -----------------------------------------------------

def test_heavy_is_exclusive_against_light_and_heavy():
    a, b = _new_job("animate"), _new_job()
    assert jobs_mod._try_acquire_gpu(a, a, "heavy")
    assert not jobs_mod._try_acquire_gpu(b, b, "light"), "light granted under heavy"
    assert not jobs_mod._try_acquire_gpu(b, b, "heavy"), "second heavy granted"
    jobs_mod.release_gpu(a)
    assert jobs_mod._try_acquire_gpu(b, b, "light")


def test_light_blocks_heavy_until_released():
    a, b = _new_job(), _new_job("animate")
    assert jobs_mod._try_acquire_gpu(f"{a}:c1", a, "light")
    assert not jobs_mod._try_acquire_gpu(b, b, "heavy"), \
        "heavy granted while image generation holds a light lease"
    jobs_mod.release_gpu(f"{a}:c1")
    assert jobs_mod._try_acquire_gpu(b, b, "heavy")


def test_light_concurrency_is_bounded():
    a = _new_job()
    assert jobs_mod.LIGHT_CONCURRENCY == 2  # test written against the default
    assert jobs_mod._try_acquire_gpu(f"{a}:c1", a, "light")
    assert jobs_mod._try_acquire_gpu(f"{a}:c2", a, "light")
    assert not jobs_mod._try_acquire_gpu(f"{a}:c3", a, "light"), \
        "third light lease exceeded LIGHT_CONCURRENCY"
    jobs_mod.release_gpu(f"{a}:c1")
    assert jobs_mod._try_acquire_gpu(f"{a}:c3", a, "light")


# ---- durability across restart --------------------------------------------

def test_stale_lease_from_crashed_holder_is_reclaimed():
    a, b = _new_job("animate"), _new_job("animate")
    assert jobs_mod._try_acquire_gpu(a, a, "heavy")
    # simulate a crashed holder: heartbeat stops updating
    with jobs_mod._WRITE_LOCK:
        jobs_mod._db().execute(
            "UPDATE gpu_leases SET heartbeat=? WHERE holder=?",
            (time.time() - jobs_mod.LEASE_STALE_S - 5, a))
        jobs_mod._db().commit()
    assert jobs_mod._try_acquire_gpu(b, b, "heavy"), \
        "stale lease not reclaimed — GPU permanently locked by a dead process"


def test_boot_recovery_clears_all_leases():
    a = _new_job("animate")
    assert jobs_mod._try_acquire_gpu(a, a, "heavy")
    jobs_mod.recover_orphans()  # what init() runs on every boot
    assert jobs_mod.gpu_leases() == []
    b = _new_job("animate")
    assert jobs_mod._try_acquire_gpu(b, b, "heavy")


def test_lease_released_even_when_body_raises():
    a = _new_job()
    try:
        with jobs_mod.gpu_lease(a, "heavy"):
            assert len(jobs_mod.gpu_leases()) == 1
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert jobs_mod.gpu_leases() == []


def test_cross_process_grant_is_atomic():
    """Simulates a SECOND SERVER PROCESS via an independent SQLite connection
    (the process-local threading lock cannot serialize it). The foreign
    connection opens a write transaction and inserts a heavy lease; our
    _try_acquire_gpu must NOT read a stale 'resource free' WAL snapshot and
    grant a conflicting lease — BEGIN IMMEDIATE forces it to wait for the
    foreign commit and then observe the lease."""
    b = _new_job("animate")  # create BEFORE the foreign txn holds the write lock
    ext = sqlite3.connect(jobs_mod.DB_PATH, timeout=30)
    try:
        now = time.time()
        ext.execute("BEGIN IMMEDIATE")
        ext.execute(
            "INSERT INTO gpu_leases (resource, holder, job_id, kind, acquired, "
            "heartbeat) VALUES (?,?,?,?,?,?)",
            (jobs_mod.GPU_RESOURCE, "foreign-proc", "foreign-proc", "heavy",
             now, now))
        result = {}
        t = threading.Thread(
            target=lambda: result.update(granted=jobs_mod._try_acquire_gpu(b, b, "heavy")))
        t.start()
        time.sleep(0.4)          # let the acquire attempt hit the write lock
        ext.commit()             # foreign process finishes its grant
        t.join(timeout=35)
        assert not t.is_alive(), "acquire attempt hung"
        assert result.get("granted") is False, \
            "conflicting heavy lease granted alongside another process's lease"
        assert len([l for l in jobs_mod.gpu_leases() if l["kind"] == "heavy"]) == 1
    finally:
        ext.close()


# ---- cancellation- and deadline-aware acquisition -------------------------

def test_waiting_acquire_aborts_on_cancel():
    holder, waiter = _new_job("animate"), _new_job("animate")
    assert jobs_mod._try_acquire_gpu(holder, holder, "heavy")
    jobs_mod.update_progress(waiter, phase="generating")  # queued -> running
    result = {}

    def wait_for_gpu():
        try:
            with jobs_mod.gpu_lease(waiter, "heavy"):
                result["outcome"] = "acquired"
        except jobs_mod.JobCancelled:
            result["outcome"] = "cancelled"

    t = threading.Thread(target=wait_for_gpu)
    t.start()
    time.sleep(0.3)
    jobs_mod.request_cancel(waiter)
    t.join(timeout=5)
    assert result.get("outcome") == "cancelled", \
        f"waiter did not abort on cancel: {result}"
    assert jobs_mod.get(waiter)["phase"] == "cancelled"
    jobs_mod.release_gpu(holder)


def test_waiting_acquire_aborts_on_deadline():
    holder, waiter = _new_job("animate"), _new_job("animate")
    assert jobs_mod._try_acquire_gpu(holder, holder, "heavy")
    jobs_mod.update_progress(waiter, phase="generating")
    _backdate_deadline(waiter)
    try:
        with jobs_mod.gpu_lease(waiter, "heavy"):
            raise AssertionError("lease granted to a job past its deadline")
    except jobs_mod.JobTimeout:
        pass
    j = jobs_mod.get(waiter)
    assert j["phase"] == "failed" and j["error_code"] == jobs_mod.E_TIMEOUT
    jobs_mod.release_gpu(holder)


# ---- server-enforced deadlines --------------------------------------------

def test_checkpoint_enforces_deadline_with_e_timeout():
    jid = _new_job()
    jobs_mod.update_progress(jid, phase="generating")
    _backdate_deadline(jid)
    try:
        jobs_mod.checkpoint(jid)
        raise AssertionError("checkpoint did not raise on exceeded deadline")
    except jobs_mod.JobTimeout:
        pass
    j = jobs_mod.get(jid)
    assert j["phase"] == "failed" and j["error_code"] == jobs_mod.E_TIMEOUT
    # terminal monotonicity holds for timeout outcomes too
    late = jobs_mod.update_progress(jid, phase="done", final="ghost.png")
    assert late["phase"] == "failed"
    assert jobs_mod.get(jid)["phase"] == "failed"


def test_cancel_beats_deadline_at_checkpoint():
    """Both conditions true → cancel wins (the user's word outranks the clock)."""
    jid = _new_job()
    jobs_mod.update_progress(jid, phase="generating")
    jobs_mod.request_cancel(jid)
    _backdate_deadline(jid)
    try:
        jobs_mod.checkpoint(jid)
        raise AssertionError("checkpoint did not raise")
    except jobs_mod.JobCancelled:
        pass
    assert jobs_mod.get(jid)["error_code"] == jobs_mod.E_CANCELLED


def test_backend_warmup_never_runs_while_heavy_is_held(monkeypatch, tmp_path):
    """Container start/warmup consumes VRAM: ensure_backend for an image run
    must wait for the heavy (video/3D) lease to be released — it may never
    execute while a heavy lease exists."""
    other = _new_job("animate")
    assert jobs_mod._try_acquire_gpu(other, other, "heavy")
    seen = {}

    def guarded_ensure(name, run_dir=None, **kw):
        seen["ran"] = True
        seen["heavy_present"] = any(
            l["kind"] == "heavy" for l in jobs_mod.gpu_leases())
        return False  # "backend would not start" — ends the run right here

    monkeypatch.setattr(server, "ensure_backend", guarded_ensure)
    jid = _new_job()
    run_dir = tmp_path / jid
    run_dir.mkdir()
    threading.Timer(1.0, jobs_mod.release_gpu, args=(other,)).start()
    req = server.RunReq(brief="warmup lease test")  # default local: model
    t0 = time.time()
    server._run_loop(run_dir, req)
    elapsed = time.time() - t0
    assert seen.get("ran"), "ensure_backend never ran"
    assert seen["heavy_present"] is False, \
        "warmup executed while a heavy lease was held"
    assert elapsed >= 0.9, "warmup did not wait for the heavy lease"
    assert jobs_mod.get(jid)["phase"] == "failed"  # honest 'would not start'


def test_timed_out_animate_never_retries_via_cloud(monkeypatch, tmp_path):
    """A job past its deadline fails with E_TIMEOUT and must not touch the
    credit-spending cloud fallback, even with allow_cloud_fallback=True."""
    src = tmp_path / "src.png"
    src.write_bytes(b"png-bytes")
    monkeypatch.setattr(server, "RUNS", tmp_path)
    monkeypatch.setattr(server, "_resolve", lambda f: src)
    monkeypatch.setitem(jobs_mod.DEADLINES, "animate", -1)  # born expired

    def no_backend(*a, **kw):
        raise AssertionError("render backend must not run for an expired job")
    monkeypatch.setattr(server, "wan_animate", no_backend)

    def no_cloud(*a, **kw):
        raise AssertionError("cloud fallback must not fire for a timed-out job")
    monkeypatch.setattr(server, "hf_generate", no_cloud)

    req = server.AnimateReq(file="src.png", quality="fast",
                            allow_cloud_fallback=True)
    jid = server.animate(req)["id"]
    for _ in range(50):
        j = jobs_mod.get(jid)
        if j["phase"] in jobs_mod.TERMINAL:
            break
        time.sleep(0.1)
    assert j["phase"] == "failed", f"expected failed, got {j['phase']}"
    assert j["error_code"] == jobs_mod.E_TIMEOUT
