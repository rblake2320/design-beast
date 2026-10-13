"""wait(timeout=...) is a total deadline, proved against real local HTTP servers (no transport mocks).

Each case runs the SDK call in a watchdog thread, so a client that ignores its deadline fails here instead of hanging
the suite. Successful terminal controls prove the bound does not come from refusing everything.
"""
import json
import socket
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


def test_deadline_reaps_a_proxy_connect_tunnel_that_drips_headers():
    """HTTPS through the caller's own requests.Session proxy: the CONNECT reply never ends, so the read is
    blocked before TLS or any response; the socket must still be shut down at the deadline. The target
    address is never contacted (the tunnel is never established)."""
    import requests

    drips = Drips()
    stop = threading.Event()

    class Proxy(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_CONNECT(self):
            try:
                dripping(drips, b"HTTP/1.1 200 Connection established\r\nX-Drip: ")(self, stop)
            except (ConnectionError, OSError):
                pass

    proxy = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    proxy.daemon_threads = True
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    session = requests.Session()
    session.trust_env = False
    session.proxies = {"https": f"http://127.0.0.1:{proxy.server_address[1]}"}
    try:
        client = BeastStudioClient("https://127.0.0.1:9", session=session, timeout=2)
        before = sdk_threads()
        box, elapsed, finished = bounded(lambda: client.wait("r1", timeout=0.3, poll_interval=0.05))
        assert finished and isinstance(box.get("error"), BeastStudioError), box
        assert "terminal phase within" in str(box["error"]), box["error"]
        assert elapsed < 0.3 + SLACK, elapsed
        assert_reaped(drips, before)  # also proves the caller's proxy setting was used
    finally:
        stop.set()
        proxy.shutdown()
        proxy.server_close()
        session.close()


def test_deadline_kills_stalled_resolver_children(monkeypatch, tmp_path):
    """getaddrinfo cannot be interrupted in-process, so lookups run in an owned child. Fault injection replaces only
    the child's code for reserved .invalid names: it records that it started, stalls, and would record an end if it
    survived. Three distinct names: every caller returns at its deadline and every child is killed (no end marker)."""
    import beast_studio_client.client as transport

    marks = str(tmp_path).replace("\\", "/")
    stall = ("import json, os, socket, sys, time; host = sys.argv[1]\n"
             "if host.endswith('.owned-deadline.invalid'):\n"
             f"    open('{marks}/start-' + str(os.getpid()), 'w').close(); time.sleep(2.0)\n"
             f"    open('{marks}/end-' + str(os.getpid()), 'w').close(); sys.exit(1)\n"
             "print(json.dumps(socket.getaddrinfo(host, int(sys.argv[2]), int(sys.argv[3]), socket.SOCK_STREAM)))")
    monkeypatch.setattr(transport, "_RESOLVER_CHILD", stall)
    before = sdk_threads()
    for i in range(3):
        client = BeastStudioClient(f"http://{i}.owned-deadline.invalid:9")
        client.session.trust_env = False
        # 1.5 s lets the child interpreter start (about 0.4 s here) and enter its stall before the deadline.
        box, elapsed, finished = bounded(lambda: client.wait("r1", timeout=1.5, poll_interval=0.05))
        assert finished and isinstance(box.get("error"), BeastStudioError), box
        assert "terminal phase within" in str(box["error"]), box["error"]
        assert elapsed < 1.5 + SLACK, elapsed
    time.sleep(2.5)  # a surviving child would have written its end marker by now
    started = sorted(p.name for p in tmp_path.glob("start-*"))
    ended = sorted(p.name for p in tmp_path.glob("end-*"))
    assert len(started) >= 3, f"fault was not injected: {started}"
    assert ended == [], f"resolver children survived the deadline: {ended}"
    assert sdk_threads() == before, sdk_threads()


def test_deadline_reaps_a_stalled_tls_handshake_through_a_proxy():
    """The CONNECT tunnel opens, the real TLS ClientHello arrives, then the handshake stalls. TLS wrapping detaches
    the original socket object, so the deadline must still reach the live connection. No certificate check is
    bypassed and the target is never contacted."""
    import requests

    hello = threading.Event()
    drips = Drips()
    stop = threading.Event()

    class Proxy(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_CONNECT(self):
            drips.begin()
            try:
                time.sleep(0.4)
                self.wfile.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
                self.wfile.flush()
                self.connection.settimeout(0.05)
                while not stop.is_set():
                    try:
                        if not self.connection.recv(4096):
                            break
                        hello.set()
                    except socket.timeout:
                        pass
            except OSError:
                pass
            finally:
                drips.end()

    proxy = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    proxy.daemon_threads = True
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    session = requests.Session()
    session.trust_env = False
    session.proxies = {"https": f"http://127.0.0.1:{proxy.server_address[1]}"}
    try:
        client = BeastStudioClient("https://127.0.0.1:9", session=session, timeout=5)
        before = sdk_threads()
        box, elapsed, finished = bounded(lambda: client.wait("r1", timeout=1.0, poll_interval=0.05))
        assert hello.is_set(), "fault was not injected: no TLS ClientHello reached the stalled tunnel"
        assert finished and isinstance(box.get("error"), BeastStudioError), box
        assert elapsed < 1.0 + 0.4, elapsed
        assert_reaped(drips, before)
    finally:
        stop.set()
        proxy.shutdown()
        proxy.server_close()
        session.close()


def test_short_deadline_never_cuts_a_concurrent_wait_on_the_same_client():
    """Two waits share one client over HTTP/1.1 keep-alive: a short one that expires, and a long one whose status
    answers after 0.7s. Each bounded wait owns its pool, so the short deadline cannot shut a connection the long
    wait reuses."""
    short_seen = threading.Event()
    peers = []

    class KeepAlive(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def do_GET(self):
            job = self.path.rsplit("/", 1)[-1]
            peers.append((job, self.client_address))
            if job == "long":
                time.sleep(0.7)
            body = json.dumps({"phase": "running" if job == "short" else "done"}).encode()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()
            except OSError:
                return
            if job == "short":
                short_seen.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), KeepAlive)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    client = BeastStudioClient(f"http://127.0.0.1:{server.server_address[1]}")
    client.session.trust_env = False
    try:
        for _ in range(5):
            short_seen.clear()
            results = {}

            def call(job, budget):
                try:
                    results[job] = client.wait(job, use_sse=False, timeout=budget, poll_interval=1)
                except BeastStudioError as error:
                    results[job] = error

            short = threading.Thread(target=call, args=("short", 0.3))
            short.start()
            assert short_seen.wait(2)
            time.sleep(0.03)
            long = threading.Thread(target=call, args=("long", 2.0))
            long.start()
            short.join(5)
            long.join(5)
            assert isinstance(results.get("short"), BeastStudioError), results
            assert results.get("long") == {"phase": "done"}, results
    finally:
        server.shutdown()
        server.server_close()


def test_bounded_lookup_keeps_multi_address_fallback(studio):
    """Positive control: 'localhost' may resolve to ::1 first; the bounded connect must fall back to 127.0.0.1."""
    routes, url = studio
    routes["/api/events/"] = broken_sse
    routes["/api/run/"] = json_reply({"phase": "done"})
    local = url.replace("127.0.0.1", "localhost")
    # Windows takes about 2 s to refuse ::1; this control proves the fallback works, not its speed.
    box, elapsed, finished = bounded(lambda: BeastStudioClient(local).wait("r1", timeout=10, poll_interval=0.05))
    assert finished and box.get("value") == {"phase": "done"}, box


# ---- TLS controls on the reaping path ----
# A loopback HTTPS server with a self-signed test certificate (tests/fixtures, SAN localhost/127.0.0.1/::1,
# test use only). The caller trusts it through its own requests.Session verify setting; without that the
# default trust store must refuse it.

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def tls_studio():
    import ssl

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path.startswith("/api/events/"):
                self.send_error(503)
                return
            json_reply({"phase": "done"})(self, None)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(FIXTURES / "loopback-cert.pem", FIXTURES / "loopback-key.pem")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_healthy_tls_through_the_reaping_path_returns_terminal(tls_studio, host):
    """Positive control: verified TLS (caller's own trust setting) by address and by hostname with fallback."""
    import requests

    session = requests.Session()
    session.trust_env = False
    session.verify = str(FIXTURES / "loopback-cert.pem")
    client = BeastStudioClient(f"https://{host}:{tls_studio}", session=session)
    before = sdk_threads()
    # Windows takes about 2 s to refuse ::1 before localhost falls back to 127.0.0.1.
    box, elapsed, finished = bounded(lambda: client.wait("r1", timeout=10, poll_interval=0.05))
    assert finished and box.get("value") == {"phase": "done"}, box
    assert sdk_threads() == before, sdk_threads()


def test_untrusted_certificate_is_refused_not_waited_out(tls_studio):
    """Negative control: the reaping path keeps certificate verification; an untrusted server certificate fails
    with a typed error well before the deadline instead of being accepted or timing out."""
    import requests

    session = requests.Session()
    session.trust_env = False
    client = BeastStudioClient(f"https://127.0.0.1:{tls_studio}", session=session)
    box, elapsed, finished = bounded(lambda: client.wait("r1", timeout=5, poll_interval=0.05))
    assert finished and isinstance(box.get("error"), BeastStudioError), box
    assert "CERTIFICATE_VERIFY_FAILED" in str(box["error"]), box["error"]
    assert "terminal phase within" not in str(box["error"]), box["error"]
    assert elapsed < 5, elapsed


# ---- caller transport policy ----

def test_custom_transport_adapter_is_refused_before_anything_is_sent(studio):
    """A caller policy adapter is never silently replaced: wait(timeout=...) refuses with a typed error and the
    server receives nothing, matching what the caller's own adapter does for status()."""
    import requests

    routes, url = studio
    received = []

    def record(handler, stop):
        received.append(handler.path)
        json_reply({"phase": "done"})(handler, stop)

    routes["/api/"] = record
    denied = []

    class DenyAdapter(requests.adapters.HTTPAdapter):
        def send(self, request, *args, **kwargs):
            denied.append(request.url)
            raise requests.RequestException("caller transport policy: no request allowed")

    session = requests.Session()
    session.trust_env = False
    session.mount("http://", DenyAdapter())
    client = BeastStudioClient(url, session=session)
    with pytest.raises(BeastStudioError):
        client.status("r1")  # the caller's policy, as the control
    before = sdk_threads()
    for use_sse in (True, False):
        box, elapsed, finished = bounded(lambda: client.wait("r1", timeout=2, use_sse=use_sse))
        assert finished and isinstance(box.get("error"), BeastStudioError), box
        assert "DenyAdapter" in str(box["error"]) and "nothing was sent" in str(box["error"]), box["error"]
    assert received == [], received
    assert len(denied) == 1, denied  # only the status() control reached the caller's adapter
    assert sdk_threads() == before


def test_non_requests_session_is_refused_before_anything_is_sent(studio):
    routes, url = studio
    received = []
    routes["/api/"] = lambda handler, stop: received.append(handler.path)

    class DuckSession:
        headers = {}

        def get(self, *args, **kwargs):
            raise AssertionError("the SDK must not send through a session it cannot bound")

        request = get

    box, elapsed, finished = bounded(lambda: BeastStudioClient(url, session=DuckSession()).wait("r1", timeout=2))
    assert finished and isinstance(box.get("error"), BeastStudioError), box
    assert "requests.Session" in str(box["error"]), box["error"]
    assert received == []


def test_standard_adapter_mounts_keep_their_prefix_and_retry_settings(studio):
    """Positive control: a standard HTTPAdapter mounted by the caller at a specific prefix with retries is
    reproduced on the bounded path (the first status attempt is refused by the server, the retry succeeds)."""
    import requests
    from urllib3.util.retry import Retry

    routes, url = studio
    attempts = []

    def flaky(handler, stop):
        attempts.append(handler.path)
        if len(attempts) == 1:
            handler.send_response(503)
            handler.send_header("Content-Length", "0")
            handler.end_headers()
            return
        json_reply({"phase": "done"})(handler, stop)

    routes["/api/events/"] = broken_sse
    routes["/api/run/"] = flaky
    session = requests.Session()
    session.trust_env = False
    session.mount(url + "/api/run/", requests.adapters.HTTPAdapter(
        max_retries=Retry(total=2, status_forcelist=[503], backoff_factor=0, allowed_methods=["GET"])))
    client = BeastStudioClient(url, session=session)
    box, elapsed, finished = bounded(lambda: client.wait("r1", timeout=5, poll_interval=0.05))
    assert finished and box.get("value") == {"phase": "done"}, box
    assert len(attempts) == 2, attempts


# ---- caller retry policy under a deadline ----
# urllib3 sleeps between retries with time.sleep, which no socket shutdown can interrupt; the bounded path
# must keep the caller's Retry policy but never let a Retry-After or backoff delay outlast the deadline.

def retrying_session(**retry):
    import requests
    from urllib3.util.retry import Retry

    session = requests.Session()
    session.trust_env = False
    session.mount("http://", requests.adapters.HTTPAdapter(max_retries=Retry(
        status_forcelist=[503], allowed_methods=["GET"], **retry)))
    return session


def unavailable(requests_seen, retry_after=None, recover_after=None):
    def behaviour(handler, stop):
        requests_seen.append(handler.path)
        if recover_after is not None and len(requests_seen) > recover_after:
            json_reply({"phase": "done"})(handler, stop)
            return
        handler.send_response(503)
        if retry_after is not None:
            handler.send_header("Retry-After", str(retry_after))
        handler.send_header("Content-Length", "0")
        handler.end_headers()
    return behaviour


@pytest.mark.parametrize("use_sse,delay", [
    (True, "retry-after"),
    (False, "retry-after"),
    (True, "backoff"),
    (False, "backoff"),
], ids=["sse-retry-after", "polling-retry-after", "sse-backoff", "polling-backoff"])
def test_retry_delays_never_outlast_the_wait_deadline(studio, use_sse, delay):
    routes, url = studio
    seen = []
    retry_after = 2 if delay == "retry-after" else None
    routes["/api/events/"] = unavailable(seen, retry_after)
    routes["/api/run/"] = unavailable(seen, retry_after)
    session = retrying_session(total=2, backoff_factor=1 if delay == "backoff" else 0)
    client = BeastStudioClient(url, session=session)
    box, elapsed, finished = bounded(lambda: client.wait("r1", timeout=0.3, use_sse=use_sse, poll_interval=0.05))
    assert seen, "fault was not injected: the server saw no request"
    assert finished and isinstance(box.get("error"), BeastStudioError), box
    assert "terminal phase within" in str(box["error"]), box["error"]
    assert elapsed < 0.3 + 0.3, elapsed


@pytest.mark.parametrize("use_sse", [True, False], ids=["sse", "polling"])
def test_retry_delays_inside_the_budget_still_retry_and_succeed(studio, use_sse):
    """Positive control: a Retry-After of 1 s and a backoff that fit the budget are honoured, and the retried
    request returns the terminal status. urllib3's first backoff is 0, so the backoff case fails twice: its second
    retry sleeps factor 0.2 * 2 = 0.4 s."""
    routes, url = studio
    for retry, backoff in ((1, 0), (None, 0.2)):
        seen = []
        failures = 1 if retry else 2
        routes["/api/events/"] = broken_sse
        routes["/api/run/"] = unavailable(seen, retry_after=retry, recover_after=failures)
        client = BeastStudioClient(url, session=retrying_session(total=2, backoff_factor=backoff))
        box, elapsed, finished = bounded(lambda: client.wait("r1", timeout=5, use_sse=use_sse, poll_interval=0.05))
        assert finished and box.get("value") == {"phase": "done"}, box
        assert len(seen) == failures + 1, seen
        if retry:
            assert elapsed >= 1.0, elapsed  # the server's Retry-After was respected, not skipped
        else:
            assert elapsed >= 0.35, elapsed  # the 0.4 s backoff was actually slept


def test_custom_retry_policy_class_is_refused_before_anything_is_sent(studio):
    import requests
    from urllib3.util.retry import Retry

    class OwnRetry(Retry):
        pass

    routes, url = studio
    seen = []
    routes["/api/"] = lambda handler, stop: seen.append(handler.path)
    session = requests.Session()
    session.trust_env = False
    session.mount("http://", requests.adapters.HTTPAdapter(max_retries=OwnRetry(total=1)))
    box, elapsed, finished = bounded(lambda: BeastStudioClient(url, session=session).wait("r1", timeout=2))
    assert finished and isinstance(box.get("error"), BeastStudioError), box
    assert "OwnRetry" in str(box["error"]) and "nothing was sent" in str(box["error"]), box["error"]
    assert seen == []


# ---- caller callbacks the deadline cannot interrupt ----
# A custom auth callable runs before any HTTP and a response hook after it; either can block for as long as it
# likes in the caller's thread. The bounded path refuses them before calling them or sending anything, and keeps
# ordinary basic auth.

def sleeping_callbacks(kind, entered):
    import requests

    session = requests.Session()
    session.trust_env = False
    if kind == "auth":
        class SlowAuth(requests.auth.AuthBase):
            def __call__(self, request):
                entered.append("auth")
                time.sleep(1)
                return request
        session.auth = SlowAuth()
    else:
        def slow_hook(response, *args, **kwargs):
            entered.append("hook")
            time.sleep(1)
        session.hooks["response"].append(slow_hook)
    return session


@pytest.mark.parametrize("kind,use_sse", [
    ("auth", True),
    ("auth", False),
    ("hook", True),
    ("hook", False),
], ids=["sse-auth", "polling-auth", "sse-response-hook", "polling-response-hook"])
def test_blocking_session_callbacks_are_refused_before_they_run(studio, kind, use_sse):
    routes, url = studio
    received = []

    def record(handler, stop):
        received.append(handler.path)
        json_reply({"phase": "done"})(handler, stop)

    routes["/api/"] = record
    entered = []
    client = BeastStudioClient(url, session=sleeping_callbacks(kind, entered))
    box, elapsed, finished = bounded(lambda: client.wait("r1", timeout=0.2, use_sse=use_sse, poll_interval=0.05))
    assert finished and isinstance(box.get("error"), BeastStudioError), box
    assert "nothing was sent" in str(box["error"]), box["error"]
    assert elapsed < 0.2 + 0.3, elapsed
    assert entered == [] and received == [], (entered, received)


@pytest.mark.parametrize("auth", ["tuple", "HTTPBasicAuth"])
def test_ordinary_basic_auth_still_reaches_the_server(studio, auth):
    """Positive control: a (user, password) tuple and requests' HTTPBasicAuth pass through the bounded path."""
    import base64

    import requests

    routes, url = studio
    seen = []

    def status(handler, stop):
        seen.append(handler.headers.get("Authorization"))
        json_reply({"phase": "done"})(handler, stop)

    routes["/api/events/"] = broken_sse
    routes["/api/run/"] = status
    session = requests.Session()
    session.trust_env = False
    session.auth = ("owner", "test-only") if auth == "tuple" else requests.auth.HTTPBasicAuth("owner", "test-only")
    box, elapsed, finished = bounded(lambda: BeastStudioClient(url, session=session).wait("r1", timeout=5))
    assert finished and box.get("value") == {"phase": "done"}, box
    assert seen and seen[-1] == "Basic " + base64.b64encode(b"owner:test-only").decode(), seen


@pytest.mark.parametrize("custom", ["session-subclass", "cookie-jar"])
def test_custom_session_classes_are_refused_before_anything_is_sent(studio, custom):
    """A Session subclass may override request/send with its own policy, and a custom cookie jar runs caller code
    per request; the bounded path cannot carry either faithfully, so it refuses them without contact."""
    import requests

    routes, url = studio
    received = []
    routes["/api/"] = lambda handler, stop: received.append(handler.path)
    denied = []

    class DenySession(requests.Session):
        def request(self, *args, **kwargs):
            denied.append(args)
            raise requests.RequestException("caller transport policy refuses requests")

    class OwnJar(requests.cookies.RequestsCookieJar):
        pass

    if custom == "session-subclass":
        session = DenySession()
    else:
        session = requests.Session()
        session.cookies = OwnJar()
    session.trust_env = False
    box, elapsed, finished = bounded(lambda: BeastStudioClient(url, session=session).wait("r1", timeout=2))
    assert finished and isinstance(box.get("error"), BeastStudioError), box
    assert "nothing was sent" in str(box["error"]), box["error"]
    assert received == [] and denied == [], (received, denied)


# ---- the whole class of caller code the private bounded session could bypass ----

def overridden_session(case, entered):
    """A plain requests.Session carrying one caller customization the bounded copy could not carry."""
    import http.cookiejar
    import ssl

    import requests
    from urllib3.util.retry import Retry

    session = requests.Session()
    session.trust_env = False

    def deny(*args, **kwargs):
        entered.append(case)
        raise requests.RequestException("caller policy refuses")

    if case == "session-instance-request":
        session.request = deny
    elif case == "session-instance-send":
        session.send = deny
    elif case == "adapter-instance-send":
        session.adapters["http://"].send = deny
    elif case == "poolmanager-instance-urlopen":
        session.adapters["http://"].poolmanager.urlopen = deny
    elif case == "poolmanager-tls-context":
        adapter = requests.adapters.HTTPAdapter()
        adapter.init_poolmanager(10, 10, ssl_context=ssl.create_default_context())
        session.mount("http://", adapter)
    elif case == "retry-instance-sleep":
        retry = Retry(total=2, status_forcelist=[503], allowed_methods=["GET"])
        retry.sleep = deny
        session.mount("http://", requests.adapters.HTTPAdapter(max_retries=retry))
    elif case == "cookie-policy-class":
        class OwnPolicy(http.cookiejar.DefaultCookiePolicy):
            def return_ok(self, cookie, request):
                entered.append(case)
                return super().return_ok(cookie, request)
        session.cookies.set_policy(OwnPolicy())
    elif case == "cookie-policy-instance":
        session.cookies._policy.return_ok = deny
    elif case == "auth-instance-call":
        auth = requests.auth.HTTPBasicAuth("owner", "test-only")
        auth.__call__ = deny  # dunder lookup ignores this today; refused so no future path can bypass it
        session.auth = auth
    return session


@pytest.mark.parametrize("case", [
    "session-instance-request", "session-instance-send", "adapter-instance-send", "poolmanager-instance-urlopen",
    "poolmanager-tls-context", "retry-instance-sleep", "cookie-policy-class", "cookie-policy-instance",
    "auth-instance-call",
])
def test_caller_customizations_the_bounded_copy_cannot_carry_are_refused(studio, case):
    routes, url = studio
    received = []

    def record(handler, stop):
        received.append(handler.path)
        json_reply({"phase": "done"})(handler, stop)

    routes["/api/"] = record
    entered = []
    client = BeastStudioClient(url, session=overridden_session(case, entered))
    box, elapsed, finished = bounded(lambda: client.wait("r1", timeout=2))
    assert finished and isinstance(box.get("error"), BeastStudioError), box
    assert "nothing was sent" in str(box["error"]), box["error"]
    assert received == [] and entered == [], (received, entered)


def test_ordinary_session_state_on_a_used_session_still_reaches_the_server(studio):
    """Positive control: headers, tuple auth and cookies arrive, after the same session served a normal call."""
    import requests

    routes, url = studio
    seen = []

    def status(handler, stop):
        seen.append((handler.headers.get("X-Studio-Client"), handler.headers.get("Authorization"),
                     handler.headers.get("Cookie")))
        json_reply({"phase": "done"})(handler, stop)

    routes["/api/events/"] = broken_sse
    routes["/api/run/"] = status
    session = requests.Session()
    session.trust_env = False
    session.headers["X-Studio-Client"] = "owned-test"
    session.auth = ("owner", "test-only")
    session.cookies.set("studio", "owned")
    client = BeastStudioClient(url, session=session)
    assert client.status("r1") == {"phase": "done"}  # pools and state already populated
    box, elapsed, finished = bounded(lambda: client.wait("r1", timeout=5))
    assert finished and box.get("value") == {"phase": "done"}, box
    header, auth, cookie = seen[-1]
    assert header == "owned-test" and auth and auth.startswith("Basic ") and cookie == "studio=owned", seen


# ---- the policy check itself must never run caller code ----
# Each case hides a slow caller method in a container or table the bounded copy would read; the check has to
# establish exact types before touching any of them, so the refusal arrives inside the budget with nothing entered.

def container_session(case, entered):
    import collections

    import requests
    from requests.structures import CaseInsensitiveDict
    from urllib3.util.retry import Retry

    def slow(name):
        def method(self, *args, **kwargs):
            entered.append(name)
            time.sleep(1)
            return getattr(super(type(self), self), name)(*args, **kwargs)
        return method

    session = requests.Session()
    session.trust_env = False
    if case == "hooks-dict-subclass":
        session.hooks = type("SlowHooks", (dict,), {"items": slow("items")})(session.hooks)
    elif case == "headers-instance-items":
        headers = CaseInsensitiveDict(session.headers)
        headers.items = lambda: (entered.append("items"), time.sleep(1), [])[2]
        session.headers = headers
    elif case == "headers-dict-subclass":
        session.headers = type("SlowHeaders", (dict,), {"items": slow("items")})({"Accept": "*/*"})
    elif case == "header-value-str-subclass":
        session.headers["X-Owned"] = type("SlowStr", (str,), {"encode": slow("encode")})("value")
    elif case == "adapters-dict-subclass":
        session.adapters = type("SlowAdapters", (collections.OrderedDict,), {"items": slow("items")})(session.adapters)
    elif case == "proxy-manager-map-subclass":
        adapter = session.adapters["http://"]
        adapter.proxy_manager = type("SlowProxies", (dict,), {"items": slow("items")})()
    elif case == "poolmanager-key-function":
        manager = session.adapters["http://"].poolmanager
        default = manager.key_fn_by_scheme["http"]
        manager.key_fn_by_scheme = dict(manager.key_fn_by_scheme,
                                        http=lambda *a, **k: (entered.append("key_fn"), default(*a, **k))[1])
    elif case == "poolmanager-pool-classes":
        manager = session.adapters["http://"].poolmanager
        manager.pool_classes_by_scheme = type("SlowClasses", (dict,), {"items": slow("items")})(
            manager.pool_classes_by_scheme)
    elif case == "auth-tuple-subclass":
        session.auth = type("SlowAuth", (tuple,), {"__len__": slow("__len__")})(("owner", "test-only"))
    elif case == "auth-part-str-subclass":
        session.auth = (type("SlowUser", (str,), {"encode": slow("encode")})("owner"), "test-only")
    elif case == "retry-forcelist-container":
        forcelist = type("SlowSet", (set,), {"__contains__": slow("__contains__")})({503})
        session.mount("http://", requests.adapters.HTTPAdapter(max_retries=Retry(
            total=1, status_forcelist=forcelist, allowed_methods=["GET"])))
    elif case == "cookie-store-subclass":
        session.cookies._cookies = type("SlowStore", (dict,), {"values": slow("values")})()
    return session


@pytest.mark.parametrize("case", [
    "hooks-dict-subclass", "headers-instance-items", "headers-dict-subclass", "header-value-str-subclass",
    "adapters-dict-subclass", "proxy-manager-map-subclass", "poolmanager-key-function", "poolmanager-pool-classes",
    "auth-tuple-subclass", "auth-part-str-subclass", "retry-forcelist-container", "cookie-store-subclass",
])
def test_policy_check_refuses_custom_containers_without_calling_them(studio, case):
    routes, url = studio
    received = []

    def record(handler, stop):
        received.append(handler.path)
        json_reply({"phase": "done"})(handler, stop)

    routes["/api/"] = record
    for use_sse in (True, False):
        entered = []
        client = BeastStudioClient(url, session=container_session(case, entered))
        box, elapsed, finished = bounded(lambda: client.wait("r1", timeout=0.2, use_sse=use_sse, poll_interval=0.05))
        assert finished and isinstance(box.get("error"), BeastStudioError), box
        assert "nothing was sent" in str(box["error"]), box["error"]
        assert elapsed < 0.2 + 0.3, (use_sse, elapsed)
        assert entered == [], (use_sse, entered)
    assert received == [], received
