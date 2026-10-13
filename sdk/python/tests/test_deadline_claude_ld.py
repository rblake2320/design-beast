"""wait(timeout=...) is a total deadline, proved against real local HTTP servers (no transport mocks).

Each case runs the SDK call in a watchdog thread, so a client that ignores its deadline fails here instead of hanging
the suite. Successful terminal controls prove the bound does not come from refusing everything.
"""
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SDK_ROOT = Path(__file__).resolve().parents[1]
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from beast_studio_client import BeastStudioClient, BeastStudioError  # noqa: E402

DEADLINE = 1.0
SLACK = 1.0  # scheduling allowance above the requested deadline
WATCHDOG = 8.0  # a client still blocked here ignored its deadline


@pytest.fixture
def studio():
    """Real HTTP server; each test assigns behaviour per path prefix."""
    routes = {}
    stop = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            for prefix, behaviour in routes.items():
                if self.path.startswith(prefix):
                    try:
                        behaviour(self, stop)
                    except (ConnectionError, OSError):
                        pass
                    return
            self.send_error(404)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield routes, f"http://127.0.0.1:{server.server_address[1]}"
    stop.set()
    server.shutdown()
    server.server_close()


def sse_head(handler):
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    handler.end_headers()
    handler.wfile.flush()


def quiet_sse(handler, stop):
    sse_head(handler)
    stop.wait(30)


def trickle_sse(handler, stop):
    """Keeps the socket busy with one byte at a time, never completing a line, so per-read timeouts never fire."""
    sse_head(handler)
    while not stop.wait(0.1):
        handler.wfile.write(b":")
        handler.wfile.flush()


def json_reply(payload):
    def reply(handler, stop):
        body = json.dumps(payload).encode()
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
    return reply


def stalled_json(handler, stop):
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", "100")
    handler.end_headers()
    handler.wfile.write(b'{"phase": ')
    handler.wfile.flush()
    stop.wait(30)


def broken_sse(handler, stop):
    handler.send_error(503)


def bounded(call):
    """Run call() in a watchdog thread; return (outcome, elapsed, finished)."""
    box = {}

    def run():
        try:
            box["value"] = call()
        except Exception as error:  # the SDK's typed error is the expected outcome
            box["error"] = error

    start = time.monotonic()
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(WATCHDOG)
    return box, time.monotonic() - start, not worker.is_alive()


def assert_deadline_error(box, elapsed, finished):
    assert finished, f"wait() still blocked after {WATCHDOG}s with a {DEADLINE}s deadline"
    assert isinstance(box.get("error"), BeastStudioError), box
    assert "terminal phase within" in str(box["error"]), box["error"]
    assert elapsed < DEADLINE + SLACK, elapsed


def test_quiet_sse_stream_honours_wait_deadline(studio):
    routes, url = studio
    routes["/api/events/"] = quiet_sse
    routes["/api/run/"] = json_reply({"phase": "running"})
    assert_deadline_error(*bounded(lambda: BeastStudioClient(url).wait("r1", timeout=DEADLINE, poll_interval=0.1)))


def test_trickling_sse_stream_honours_wait_deadline(studio):
    routes, url = studio
    routes["/api/events/"] = trickle_sse
    routes["/api/run/"] = json_reply({"phase": "running"})
    assert_deadline_error(*bounded(lambda: BeastStudioClient(url).wait("r1", timeout=DEADLINE, poll_interval=0.1)))


def test_polling_fallback_with_stalled_status_body_honours_wait_deadline(studio):
    routes, url = studio
    routes["/api/events/"] = broken_sse
    routes["/api/run/"] = stalled_json
    assert_deadline_error(*bounded(lambda: BeastStudioClient(url).wait("r1", timeout=DEADLINE, poll_interval=0.1)))


def test_polling_fallback_never_terminal_honours_wait_deadline(studio):
    routes, url = studio
    routes["/api/events/"] = broken_sse
    routes["/api/run/"] = json_reply({"phase": "running"})
    assert_deadline_error(*bounded(lambda: BeastStudioClient(url).wait("r1", timeout=DEADLINE, poll_interval=5)))


def test_terminal_sse_snapshot_returns_within_deadline(studio):
    routes, url = studio

    def finishing(handler, stop):
        sse_head(handler)
        handler.wfile.write(b'data: {"phase": "generating"}\n\n')
        handler.wfile.flush()
        time.sleep(0.2)
        handler.wfile.write(b'data: {"phase": "done", "final": "final.png"}\n\n')
        handler.wfile.flush()

    routes["/api/events/"] = finishing
    box, elapsed, finished = bounded(lambda: BeastStudioClient(url).wait("r1", timeout=5))
    assert finished and box.get("value") == {"phase": "done", "final": "final.png"}, box
    assert elapsed < 5


