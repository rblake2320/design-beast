"""Single-source job state tests — SQLite authoritative, status.json derived.

    cd design-beast && python -m pytest studio/tests/test_state_authority.py -q

GPU-free, no live server, no generation. conftest.py redirects jobs.DB_PATH to
a throwaway SQLite file BEFORE server.py is imported so nothing touches the
live studio/jobs.db.
"""
import json
import sqlite3
import tempfile
import threading
from pathlib import Path

import jobs as jobs_mod  # noqa: E402  (path + DB redirect done in conftest.py)

assert "beast-test" in str(jobs_mod.DB_PATH), \
    "conftest.py must redirect jobs.DB_PATH before server is imported"
_TMP = Path(tempfile.mkdtemp(prefix="beast-test-state-"))

import server  # noqa: E402  (init() runs against the conftest temp DB)


def _new_job(brief="state test") -> str:
    jid, created = jobs_mod.create("create", "local:flux.1-schnell", brief, {})
    assert created
    return jid


def _switch_db(path: Path):
    if hasattr(jobs_mod._LOCAL, "conn"):
        jobs_mod._LOCAL.conn.close()
        del jobs_mod._LOCAL.conn
    jobs_mod.DB_PATH = path


# ---- migration ------------------------------------------------------------

def test_old_schema_db_gains_progress_column_and_keeps_rows():
    main_db = jobs_mod.DB_PATH
    old_db = _TMP / "old-schema.db"
    conn = sqlite3.connect(old_db)
    conn.executescript("""
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, model TEXT, brief TEXT,
            phase TEXT NOT NULL DEFAULT 'queued', error TEXT, error_code TEXT,
            cancel_requested INTEGER DEFAULT 0, idempotency_key TEXT UNIQUE,
            params TEXT, result TEXT, created REAL, started REAL, finished REAL);
        INSERT INTO jobs (id, kind, brief, phase, created)
        VALUES ('legacy_01', 'create', 'pre-migration job', 'done', 1.0);
    """)
    conn.commit()
    conn.close()
    try:
        _switch_db(old_db)
        jobs_mod.init()  # runs _migrate()
        cols = {r[1] for r in jobs_mod._db().execute("PRAGMA table_info(jobs)")}
        assert "progress" in cols
        legacy = jobs_mod.get("legacy_01")
        assert legacy["phase"] == "done" and legacy["progress"] is None
        # the migrated column is immediately usable
        snap = jobs_mod.update_progress("legacy_01", note="post-migration write")
        assert snap["note"] == "post-migration write"
        # init() twice is idempotent (migration must not raise on 2nd run)
        jobs_mod.init()
    finally:
        _switch_db(main_db)


# ---- SQLite authoritative, status.json derived ----------------------------

def test_status_json_is_derived_and_never_read_back(tmp_path, monkeypatch):
    jid = _new_job("authority test")
    run_dir = tmp_path / jid
    run_dir.mkdir()
    server._status(run_dir, id=jid, brief="authority test", phase="generating",
                   candidates=[{"i": 1}])
    # export exists and matches the DB snapshot
    exported = json.loads((run_dir / "status.json").read_text())
    assert exported["phase"] == "generating"
    assert jobs_mod.get_status(jid)["phase"] == "generating"
    # tamper with the export — the API must not care
    (run_dir / "status.json").write_text(json.dumps({"phase": "done", "id": jid}))
    monkeypatch.setattr(server, "RUNS", tmp_path)
    resp = server.run_status(jid)
    assert resp["phase"] == "generating"  # DB truth, not the tampered file


def test_export_write_failure_does_not_change_api_or_db_truth(tmp_path, monkeypatch):
    jid = _new_job("export failure test")
    blocked = tmp_path / jid
    blocked.write_text("a FILE where the run dir should be")  # write_text will fail
    server._status(blocked, phase="generating", note="still lands in DB")
    s = jobs_mod.get_status(jid)
    assert s["phase"] == "generating" and s["note"] == "still lands in DB"
    monkeypatch.setattr(server, "RUNS", tmp_path)
    assert server.run_status(jid)["phase"] == "generating"


def test_api_response_shape_preserved(tmp_path):
    jid = _new_job("shape test")
    run_dir = tmp_path / jid
    run_dir.mkdir()
    server._status(run_dir, id=jid, brief="shape test",
                   model="local:flux.1-schnell", kind="create", phase="queued")
    resp = server.run_status(jid)
    for key in ("id", "brief", "model", "kind", "phase", "error_code"):
        assert key in resp, f"missing key {key}"
    assert resp["id"] == jid and resp["phase"] == "queued"


def test_legacy_run_without_db_row_still_served(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "RUNS", tmp_path)
    legacy = tmp_path / "20250101_000000_old"
    legacy.mkdir()
    (legacy / "status.json").write_text(json.dumps(
        {"id": "20250101_000000_old", "brief": "ancient run", "phase": "done",
         "kind": "create"}))
    resp = server.run_status("20250101_000000_old")
    assert resp["phase"] == "done" and resp["brief"] == "ancient run"
    listed = server.list_runs()
    assert any(r["id"] == "20250101_000000_old" for r in listed)
    assert all(set(r) == {"id", "brief", "phase", "kind"} for r in listed)


# ---- restart recovery -----------------------------------------------------

def test_restart_recovery_visible_through_api(tmp_path, monkeypatch):
    jid = _new_job("restart recovery")
    run_dir = tmp_path / jid
    run_dir.mkdir()
    server._status(run_dir, id=jid, brief="restart recovery", phase="generating")
    # simulate a dead server process restarting: boot recovery runs
    jobs_mod.recover_orphans()
    # stale export still says "generating" on disk — must be ignored
    assert json.loads((run_dir / "status.json").read_text())["phase"] == "generating"
    monkeypatch.setattr(server, "RUNS", tmp_path)
    resp = server.run_status(jid)
    assert resp["phase"] == "failed"
    assert resp["error_code"] == jobs_mod.E_INTERNAL
    assert "server restarted mid-job" in resp["error"]


