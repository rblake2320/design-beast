"""Real temporary SQLite regression tests; no server, provider or GPU calls."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import sqlite3
import threading
import uuid

import pytest
import jobs


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs, "DB_PATH", tmp_path / "jobs.db")
    monkeypatch.setattr(jobs, "_LOCAL", threading.local())
    jobs.init()
    yield
    jobs._db().close()


def create(key=None, kind="create"):
    return jobs.create(kind, "synthetic", "collision regression", {}, key)


def test_same_second_shared_uuid_prefix_does_not_collide(monkeypatch):
    values = iter([uuid.UUID("abcd0000-0000-4000-8000-000000000001"),
                   uuid.UUID("abcd0000-0000-4000-8000-000000000002")])
    monkeypatch.setattr(jobs.uuid, "uuid4", lambda: next(values))
    monkeypatch.setattr(jobs.time, "strftime", lambda fmt: "20260919_000000")
    first, second = create(), create()
    assert first[1] and second[1] and first[0] != second[0]
    assert len(first[0].rsplit("_", 1)[1]) == 32


def test_exact_id_collision_retries_without_overwriting(monkeypatch):
    original_uuid = uuid.uuid4
    repeated = original_uuid()
    values = iter([repeated, repeated, original_uuid()])
    monkeypatch.setattr(jobs.uuid, "uuid4", lambda: next(values))
    monkeypatch.setattr(jobs.time, "strftime", lambda fmt: "20260919_000000")
    first = create("first")
    second = create("second")
    assert first[0] != second[0]
    assert jobs.get(first[0])["idempotency_key"] == "first"
    assert jobs.get(second[0])["idempotency_key"] == "second"


def test_exhausted_collision_budget_rolls_back_and_fails(monkeypatch):
    repeated = uuid.uuid4()
    calls = []
    def next_uuid():
        calls.append(1)
        return repeated
    monkeypatch.setattr(jobs.uuid, "uuid4", next_uuid)
    monkeypatch.setattr(jobs.time, "strftime", lambda fmt: "20260919_000000")
    create()
    with pytest.raises(RuntimeError, match="job ID collision retry budget exhausted"):
        create()
    assert len(calls) == 4  # original + three bounded attempts
    assert not jobs._db().in_transaction
    assert jobs._db().execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


def test_other_integrity_errors_propagate_and_rollback():
    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL constraint failed: jobs.kind"):
        create(kind=None)
    assert not jobs._db().in_transaction
    assert create()[1]


@pytest.mark.parametrize("shared_python_lock", [True, False])
def test_concurrent_idempotency_returns_one_created_job(monkeypatch, shared_python_lock):
    if not shared_python_lock:
        # Independent SQLite connections must serialize even without a common
        # Python lock, as is the case for separate server processes.
        monkeypatch.setattr(jobs, "_WRITE_LOCK", nullcontext())
    barrier = threading.Barrier(8)
    def worker(_):
        try:
            barrier.wait(timeout=10)
            return create("concurrent-key")
        finally:
            jobs._db().close()
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(worker, range(8)))
    assert sum(created for _, created in results) == 1
    assert len({jid for jid, _ in results}) == 1
    assert jobs._db().execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


@pytest.mark.parametrize("key", ["replay-key", ""])
def test_idempotency_replay_does_not_allocate_new_identifier(monkeypatch, key):
    original = create(key)
    def forbidden():
        raise AssertionError("replay must not allocate")
    monkeypatch.setattr(jobs.uuid, "uuid4", forbidden)
    assert create(key) == (original[0], False)
