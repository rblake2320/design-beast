"""Cancellation-correctness unit tests — no live server, no GPU, no generation.

    cd design-beast && python -m pytest studio/tests/test_cancel.py -q

SAFETY: conftest.py redirects jobs.DB_PATH to a throwaway SQLite file BEFORE
server.py is imported, so its module-level jobs.init()/recover_orphans() cannot
touch the live studio/jobs.db (which may hold another agent's running jobs).
"""
import time
from pathlib import Path

import jobs as jobs_mod  # noqa: E402  (path + DB redirect done in conftest.py)

assert "beast-test" in str(jobs_mod.DB_PATH), \
    "conftest.py must redirect jobs.DB_PATH before server is imported"

import server  # noqa: E402  (init() runs against the conftest temp DB)


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeRequests:
    """Records every get/post; per-URL canned responses; optional raising."""

    def __init__(self, responses=None, post_raises=False):
        self.calls = []
        self.responses = responses or {}  # url-suffix -> payload
        self.post_raises = post_raises

    def _lookup(self, url):
        for suffix, payload in self.responses.items():
            if url.endswith(suffix):
                return payload
        return {}

    def get(self, url, **kw):
        self.calls.append(("get", url, None))
        return FakeResp(self._lookup(url))

    def post(self, url, **kw):
        self.calls.append(("post", url, kw.get("json")))
        if self.post_raises:
            raise ConnectionError("comfy down")
        return FakeResp(self._lookup(url))

    def urls(self, verb):
        return [u for v, u, _ in self.calls if v == verb]


def _new_job(brief="cancel test") -> str:
    jid, created = jobs_mod.create("create", "local:flux.1-schnell", brief, {})
    assert created
    return jid


def _owned(run_id, *pids):
    server._COMFY_PROMPTS[run_id] = set(pids)


def teardown_function(_):
    server._COMFY_PROMPTS.clear()


# ---- _comfy_cancel_run: atomic per-job endpoint, never /interrupt ---------

def test_no_owned_prompts_means_no_comfy_calls(monkeypatch):
    fake = FakeRequests()
    monkeypatch.setattr(server, "requests", fake)
    note = server._comfy_cancel_run("job-without-prompts")
    assert "no ComfyUI prompts owned" in note
    assert fake.calls == []  # old code would have blind-posted /interrupt


def test_one_atomic_cancel_call_per_owned_pid_never_interrupt(monkeypatch):
    fake = FakeRequests({"/cancel": {"cancelled": True}})
    monkeypatch.setattr(server, "requests", fake)
    _owned("job-a", "p1", "p2")
    note = server._comfy_cancel_run("job-a")
    posts = fake.urls("post")
    assert sorted(posts) == [
        f"http://localhost:{server.COMFY_PORT}/api/jobs/p1/cancel",
        f"http://localhost:{server.COMFY_PORT}/api/jobs/p2/cancel",
    ]
    assert not any("/interrupt" in u for u in posts + fake.urls("get"))
    assert not any(u.endswith("/queue") for u in posts + fake.urls("get"))
    assert note.count("cancelled") == 2


def test_unknown_or_finished_pid_is_safe_noop(monkeypatch):
    """ComfyUI returns {"cancelled": false} (HTTP 200) for unknown/terminal ids
    — idempotent no-op, reported as such, never an error."""
    fake = FakeRequests({"/cancel": {"cancelled": False}})
    monkeypatch.setattr(server, "requests", fake)
    _owned("job-b", "p-finished")
    note = server._comfy_cancel_run("job-b")
    assert "no-op" in note
    assert "failed" not in note
    assert not any("/interrupt" in u for u in fake.urls("post"))


def test_comfy_unreachable_is_reported_not_raised(monkeypatch):
    fake = FakeRequests(post_raises=True)
    monkeypatch.setattr(server, "requests", fake)
    _owned("job-d", "p4")
    note = server._comfy_cancel_run("job-d")
    assert "cancel call failed" in note  # no exception escapes


# ---- INV-3: Beast cancel flag wins over Comfy history status_str=error ----

def test_cancel_flag_wins_over_history_error(monkeypatch, tmp_path):
    """An interrupted prompt lands in /history as status_str='error' exactly
    like a crash. If the Beast cancel flag is set, the poll loop must classify
    it as cancelled, not as an engine failure."""
    monkeypatch.setattr(server, "ensure_comfy", lambda *a, **kw: True)
    monkeypatch.setattr(server.time, "sleep", lambda s: None)
    fake = FakeRequests({
        "/prompt": {"prompt_id": "pX"},
        "/history/pX": {"pX": {"status": {"completed": False, "status_str": "error"}}},
    })
    monkeypatch.setattr(server, "requests", fake)
    # cancel lands AFTER the top-of-loop check, BEFORE the history read —
    # first cancelled() call says False, every later one says True
    flags = iter([False])
    monkeypatch.setattr(jobs_mod, "cancelled", lambda jid: next(flags, True))
    run_dir = tmp_path / "20260726_000000_test"
    run_dir.mkdir()
    r = server.comfy_flux_image("a prompt", run_dir / "cand1.png", "1:1")
    assert r.get("cancelled") is True
    assert r["error"] == "cancelled by request"


# ---- cancel endpoint ------------------------------------------------------

