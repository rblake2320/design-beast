"""GPU-free tests for mutually exclusive local NIM backend classes."""
from types import SimpleNamespace

import jobs as jobs_mod

assert "beast-test" in str(jobs_mod.DB_PATH), \
    "conftest.py must redirect jobs.DB_PATH before server is imported"

import server  # noqa: E402


def _result(returncode=0, stdout=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout)


def test_ready_target_does_not_touch_other_containers(monkeypatch):
    monkeypatch.setattr(server.requests, "get",
                        lambda *a, **kw: SimpleNamespace(ok=True))
    calls = []
    monkeypatch.setattr(server.subprocess, "run",
                        lambda *a, **kw: calls.append(a[0]))

    assert server.ensure_backend("nim-trellis") is True
    assert calls == []


def test_trellis_stops_all_running_image_nims_before_start(monkeypatch):
    health = iter([False, True])
    monkeypatch.setattr(server.requests, "get",
                        lambda *a, **kw: SimpleNamespace(ok=next(health)))
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["docker", "inspect", "-f"]:
            return _result(stdout="true\n")
        return _result()

    monkeypatch.setattr(server.subprocess, "run", run)
    monkeypatch.setattr(server.time, "sleep", lambda _: None)

    assert server.ensure_backend("nim-trellis", wait_s=1) is True
    assert calls == [
        ["docker", "inspect", "-f", "{{.State.Running}}", "nim-flux"],
        ["docker", "stop", "nim-flux"],
        ["docker", "inspect", "-f", "{{.State.Running}}", "nim-kontext"],
        ["docker", "stop", "nim-kontext"],
        ["docker", "inspect", "-f", "{{.State.Running}}", "nim-flux2"],
        ["docker", "stop", "nim-flux2"],
        ["docker", "start", "nim-trellis"],
    ]


def test_image_nim_stops_only_running_trellis_before_start(monkeypatch):
    health = iter([False, True])
    monkeypatch.setattr(server.requests, "get",
                        lambda *a, **kw: SimpleNamespace(ok=next(health)))
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["docker", "inspect", "-f"]:
            return _result(stdout="true")
        return _result()

    monkeypatch.setattr(server.subprocess, "run", run)
    monkeypatch.setattr(server.time, "sleep", lambda _: None)

    assert server.ensure_backend("nim-kontext", wait_s=1) is True
    assert calls == [
        ["docker", "inspect", "-f", "{{.State.Running}}", "nim-trellis"],
        ["docker", "stop", "nim-trellis"],
        ["docker", "start", "nim-kontext"],
    ]


def test_absent_or_stopped_conflicts_are_not_stopped(monkeypatch):
    health = iter([False, True])
    monkeypatch.setattr(server.requests, "get",
                        lambda *a, **kw: SimpleNamespace(ok=next(health)))
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[-1] == "nim-flux":
            return _result(returncode=1)
        if cmd[-1] in {"nim-kontext", "nim-flux2"} and cmd[1] == "inspect":
            return _result(stdout="false\n")
        return _result()

    monkeypatch.setattr(server.subprocess, "run", run)
    monkeypatch.setattr(server.time, "sleep", lambda _: None)

    assert server.ensure_backend("nim-trellis", wait_s=1) is True
    assert not any(call[1] == "stop" for call in calls)
    assert calls[-1] == ["docker", "start", "nim-trellis"]


def test_failed_conflict_stop_aborts_before_target_start(monkeypatch):
    monkeypatch.setattr(server.requests, "get",
                        lambda *a, **kw: SimpleNamespace(ok=False))
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1] == "inspect":
            return _result(stdout="true")
        if cmd[1] == "stop":
            return _result(returncode=1)
        return _result()

    monkeypatch.setattr(server.subprocess, "run", run)

    assert server.ensure_backend("nim-trellis") is False
    assert ["docker", "start", "nim-trellis"] not in calls


def test_cancel_checkpoint_runs_between_inspect_and_stop(monkeypatch, tmp_path):
    jid, _ = jobs_mod.create(
        "refine", "local:flux.1-kontext", "cancel during swap", {})
    run_dir = tmp_path / jid
    run_dir.mkdir()
    monkeypatch.setattr(server.requests, "get",
                        lambda *a, **kw: SimpleNamespace(ok=False))
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1] == "inspect":
            jobs_mod.request_cancel(jid)
            return _result(stdout="true")
        return _result()

    monkeypatch.setattr(server.subprocess, "run", run)

    try:
        server.ensure_backend("nim-kontext", run_dir)
        assert False, "cancelled backend swap returned normally"
    except jobs_mod.JobCancelled:
        pass
    assert not any(call[1] in {"stop", "start"} for call in calls)
