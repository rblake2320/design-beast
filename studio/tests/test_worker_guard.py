"""Every non-create worker must end in a terminal phase, using the real job store.

Regression for: refine job stayed 'running' forever when the judge raised.
Run: python -m pytest studio/tests/test_worker_guard.py -q
"""
import jobs as jobs_mod  # noqa: E402  (path + DB redirect done in conftest.py)
import pytest  # noqa: E402
import server  # noqa: E402


def _job():
    run_dir, created = server._new_run("worker guard probe", "local:flux.1-schnell", "refine")
    assert created
    return run_dir


def test_exception_in_worker_becomes_terminal_failure():
    run_dir = _job()

    def judge_down():
        raise ConnectionError("ollama not answering (probe)")

    server._guarded(run_dir, judge_down)()
    j = jobs_mod.get(run_dir.name)
    assert j["phase"] == "failed"
    assert "ConnectionError" in j["error"]


def test_cancel_and_deadline_map_to_their_terminal_phases():
    run_dir = _job()

    def cancelled():
        raise server.JobCancelled(run_dir.name)

    server._guarded(run_dir, cancelled)()
    assert jobs_mod.get(run_dir.name)["phase"] == "cancelled"

    run_dir = _job()

    def timed_out():
        raise server.JobTimeout(run_dir.name)

    server._guarded(run_dir, timed_out)()
    assert jobs_mod.get(run_dir.name)["phase"] == "failed"


def test_clean_worker_control_leaves_phase_to_the_worker():
    run_dir = _job()
    server._guarded(run_dir, lambda: None)()
    assert jobs_mod.get(run_dir.name)["phase"] == "queued"
