import subprocess

import pytest

from bench import campaign_preflight


def test_shutdown_failure_remains_recordable():
    class Child:
        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout):
            raise subprocess.TimeoutExpired("owned test child", timeout)

    record = {"outcome": "preflight_only_ready"}
    campaign_preflight.stop_owned(Child(), record)
    assert record["outcome"] == "preflight_error"
    assert record["owned_server_stopped"] is False
    assert "TimeoutExpired" in record["cleanup_errors"][0]


def test_owned_child_stopped_before_caller_unwinds(monkeypatch):
    events = []

    class Child:
        pid = 123
        stopped = False

        def poll(self):
            return 0 if self.stopped else None

        def terminate(self):
            events.append("terminate")
            self.stopped = True

        def wait(self, timeout):
            events.append("wait")

    monkeypatch.setattr(campaign_preflight.subprocess, "Popen", lambda *a, **kw: Child())
    record = {}
    with pytest.raises(RuntimeError, match="request failed"):
        try:
            with campaign_preflight.owned_server([], None, record):
                raise RuntimeError("request failed")
        finally:
            events.append("caller_cleanup")
    assert events == ["terminate", "wait", "caller_cleanup"]
    assert record["owned_server_stopped"] is True
