"""GPU-free tests for mutually exclusive local NIM backend classes."""
from contextlib import contextmanager
from types import SimpleNamespace
import time

import jobs as jobs_mod
import pytest

assert "beast-test" in str(jobs_mod.DB_PATH), \
    "conftest.py must redirect jobs.DB_PATH before server is imported"

import server  # noqa: E402


def _result(returncode=0, stdout=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout)


def test_ready_target_still_stops_running_conflicts_without_restart(monkeypatch):
    monkeypatch.setattr(server.requests, "get",
                        lambda *a, **kw: SimpleNamespace(ok=True))
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1] == "inspect":
            return _result(stdout="true")
        return _result()

    monkeypatch.setattr(server.subprocess, "run", run)

    assert server.ensure_backend("nim-trellis") is True
    assert ["docker", "stop", "nim-flux"] in calls
    assert ["docker", "stop", "nim-kontext"] in calls
    assert ["docker", "stop", "nim-flux2"] in calls
    assert ["docker", "stop", "nim-wan"] in calls
    assert ["docker", "start", "nim-trellis"] not in calls


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
        ["docker", "inspect", "-f", "{{.State.Running}}", "nim-wan"],
        ["docker", "stop", "nim-wan"],
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
        ["docker", "inspect", "-f", "{{.State.Running}}", "nim-wan"],
        ["docker", "stop", "nim-wan"],
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
        if cmd[-1] in {"nim-kontext", "nim-flux2", "nim-wan"} \
                and cmd[1] == "inspect":
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


def test_wan_stops_every_other_nim_before_start(monkeypatch):
    health = iter([False, True])
    monkeypatch.setattr(server.requests, "get",
                        lambda *a, **kw: SimpleNamespace(ok=next(health)))
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1] == "inspect":
            return _result(stdout="true")
        return _result()

    monkeypatch.setattr(server.subprocess, "run", run)
    monkeypatch.setattr(server.time, "sleep", lambda _: None)

    assert server.ensure_backend("nim-wan", wait_s=1) is True
    stopped = {call[-1] for call in calls if call[1] == "stop"}
    assert stopped == {"nim-flux", "nim-kontext", "nim-flux2", "nim-trellis"}
    assert calls[-1] == ["docker", "start", "nim-wan"]


def test_trellis_and_image_nims_treat_wan_as_conflict(monkeypatch):
    """WAN is heavy: neither TRELLIS nor an image NIM may leave it running."""
    monkeypatch.setattr(server.requests, "get",
                        lambda *a, **kw: SimpleNamespace(ok=True))

    for target in ("nim-trellis", "nim-flux", "nim-kontext", "nim-flux2"):
        calls = []

        def run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[1] == "inspect":
                return _result(stdout="true" if cmd[-1] == "nim-wan" else "false")
            return _result()

        monkeypatch.setattr(server.subprocess, "run", run)
        assert server.ensure_backend(target) is True
        assert ["docker", "stop", "nim-wan"] in calls
        assert ["docker", "start", target] not in calls


def test_backend_api_nim_start_routes_through_conflict_policy(monkeypatch):
    calls = []
    monkeypatch.setattr(
        server, "ensure_backend",
        lambda name, *args, **kwargs: calls.append(name) or True)
    monkeypatch.setattr(
        server.subprocess, "run",
        lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("NIM start bypassed ensure_backend")))

    response = server.backend(server.BackendReq(name="nim-wan", action="start"))
    assert response["ok"] is True
    assert calls == ["nim-wan"]


def test_backend_api_atomically_rejects_start_and_stop_while_leased(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "ensure_backend",
                        lambda *a, **kw: calls.append(("ensure", a)))
    monkeypatch.setattr(server.subprocess, "run",
                        lambda *a, **kw: calls.append(("run", a)))

    # Use the real atomic lease implementation rather than mocking a racy
    # read-only gpu_leases() snapshot.
    with jobs_mod.gpu_lease_nowait("test-active-job", "light") as acquired:
        assert acquired
        for name in ("nim-flux", "nim-kontext", "nim-flux2",
                     "nim-trellis", "nim-wan"):
            for action in ("start", "stop"):
                response = server.backend(
                    server.BackendReq(name=name, action=action))
                assert response.status_code == 409
                assert b"GPU" in response.body or b"gpu" in response.body
    assert calls == []