def test_cancel_endpoint_keeps_api_shape_and_no_blind_interrupt(monkeypatch):
    fake = FakeRequests()
    monkeypatch.setattr(server, "requests", fake)
    jid = _new_job()
    resp = server.cancel_job(jid)
    assert resp["ok"] is True          # pre-existing contract (test_p0 relies on it)
    assert "note" in resp
    assert not any(u.endswith("/interrupt") for u in fake.urls("post"))
    assert jobs_mod.get(jid)["phase"] == "cancelled"  # queued job cancels instantly


# ---- candidate generation observes cancellation ---------------------------

def _forbid_generation(monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("generation backend must not be called after cancel")
    for fn in ("comfy_flux_image", "flux_local", "nim_flux", "hf_generate"):
        monkeypatch.setattr(server, fn, boom)


def test_generate_one_short_circuits_when_already_cancelled(monkeypatch, tmp_path):
    _forbid_generation(monkeypatch)
    jid = _new_job()
    jobs_mod.request_cancel(jid)
    run_dir = tmp_path / jid
    run_dir.mkdir()
    req = server.RunReq(brief="cancelled before start")
    cand = server._generate_one(run_dir, 1, "prompt", req)
    assert cand["state"] == "cancelled"
    assert "error" not in cand


def test_run_loop_observes_cancel_before_all_candidates_finish(monkeypatch, tmp_path):
    """Candidate 1 finishes fast and triggers cancel; 2-4 are slow. The run must
    reach 'cancelled' without waiting for the slow candidates (old pool.map code
    waited for all four)."""
    monkeypatch.setattr(server, "ensure_backend", lambda *a, **kw: True)
    jid = _new_job("early cancel")
    run_dir = tmp_path / jid
    run_dir.mkdir()
    (run_dir / "status.json").write_text('{"brief": "early cancel"}')
    finished = []

    def fake_generate(rd, i, prompt, req):
        if i == 1:
            jobs_mod.request_cancel(jid)  # cancel lands mid-generation
        else:
            time.sleep(2.0)
        finished.append(i)
        return {"i": i, "state": "done", "score": 9, "kill": False,
                "fix": "", "file": "x.png"}

    monkeypatch.setattr(server, "_generate_one", fake_generate)
    req = server.RunReq(brief="early cancel", variations=["a", "b", "c", "d"])
    t0 = time.time()
    server._run_loop(run_dir, req)
    elapsed = time.time() - t0
    assert jobs_mod.get(jid)["phase"] == "cancelled"
    import json as _json
    assert _json.loads((run_dir / "status.json").read_text())["phase"] == "cancelled"
    assert elapsed < 1.5, f"run loop waited {elapsed:.1f}s — it blocked on slow candidates"
    assert len(finished) < 4, "all four candidates ran to completion before cancel took effect"


def test_animate_reports_cancelled_not_failed(monkeypatch, tmp_path):
    """A cancelled wan/ltx render returns {'error': ..., 'cancelled': True} —
    the animate() closure must mark the job cancelled/E_CANCELLED, not
    failed/E_ENGINE, and must never fall back to the credit-spending cloud
    path for a cancelled render."""
    src = tmp_path / "src.png"
    src.write_bytes(b"png-bytes")
    monkeypatch.setattr(server, "RUNS", tmp_path)
    monkeypatch.setattr(server, "_resolve", lambda f: src)
    monkeypatch.setattr(server, "wan_animate",
                        lambda *a, **kw: {"error": "cancelled by request",
                                          "cancelled": True})

    def no_cloud(*a, **kw):
        raise AssertionError("cloud fallback must not fire for a cancelled render")
    monkeypatch.setattr(server, "hf_generate", no_cloud)

    req = server.AnimateReq(file="src.png", quality="fast",
                            allow_cloud_fallback=True)
    jid = server.animate(req)["id"]
    for _ in range(50):  # worker thread: wait for a terminal phase
        j = jobs_mod.get(jid)
        if j["phase"] in jobs_mod.TERMINAL:
            break
        time.sleep(0.1)
    assert j["phase"] == "cancelled", f"expected cancelled, got {j['phase']} ({j['error']})"
    assert j["error_code"] == jobs_mod.E_CANCELLED
    assert jobs_mod.get_status(jid)["phase"] == "cancelled"


def test_run_loop_observes_cancel_with_zero_completions(monkeypatch, tmp_path):
    """Codex invariant: cancellation must be observed even when EVERY candidate
    is still blocked (e.g. long NIM HTTP calls) — no completion required."""
    monkeypatch.setattr(server, "ensure_backend", lambda *a, **kw: True)
    jid = _new_job("cancel while all blocked")
    run_dir = tmp_path / jid
    run_dir.mkdir()
    (run_dir / "status.json").write_text('{"brief": "cancel while all blocked"}')

    def slow_generate(rd, i, prompt, req):
        time.sleep(3.0)  # simulates a blocking NIM call
        return {"i": i, "state": "done", "score": 9, "kill": False,
                "fix": "", "file": "x.png"}

    monkeypatch.setattr(server, "_generate_one", slow_generate)
    import threading as _t
    _t.Timer(0.3, jobs_mod.request_cancel, args=(jid,)).start()
    req = server.RunReq(brief="cancel while all blocked",
                        variations=["a", "b", "c", "d"])
    t0 = time.time()
    server._run_loop(run_dir, req)
    elapsed = time.time() - t0
    assert jobs_mod.get(jid)["phase"] == "cancelled"
    assert elapsed < 2.5, (f"run loop took {elapsed:.1f}s — cancel was not observed "
                           "until a candidate completed")
