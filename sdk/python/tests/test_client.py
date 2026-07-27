"""GPU-free contract tests for the Python SDK. No live server, no network —
requests.Session.request is monkeypatched per-test.

    cd design-beast && python -m pytest sdk/python/tests -q
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SDK_ROOT = Path(__file__).resolve().parents[1]
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from beast_studio_client import BeastStudioClient, BeastStudioError  # noqa: E402


class FakeResponse:
    def __init__(self, status_code=200, payload=None, lines=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self._lines = lines or []

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")

    def iter_lines(self, decode_unicode=True):
        return iter(self._lines)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def client():
    c = BeastStudioClient(base_url="http://127.0.0.1:8787")
    c.session = MagicMock()
    return c


def _last_call(mock_session):
    args, kwargs = mock_session.request.call_args
    return args, kwargs


# ---- sync endpoints: verify method/path/body shape ----

def test_recipes_get(client):
    client.session.request.return_value = FakeResponse(payload=[{"name": "a", "title": "A"}])
    out = client.recipes()
    args, _ = _last_call(client.session)
    assert args[0] == "GET" and args[1] == "http://127.0.0.1:8787/api/recipes"
    assert out == [{"name": "a", "title": "A"}]


def test_upload_post_body(client):
    client.session.request.return_value = FakeResponse(payload={"file": "x.png"})
    client.upload("x.png", "data:image/png;base64,AAAA")
    args, kwargs = _last_call(client.session)
    assert args[0] == "POST" and args[1].endswith("/api/upload")
    assert kwargs["json"] == {"name": "x.png", "data": "data:image/png;base64,AAAA"}


def test_backend_action(client):
    client.session.request.return_value = FakeResponse(payload={"ok": True})
    client.backend("nim-flux", "start")
    _, kwargs = _last_call(client.session)
    assert kwargs["json"] == {"name": "nim-flux", "action": "start"}


@pytest.mark.parametrize("name,action,expected", [
    ("nim-wan", "start", 1530.0),
    ("nim-flux", "start", 510.0),
    ("nim-trellis", "start", 510.0),
    ("nim-wan", "stop", 150.0),
    ("comfyui", "start", 30),
])
def test_backend_timeout_matches_synchronous_server_budget(
        client, name, action, expected):
    client.session.request.return_value = FakeResponse(payload={"ok": True})
    client.backend(name, action)
    _, kwargs = _last_call(client.session)
    assert kwargs["timeout"] == expected


def test_backend_timeout_can_be_overridden(client):
    client.session.request.return_value = FakeResponse(payload={"ok": True})
    client.backend("nim-wan", "start", timeout=12)
    _, kwargs = _last_call(client.session)
    assert kwargs["timeout"] == 12


# ---- async-submit endpoints: privacy/credit flags default False ----

@pytest.mark.parametrize("method,args,flag", [
    ("refine", ("f.png", "make it red"), "allow_cloud_fallback"),
    ("animate", ("f.png",), "allow_cloud_fallback"),
    ("to3d", ("f.png",), "allow_hosted_fallback"),
])
def test_credit_privacy_flags_default_false(client, method, args, flag):
    client.session.request.return_value = FakeResponse(payload={"id": "j1"})
    getattr(client, method)(*args)
    _, kwargs = _last_call(client.session)
    assert kwargs["json"][flag] is False, (
        f"{method}() must default {flag} to False — sending True unprompted "
        "spends credits or leaks images off-machine (AGENT_ACCESS.md rule 1)")


def test_credit_flag_explicit_true_is_passed_through(client):
    client.session.request.return_value = FakeResponse(payload={"id": "j1"})
    client.animate("f.png", allow_cloud_fallback=True)
    _, kwargs = _last_call(client.session)
    assert kwargs["json"]["allow_cloud_fallback"] is True


def test_run_default_model_is_free_local(client):
    client.session.request.return_value = FakeResponse(payload={"id": "j1"})
    client.run(brief="a cozy reading nook")
    _, kwargs = _last_call(client.session)
    assert kwargs["json"]["model"] == "local:flux.1-schnell"


def test_run_idempotency_key_header(client):
    client.session.request.return_value = FakeResponse(payload={"id": "j1"})
    client.run(brief="x y z", idempotency_key="key-123")
    _, kwargs = _last_call(client.session)
    assert kwargs["headers"] == {"Idempotency-Key": "key-123"}


def test_to_ue_path_and_body(client):
    client.session.request.return_value = FakeResponse(payload={"id": "j1"})
    client.to_ue("runs/20260101_x/model.glb")
    args, kwargs = _last_call(client.session)
    assert args[1].endswith("/api/to_ue")
    assert kwargs["json"] == {"file": "runs/20260101_x/model.glb"}


# ---- status / control ----

def test_status_get(client):
    client.session.request.return_value = FakeResponse(payload={"phase": "done"})
    out = client.status("run1")
    args, _ = _last_call(client.session)
    assert args[1].endswith("/api/run/run1")
    assert out["phase"] == "done"


def test_cancel_post(client):
    client.session.request.return_value = FakeResponse(payload={"ok": True})
    client.cancel("run1")
    args, _ = _last_call(client.session)
    assert args[0] == "POST" and args[1].endswith("/api/job/run1/cancel")


def test_retry_post(client):
    client.session.request.return_value = FakeResponse(payload={"id": "run2"})
    client.retry("run1")
    args, _ = _last_call(client.session)
    assert args[0] == "POST" and args[1].endswith("/api/job/run1/retry")


def test_events_url(client):
    assert client.events_url("run1") == "http://127.0.0.1:8787/api/events/run1"


def test_run_id_is_encoded_in_all_control_urls(client):
    hostile = "../health?admin=1#fragment"
    encoded = "..%2Fhealth%3Fadmin%3D1%23fragment"
    client.status(hostile)
    assert client.session.calls[-1]["url"].endswith(f"/api/run/{encoded}")
    client.cancel(hostile)
    assert client.session.calls[-1]["url"].endswith(f"/api/job/{encoded}/cancel")
    client.retry(hostile)
    assert client.session.calls[-1]["url"].endswith(f"/api/job/{encoded}/retry")
    assert client.events_url(hostile).endswith(f"/api/events/{encoded}")


# ---- SSE consumption ----

def test_stream_events_parses_and_stops_at_terminal(client):
    lines = [
        'data: {"phase": "generating"}',
        "",
        'data: {"phase": "done", "final": "final.png"}',
        'data: {"phase": "done", "final": "final.png"}',  # must not be reached
    ]
    client.session.get.return_value = FakeResponse(lines=lines)
    events = list(client.stream_events("run1"))
    assert [e["phase"] for e in events] == ["generating", "done"]
    assert events[-1]["final"] == "final.png"


def test_wait_uses_sse_and_returns_terminal_snapshot(client):
    lines = ['data: {"phase": "generating"}', 'data: {"phase": "failed", "error": "boom"}']
    client.session.get.return_value = FakeResponse(lines=lines)
    out = client.wait("run1", use_sse=True)
    assert out == {"phase": "failed", "error": "boom"}


def test_wait_falls_back_to_polling_when_sse_unavailable(client, monkeypatch):
    import requests
    client.session.get.side_effect = requests.ConnectionError("connection refused")
    calls = {"n": 0}

    def fake_status(run_id):
        calls["n"] += 1
        return {"phase": "done"} if calls["n"] > 1 else {"phase": "running"}

    monkeypatch.setattr(client, "status", fake_status)
    out = client.wait("run1", poll_interval=0, use_sse=True)
    assert out == {"phase": "done"}
    assert calls["n"] == 2


# ---- transport-level error handling ----

def test_connection_error_raises_beast_studio_error(client):
    import requests
    client.session.request.side_effect = requests.ConnectionError("refused")
    with pytest.raises(BeastStudioError):
        client.health()


def test_api_level_error_is_not_raised_by_default(client):
    """API-level errors (validation, not-found) come back as {"error": ...}
    dicts by default — matching AGENT_ACCESS.md's contract — not exceptions."""
    client.session.request.return_value = FakeResponse(
        status_code=422, payload={"error": "short brief"})
    out = client.run(brief="ab")
    assert out == {"error": "short brief"}


def test_raise_for_status_opt_in():
    c = BeastStudioClient(raise_for_status=True)
    c.session = MagicMock()
    c.session.request.return_value = FakeResponse(status_code=500, payload={"error": "x"})
    with pytest.raises(RuntimeError):
        c.health()