# ---- terminal monotonicity + races ----------------------------------------

def test_cancelled_beats_racing_done():
    """Cancel flag lands while the worker is finishing: the worker's 'done'
    write must be converted to cancelled, atomically, inside update_progress."""
    jid = _new_job("cancel vs done race")
    jobs_mod.update_progress(jid, phase="generating")   # queued -> running
    jobs_mod.request_cancel(jid)                        # running: flag only
    snap = jobs_mod.update_progress(jid, phase="done", final="final.png")
    assert snap["phase"] == "cancelled"
    j = jobs_mod.get(jid)
    assert j["phase"] == "cancelled"
    assert j["error_code"] == jobs_mod.E_CANCELLED
    assert jobs_mod.get_status(jid)["phase"] == "cancelled"


def test_terminal_failed_never_overwritten_by_late_worker(tmp_path):
    """A terminal row is immutable: late 'generating' or 'done' writes from a
    straggling worker thread must not resurrect or flip the outcome."""
    jid = _new_job("failed vs running race")
    jobs_mod.update_progress(jid, phase="generating")
    jobs_mod.update_progress(jid, phase="failed", error="backend not answering")
    assert jobs_mod.get(jid)["phase"] == "failed"
    late1 = jobs_mod.update_progress(jid, phase="generating", note="straggler")
    late2 = jobs_mod.update_progress(jid, phase="done", final="ghost.png")
    assert late1["phase"] == "failed" and late2["phase"] == "failed"
    j = jobs_mod.get(jid)
    assert j["phase"] == "failed"
    assert j["error_code"] == jobs_mod.E_BACKEND_DOWN
    s = jobs_mod.get_status(jid)
    assert s["phase"] == "failed"
    assert s["note"] == "straggler"  # diagnostics may still accumulate


def test_terminal_error_immune_to_straggler_error_updates():
    """A late worker writing error='STRAGGLER' into mutable progress must not
    change the displayed error of an already-terminal job — the row's error is
    part of the immutable terminal outcome."""
    jid = _new_job("straggler error race")
    jobs_mod.update_progress(jid, phase="generating")
    jobs_mod.update_progress(jid, phase="failed", error="backend not answering")
    jobs_mod.update_progress(jid, error="STRAGGLER")
    s = jobs_mod.get_status(jid)
    assert s["phase"] == "failed"
    assert s["error"] == "backend not answering"
    assert jobs_mod.get(jid)["error"] == "backend not answering"


def test_failed_preserved_when_cancel_flag_raced():
    """POLICY (documented in update_progress): a genuine failure that raced a
    cancel request keeps its failure identity — only a racing 'done' converts
    to cancelled. The failure detail is more informative than 'cancelled', and
    interrupt-caused errors are already classified as cancelled at the source."""
    jid = _new_job("failed vs cancel-flag race")
    jobs_mod.update_progress(jid, phase="generating")
    jobs_mod.request_cancel(jid)  # running job: flag only
    jobs_mod.update_progress(jid, phase="failed", error="genuine engine crash")
    j = jobs_mod.get(jid)
    assert j["phase"] == "failed"
    assert j["error_code"] == jobs_mod.E_ENGINE
    assert jobs_mod.get_status(jid)["phase"] == "failed"
    assert jobs_mod.get_status(jid)["error"] == "genuine engine crash"


def test_row_terminal_phase_wins_over_conflicting_terminal_progress():
    """Even if progress somehow contains a DIFFERENT terminal phase, the row
    is the authority."""
    jid = _new_job("conflicting terminals")
    jobs_mod.update_progress(jid, phase="generating")
    jobs_mod.request_cancel(jid)
    jobs_mod.update_progress(jid, phase="cancelled")
    # force a conflicting terminal into progress via direct SQL (simulates any
    # historical/corrupt writer) — get_status must still say cancelled
    with jobs_mod._WRITE_LOCK:
        jobs_mod._db().execute(
            "UPDATE jobs SET progress=? WHERE id=?",
            (json.dumps({"phase": "done", "final": "x.png"}), jid))
        jobs_mod._db().commit()
    assert jobs_mod.get_status(jid)["phase"] == "cancelled"


# ---- concurrency ----------------------------------------------------------

def test_concurrent_updates_lose_nothing():
    jid = _new_job("concurrency test")
    n_threads, n_writes = 8, 25
    errors = []

    def writer(t):
        try:
            for i in range(n_writes):
                jobs_mod.update_progress(jid, **{f"k_{t}_{i}": i})
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(t,)) for t in range(n_threads)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=30)
    assert not errors
    s = jobs_mod.get_status(jid)
    missing = [f"k_{t}_{i}" for t in range(n_threads) for i in range(n_writes)
               if f"k_{t}_{i}" not in s]
    assert not missing, f"lost {len(missing)} updates, e.g. {missing[:5]}"


def test_events_stream_reads_db_single_terminal_event(tmp_path):
    jid = _new_job("events test")
    run_dir = tmp_path / jid
    run_dir.mkdir()
    server._status(run_dir, id=jid, brief="events test", phase="done",
                   final="final.png")
    resp = server.events(jid)

    async def _first_chunk():
        async for chunk in resp.body_iterator:
            return chunk

    import asyncio
    first = asyncio.run(_first_chunk())
    assert first.startswith("data: ")
    payload = json.loads(first[len("data: "):].strip())
    assert payload["phase"] == "done"
