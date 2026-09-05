"""Storage contention uses real SQLite connections, never production data."""
from concurrent.futures import ThreadPoolExecutor
import threading
import uuid

import pytest

import jobs


@pytest.fixture(autouse=True)
def initialize_test_store(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "DB_PATH", tmp_path / "jobs.db")
    monkeypatch.setattr(jobs, "_LOCAL", threading.local())
    jobs.init()
    yield
    jobs._db().close()


def test_concurrent_same_key_creates_exactly_one_job():
    key = f"test-{uuid.uuid4().hex}"
    barrier = threading.Barrier(16)

    def create(_):
        barrier.wait(timeout=10)
        try:
            return jobs.create("create", "local", "same request", {}, key)
        finally:
            if hasattr(jobs._LOCAL, "conn"):
                jobs._LOCAL.conn.close()
                del jobs._LOCAL.conn

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(create, range(16)))
    assert len({jid for jid, _ in results}) == 1
    assert sum(created for _, created in results) == 1


@pytest.mark.parametrize("terminal", jobs.TERMINAL)
def test_direct_phase_writer_cannot_resurrect_terminal_job(terminal):
    jid, _ = jobs.create("create", "local", "terminal job", {})
    jobs.set_phase(jid, terminal)
    before = jobs.get(jid)
    jobs.set_phase(jid, "running")
    after = jobs.get(jid)
    assert after["phase"] == terminal
    assert after["finished"] == before["finished"]
    assert after["started"] == before["started"]


def test_recent_uses_created_index_without_sorting_history():
    details = " ".join(row[3] for row in jobs._db().execute(
        "EXPLAIN QUERY PLAN SELECT id, kind, model, brief, phase, error_code, created "
        "FROM jobs ORDER BY created DESC LIMIT 30"))
    assert "idx_jobs_created" in details
    assert "TEMP B-TREE" not in details