def test_terminal_status_via_polling_fallback_returns_within_deadline(studio):
    routes, url = studio
    routes["/api/events/"] = broken_sse
    routes["/api/run/"] = json_reply({"phase": "failed", "error": "boom"})
    box, elapsed, finished = bounded(lambda: BeastStudioClient(url).wait("r1", timeout=5, poll_interval=0.1))
    assert finished and box.get("value") == {"phase": "failed", "error": "boom"}, box
    assert elapsed < 5


def test_unbounded_stream_survives_a_phase_quieter_than_the_request_timeout(studio):
    """The server emits only on phase change; without a deadline a long quiet phase is normal, not a failure."""
    routes, url = studio

    def slow_phase(handler, stop):
        sse_head(handler)
        handler.wfile.write(b'data: {"phase": "generating"}\n\n')
        handler.wfile.flush()
        time.sleep(1.5)
        handler.wfile.write(b'data: {"phase": "done"}\n\n')
        handler.wfile.flush()

    routes["/api/events/"] = slow_phase
    client = BeastStudioClient(url, timeout=0.5)
    box, elapsed, finished = bounded(lambda: list(client.stream_events("r1")))
    assert finished and box.get("value") == [{"phase": "generating"}, {"phase": "done"}], box


# ---- reaping: after wait() returns at its deadline, nothing of it may keep running ----
# Raw HTTP: a complete status line, then a header that never ends (one byte per 30 ms), so neither
# per-read inactivity timeouts nor body-level deadline checks ever fire. The server side records when
# the client actually closes the connection; an abandoned worker or socket keeps the drip alive.

class Drips:
    def __init__(self):
        self.lock = threading.Lock()
        self.open = 0
        self.started = 0

    def begin(self):
        with self.lock:
            self.open += 1
            self.started += 1

    def end(self):
        with self.lock:
            self.open -= 1


def dripping(drips, head):
    def behaviour(handler, stop):
        drips.begin()
        try:
            handler.wfile.write(head)
            handler.wfile.flush()
            while not stop.wait(0.03):
                handler.wfile.write(b"x")
                handler.wfile.flush()
        finally:
            drips.end()
    return behaviour


HEADER_DRIP = b"HTTP/1.1 200 OK\r\nX-Drip: "
BODY_DRIP = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 100000\r\n\r\n"


def sdk_threads():
    return sorted(t.name for t in threading.enumerate() if t.name.startswith("beast-"))


def assert_reaped(drips, threads_before):
    """Every dripping connection the SDK opened is closed by the client within 1 s, and no SDK thread remains."""
    assert drips.started, "fault was not injected: the SDK never reached the dripping endpoint"
    limit = time.monotonic() + 1.0
    while drips.open and time.monotonic() < limit:
        time.sleep(0.02)
    assert drips.open == 0, f"{drips.open} of {drips.started} dripping connections still open 1s after wait() returned"
    assert sdk_threads() == threads_before, sdk_threads()


@pytest.mark.parametrize("use_sse,events,status", [
    (True, HEADER_DRIP, HEADER_DRIP),
    (False, None, HEADER_DRIP),
    (False, None, BODY_DRIP),
    (True, BODY_DRIP, BODY_DRIP),
], ids=["sse-header-drip", "poll-header-drip", "poll-body-drip", "sse-body-drip"])
def test_deadline_closes_dripping_connections_and_leaves_no_worker(studio, use_sse, events, status):
    routes, url = studio
    drips = Drips()
    if events:
        routes["/api/events/"] = dripping(drips, events)
    routes["/api/run/"] = dripping(drips, status)
    before = sdk_threads()
    client = BeastStudioClient(url, timeout=2)
    for _ in range(3):
        box, elapsed, finished = bounded(lambda: client.wait("r1", timeout=0.3, poll_interval=0.05, use_sse=use_sse))
        assert finished and isinstance(box.get("error"), BeastStudioError), box
        assert "terminal phase within" in str(box["error"]), box["error"]
        assert elapsed < 0.3 + SLACK, elapsed
    assert_reaped(drips, before)


def test_reaping_keeps_session_state_and_terminal_results(studio):
    """Positive control on the reaping path: caller headers reach the server and a terminal status returns."""
    routes, url = studio
    seen = {}

    def status(handler, stop):
        seen["auth"] = handler.headers.get("X-Studio-Token")
        json_reply({"phase": "done"})(handler, stop)

    routes["/api/events/"] = broken_sse
    routes["/api/run/"] = status
    client = BeastStudioClient(url)
    client.session.headers["X-Studio-Token"] = "owned-test-token"
    before = sdk_threads()
    box, elapsed, finished = bounded(lambda: client.wait("r1", timeout=5, poll_interval=0.05))
    assert finished and box.get("value") == {"phase": "done"}, box
    assert seen["auth"] == "owned-test-token"
    time.sleep(0.1)
    assert sdk_threads() == before
