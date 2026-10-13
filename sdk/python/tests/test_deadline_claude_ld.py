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
