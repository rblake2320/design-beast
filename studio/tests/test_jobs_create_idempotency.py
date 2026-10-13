"""Concurrent idempotency for jobs.create on real SQLite, one connection per thread.

Same key from many callers must yield exactly one job id, exactly one created=True,
and no exception (UNIQUE violation or database locked). Distinct keys must each
create one job.
"""
import threading

import pytest

import jobs


@pytest.fixture(autouse=True)
def _own_db(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs, "DB_PATH", tmp_path / "create-idempotency.db")
    monkeypatch.setattr(jobs, "_LOCAL", threading.local())
    jobs.init()
    yield
    jobs._db().close()


def _race(workers, call):
    """Start all callers at once; return (results, errors) in caller order."""
    barrier = threading.Barrier(workers)
    results = [None] * workers
    errors = []
    lock = threading.Lock()

    def run(slot):
        try:
            barrier.wait()
            results[slot] = call(slot)
        except Exception as exc:  # noqa: BLE001 — every failure is evidence
            with lock:
                errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            jobs._db().close()

    threads = [threading.Thread(target=run, args=(slot,)) for slot in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    return results, errors


@pytest.mark.parametrize("round_no", range(5))
def test_same_key_eight_callers_yield_one_job(round_no):
    key = f"same-key-{round_no}"
    results, errors = _race(8, lambda slot: jobs.create("create", "owned", "brief", {}, key))
    assert errors == []
    ids = {jid for jid, _ in results}
    created = [flag for _, flag in results]
    assert len(ids) == 1, ids
    assert created.count(True) == 1, created
    assert created.count(False) == 7, created
    rows = jobs._db().execute("SELECT COUNT(*) AS n FROM jobs WHERE idempotency_key=?", (key,)).fetchone()
    assert rows["n"] == 1


def test_distinct_keys_eight_callers_each_create_one_job():
    results, errors = _race(8, lambda slot: jobs.create("create", "owned", "brief", {}, f"distinct-{slot}"))
    assert errors == []
    assert len({jid for jid, _ in results}) == 8
    assert all(flag for _, flag in results)


def test_no_key_callers_each_create_a_job():
    results, errors = _race(8, lambda slot: jobs.create("create", "owned", "brief", {}, None))
    assert errors == []
    assert len({jid for jid, _ in results}) == 8
    assert all(flag for _, flag in results)


def test_existing_key_returns_original_job_sequentially():
    first = jobs.create("create", "owned", "brief", {}, "seq-key")
    second = jobs.create("create", "owned", "brief", {}, "seq-key")
    assert first[1] is True and second == (first[0], False)
