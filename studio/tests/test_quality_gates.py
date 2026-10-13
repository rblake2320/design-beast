"""Quality-loop gates: accept bar, minimum candidates, bounded NVCF polling.

Run: python -m pytest studio/tests/test_quality_gates.py -q
The NVCF test runs against a real local HTTP server that never completes.
"""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest  # noqa: E402
import requests  # noqa: E402  (path + DB redirect done in conftest.py)
import server  # noqa: E402
from pydantic import ValidationError  # noqa: E402


# ---- accept bar -----------------------------------------------------------

@pytest.mark.parametrize("cand, expected", [
    ({"state": "done", "score": 6}, False),           # below bar: previously shipped (old bar was >3)
    ({"state": "done", "score": 4}, False),
    ({"state": "done", "score": 7}, True),            # judge pass
    ({"state": "done", "score": 9}, True),
    ({"state": "done", "score": 9, "kill": True}, False),
    ({"state": "failed", "score": 9}, False),
    ({"state": "done"}, False),                       # no score is not a pass
    ({"state": "done", "score": "7"}, False),         # malformed score is not a pass
])
def test_only_judge_passing_candidates_are_accepted(cand, expected):
    assert server.ACCEPT_SCORE == 7
    assert server._accepted(cand) is expected


# ---- minimum candidates -----------------------------------------------------

def test_one_or_three_variations_are_refused():
    for variations in (["a"], ["a", "b", "c"]):
        with pytest.raises(ValidationError):
            server.RunReq(brief="a brief", variations=variations)


def test_zero_or_four_variations_are_accepted():
    assert server.RunReq(brief="a brief").variations == []
    assert len(server.RunReq(brief="a brief", variations=["a", "b", "c", "d"]).variations) == 4


# ---- bounded NVCF polling (real local server, never completes) --------------

class _AlwaysPending(BaseHTTPRequestHandler):
    def _pending(self):
        # Consume any request body first: answering with an unread body can
        # make Windows reset the connection and fail the client early.
        n = int(self.headers.get("Content-Length") or 0)
        if n:
            self.rfile.read(n)
        self.send_response(202)
        self.send_header("NVCF-REQID", "req-1")
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_POST = _pending
    do_GET = _pending

    def log_message(self, *args):  # keep test output quiet
        pass


def test_nvcf_poll_gives_up_within_its_timeout():
    httpd = HTTPServer(("127.0.0.1", 0), _AlwaysPending)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{httpd.server_port}"
        with pytest.raises(TimeoutError, match="still pending"):
            server._nim_invoke(f"{base}/invoke", {}, {}, timeout=1,
                               poll_base=f"{base}/status", poll_interval=0.05)
    finally:
        httpd.shutdown()
        httpd.server_close()


# ---- whole-operation deadline holds for slow status responses ---------------

class _SlowStatus(BaseHTTPRequestHandler):
    """POST returns 202; each status GET takes 2s and then returns 200."""
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n:
            self.rfile.read(n)
        self.send_response(202)
        self.send_header("NVCF-REQID", "req-2")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        import time as _t
        _t.sleep(2)
        body = b'{"artifacts": []}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_nvcf_slow_status_cannot_overrun_deadline():
    import time as _t
    httpd = HTTPServer(("127.0.0.1", 0), _SlowStatus)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{httpd.server_port}"
        start = _t.monotonic()
        # Windows can surface the client-side cutoff as a socket abort
        # (ConnectionError) rather than a read timeout; the contract under
        # test is the deadline bound, so either failure class is accepted.
        with pytest.raises((TimeoutError, requests.exceptions.RequestException)):
            server._nim_invoke(f"{base}/invoke", {}, {}, timeout=1,
                               poll_base=f"{base}/status", poll_interval=0.01)
        elapsed = _t.monotonic() - start
        assert elapsed < 1.5, f"deadline overrun: returned after {elapsed:.3f}s with timeout=1"
    finally:
        httpd.shutdown()
        httpd.server_close()


# ---- whole-operation deadline holds for a stalled DNS lookup ----------------

def test_nvcf_dns_stall_cannot_overrun_deadline(monkeypatch):
    import time as _t
    # Fault: the resolver child is a real process that stalls for 5 seconds.
    monkeypatch.setattr(server, "_RESOLVE_CHILD", "import time; time.sleep(5)")
    start = _t.monotonic()
    with pytest.raises(TimeoutError):
        server._nim_invoke("http://nonexistent-host-for-deadline-test.invalid/invoke",
                           {}, {}, timeout=1, poll_base="http://x/status", poll_interval=0.01)
    elapsed = _t.monotonic() - start
    assert elapsed < 1.5, f"DNS stall overran the deadline: {elapsed:.3f}s with timeout=1"