def test_backend_api_holds_heavy_lease_through_start_and_stop(monkeypatch):
    state = {"entered": False, "requests": []}

    @contextmanager
    def lease(holder, kind):
        assert holder.startswith("manual-backend:")
        assert kind == "heavy"
        state["requests"].append((holder, kind))
        state["entered"] = True
        try:
            yield True
        finally:
            state["entered"] = False

    def ensure(name):
        assert state["entered"], "start mutation ran outside manual GPU lease"
        return True

    def run(cmd, **kwargs):
        assert state["entered"], "stop mutation ran outside manual GPU lease"
        return _result()

    monkeypatch.setattr(server.jobs, "gpu_lease_nowait", lease)
    monkeypatch.setattr(server, "ensure_backend", ensure)
    monkeypatch.setattr(server.subprocess, "run", run)

    assert server.backend(
        server.BackendReq(name="nim-wan", action="start"))["ok"] is True
    assert not state["entered"]
    assert server.backend(
        server.BackendReq(name="nim-wan", action="stop"))["ok"] is True
    assert not state["entered"]
    assert len(state["requests"]) == 2


def test_backend_api_releases_manual_lease_when_mutation_raises(monkeypatch):
    before = {lease["holder"] for lease in jobs_mod.gpu_leases()}

    monkeypatch.setattr(
        server, "ensure_backend",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("start exploded")))
    with pytest.raises(RuntimeError, match="start exploded"):
        server.backend(server.BackendReq(name="nim-wan", action="start"))
    assert {lease["holder"] for lease in jobs_mod.gpu_leases()} == before

    monkeypatch.setattr(
        server.subprocess, "run",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("stop exploded")))
    with pytest.raises(RuntimeError, match="stop exploded"):
        server.backend(server.BackendReq(name="nim-wan", action="stop"))
    assert {lease["holder"] for lease in jobs_mod.gpu_leases()} == before


def test_backend_api_reaps_stale_lease_atomically_instead_of_false_busy(
        monkeypatch):
    stale_holder = "stale-manual-control"
    stale = time.time() - jobs_mod.LEASE_STALE_S - 10
    db = jobs_mod._db()
    db.execute(
        "INSERT INTO gpu_leases "
        "(resource, holder, job_id, kind, acquired, heartbeat) "
        "VALUES (?,?,?,?,?,?)",
        (jobs_mod.GPU_RESOURCE, stale_holder, stale_holder,
         "heavy", stale, stale))
    db.commit()
    calls = []
    monkeypatch.setattr(
        server, "ensure_backend",
        lambda name, *a, **kw: calls.append(name) or True)

    response = server.backend(
        server.BackendReq(name="nim-wan", action="start"))

    assert response["ok"] is True
    assert calls == ["nim-wan"]
    assert stale_holder not in {
        lease["holder"] for lease in jobs_mod.gpu_leases()}


class _DockerState:
    """Stateful docker subprocess fake for backend ownership/restore tests."""

    def __init__(self, states):
        self.states = dict(states)
        self.initial = dict(states)
        self.calls = []

    def run(self, cmd, **kwargs):
        self.calls.append(cmd)
        name = cmd[-1]
        if cmd[1] in {"inspect", "container"}:
            exists = name in self.states
            running = self.states.get(name, False)
            return _result(
                returncode=0 if exists else 1,
                stdout=("true\n" if running else "false\n"))
        if cmd[1] == "start":
            self.states[name] = True
            return _result()
        if cmd[1] == "stop":
            self.states[name] = False
            return _result()
        raise AssertionError(f"unexpected docker command: {cmd}")


@pytest.mark.parametrize("outcome", ["success", "failure", "cancel"])
def test_job_wan_restores_only_owned_backend_changes(
        monkeypatch, tmp_path, outcome):
    """Contract for server.job_backend(name, run_dir):

    the context snapshots target/conflicts, yields readiness after safe startup,
    and its finally restores only mutations owned by this job. Animate must
    hold this context around Wan inference, so all exit modes share cleanup.
    """
    docker = _DockerState({
        "nim-wan": False,
        "nim-flux": True,
        "nim-kontext": False,
        "nim-flux2": True,
        "nim-trellis": False,
    })
    monkeypatch.setattr(server.subprocess, "run", docker.run)
    monkeypatch.setattr(
        server.requests, "get",
        lambda *a, **kw: SimpleNamespace(ok=docker.states["nim-wan"]))
    monkeypatch.setattr(server.time, "sleep", lambda _: None)
    run_dir = tmp_path / "wan-job"
    run_dir.mkdir()

    try:
        with server.job_backend("nim-wan", run_dir) as ready:
            assert ready
            assert docker.states["nim-wan"] is True
            assert docker.states["nim-flux"] is False
            assert docker.states["nim-flux2"] is False
            if outcome == "failure":
                raise RuntimeError("engine failed")
            if outcome == "cancel":
                raise jobs_mod.JobCancelled("wan-job")
    except RuntimeError:
        assert outcome == "failure"
    except jobs_mod.JobCancelled:
        assert outcome == "cancel"

    assert docker.states == docker.initial
    # WAN was initially stopped, so this job owns exactly one start+stop pair.
    assert docker.calls.count(["docker", "start", "nim-wan"]) == 1
    assert docker.calls.count(["docker", "stop", "nim-wan"]) == 1
    # Only peers this job actually stopped may be restarted.
    assert docker.calls.count(["docker", "start", "nim-flux"]) == 1
    assert docker.calls.count(["docker", "start", "nim-flux2"]) == 1
    assert ["docker", "start", "nim-kontext"] not in docker.calls
    assert ["docker", "start", "nim-trellis"] not in docker.calls


