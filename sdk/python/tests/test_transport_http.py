"""Real loopback HTTP tests: deadlines, malformed payloads, and cleanup."""
import json
import sys
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from beast_studio_client import BeastStudioClient, BeastStudioError  # noqa: E402


@contextmanager
def endpoint(mode):
    closed = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def do_GET(self):
            if "/events/" in self.path:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                self.wfile.flush()
                if mode == "multiline":
                    self.wfile.write(b'data: {"phase":\r\ndata: "done"}\r\n\r\n')
                    self.wfile.flush()
                elif mode == "heartbeat":
                    time.sleep(0.05)
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                self.connection.settimeout(1)
                try:
                    if self.connection.recv(1) == b"":
                        closed.set()
                except OSError:
                    pass
                self.close_connection = True
                return
            if mode == "drip":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", "1000")
                self.end_headers()
                try:
                    for _ in range(100):
                        self.wfile.write(b" ")
                        self.wfile.flush()
                        time.sleep(0.02)
                except OSError:
                    closed.set()
                self.close_connection = True
                return
            if mode == "healthy_delay":
                time.sleep(0.15)
            body = json.dumps(None if mode == "null" else {"phase": "running"}).encode()
            if mode == "healthy_delay":
                body = b'{"phase":"done"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = BeastStudioClient(f"http://127.0.0.1:{server.server_port}")
    try:
        yield client, closed
    finally:
        client.session.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("mode", ["silent", "heartbeat", "drip"])
def test_finite_wait_bounds_real_transport_and_closes_connection(mode):
    with endpoint(mode) as (client, closed):
        for _ in range(2):
            closed.clear()
            started = time.monotonic()
            with pytest.raises(BeastStudioError):
                client.wait("x", timeout=0.2, use_sse=mode != "drip")
            assert time.monotonic() - started < 0.5
            assert closed.wait(0.6), "server did not observe transport cleanup"
        deadline = time.monotonic() + 0.5
        while any(t.name == "beast-bounded-wait" for t in threading.enumerate()):
            assert time.monotonic() < deadline, "wait worker leaked"
            time.sleep(0.01)


def test_multiline_crlf_sse_is_parsed_over_real_http():
    with endpoint("multiline") as (client, closed):
        assert client.wait("x", timeout=0.5) == {"phase": "done"}
        assert closed.wait(0.5)


@pytest.mark.parametrize("timeout", [None, 0.5])
def test_null_status_is_a_classified_error(timeout):
    with endpoint("null") as (client, _):
        with pytest.raises(BeastStudioError, match="invalid status"):
            client.wait("x", timeout=timeout, use_sse=False)


def test_zero_deadline_makes_no_request():
    with endpoint("silent") as (client, _):
        with pytest.raises(BeastStudioError, match="within 0s"):
            client.wait("x", timeout=0)


def test_status_delayed_within_budget_still_succeeds():
    with endpoint("healthy_delay") as (client, _):
        assert client.wait("x", timeout=0.8, use_sse=False) == {"phase": "done"}