def test_job_wan_never_stops_preexisting_target(monkeypatch, tmp_path):
    """A pre-running WAN belongs to the operator/another lifecycle, not this job."""
    docker = _DockerState({
        "nim-wan": True,
        "nim-flux": True,
        "nim-kontext": False,
        "nim-flux2": False,
        "nim-trellis": False,
    })
    monkeypatch.setattr(server.subprocess, "run", docker.run)
    monkeypatch.setattr(server.requests, "get",
                        lambda *a, **kw: SimpleNamespace(ok=True))
    run_dir = tmp_path / "wan-preexisting"
    run_dir.mkdir()

    with server.job_backend("nim-wan", run_dir) as ready:
        assert ready
        assert docker.states["nim-wan"] is True
        assert docker.states["nim-flux"] is False

    assert docker.states == docker.initial
    assert ["docker", "start", "nim-wan"] not in docker.calls
    assert ["docker", "stop", "nim-wan"] not in docker.calls
    assert docker.calls.count(["docker", "start", "nim-flux"]) == 1


def test_job_wan_startup_failure_restores_conflicts_without_stopping_wan(
        monkeypatch, tmp_path):
    docker = _DockerState({
        "nim-wan": False,
        "nim-flux": True,
        "nim-kontext": False,
        "nim-flux2": False,
        "nim-trellis": True,
    })

    def fail_wan_start(cmd, **kwargs):
        result = docker.run(cmd, **kwargs)
        if cmd == ["docker", "start", "nim-wan"]:
            docker.states["nim-wan"] = False
            return _result(returncode=1)
        return result

    monkeypatch.setattr(server.subprocess, "run", fail_wan_start)
    monkeypatch.setattr(server.requests, "get",
                        lambda *a, **kw: SimpleNamespace(ok=False))
    run_dir = tmp_path / "wan-start-failed"
    run_dir.mkdir()

    with server.job_backend("nim-wan", run_dir) as ready:
        assert ready is False

    assert docker.states == docker.initial
    assert ["docker", "stop", "nim-wan"] not in docker.calls
    assert docker.calls.count(["docker", "start", "nim-flux"]) == 1
    assert docker.calls.count(["docker", "start", "nim-trellis"]) == 1
    assert ["docker", "start", "nim-kontext"] not in docker.calls
    assert ["docker", "start", "nim-flux2"] not in docker.calls


def test_job_wan_cancel_immediately_after_conflict_stop_restores_it(
        monkeypatch, tmp_path):
    """Ownership must be recorded before the post-stop cancel checkpoint.

    This is the precise race where docker stop succeeds, cancellation fires
    before ensure_backend returns, and job_backend's finally must still know
    that this job owes the operator a restart.
    """
    docker = _DockerState({
        "nim-wan": False,
        "nim-flux": True,
        "nim-kontext": False,
        "nim-flux2": False,
        "nim-trellis": False,
    })
    monkeypatch.setattr(server.subprocess, "run", docker.run)
    monkeypatch.setattr(server.requests, "get",
                        lambda *a, **kw: SimpleNamespace(ok=False))

    def checkpoint(_jid):
        if ["docker", "stop", "nim-flux"] in docker.calls:
            raise jobs_mod.JobCancelled("cancelled after successful stop")

    monkeypatch.setattr(server.jobs, "checkpoint", checkpoint)
    run_dir = tmp_path / "wan-cancel-after-stop"
    run_dir.mkdir()

    with pytest.raises(jobs_mod.JobCancelled,
                       match="cancelled after successful stop"):
        with server.job_backend("nim-wan", run_dir):
            pytest.fail("cancellation should prevent context body entry")

    assert docker.states == docker.initial
    assert docker.calls.count(["docker", "stop", "nim-flux"]) == 1
    assert docker.calls.count(["docker", "start", "nim-flux"]) == 1
    assert ["docker", "start", "nim-kontext"] not in docker.calls
    assert ["docker", "start", "nim-flux2"] not in docker.calls
    assert ["docker", "start", "nim-trellis"] not in docker.calls
    assert ["docker", "start", "nim-wan"] not in docker.calls
    assert ["docker", "stop", "nim-wan"] not in docker.calls
