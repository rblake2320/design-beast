"""Lightweight Python client for Beast Studio (http://127.0.0.1:8787).

One dependency: requests. See ../../../openapi.json for the generated
contract and ../../../AGENT_ACCESS.md for operational rules this client
does not itself enforce (backend-sharing etiquette, VRAM contention).

    from beast_studio_client import BeastStudioClient
    c = BeastStudioClient()
    expanded = c.expand("a cozy reading nook")
    job = c.run(brief="a cozy reading nook", prompt=expanded["prompt"],
                variations=expanded["variations"])
    final = c.wait(job["id"])
"""
from __future__ import annotations

import collections
import copy
import http.cookiejar
import ipaddress
import json
import math
import os
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import quote

import requests
import urllib3
import urllib3._collections
import urllib3.util.url
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import ConnectTimeoutError, NewConnectionError
from urllib3.poolmanager import PoolManager, ProxyManager
from urllib3.util.connection import allowed_gai_family
from urllib3.util.retry import Retry

from .models import AnimateDuration, AnimateQuality, AspectRatio, BackendAction, ImageModel

DEFAULT_BASE_URL = "http://127.0.0.1:8787"
TERMINAL_PHASES = ("done", "failed", "cancelled")
NIM_BACKENDS = frozenset(
    ("nim-flux", "nim-kontext", "nim-flux2", "nim-trellis", "nim-wan"))
BACKEND_START_TIMEOUTS = {"nim-wan": 2130.0}
DEFAULT_NIM_START_TIMEOUT = 510.0
NIM_STOP_TIMEOUT = 150.0


def _bounded_lines(response, deadline):
    """Check the wall deadline even when a peer drips an unfinished line."""
    line = bytearray()
    for chunk in response.iter_content(chunk_size=1):
        if deadline is not None and time.monotonic() >= deadline:
            raise BeastStudioError("SSE stream exceeded its deadline")
        if not chunk:
            continue
        line.extend(chunk)
        if len(line) > 1_048_576:
            raise BeastStudioError("SSE line exceeds 1MiB")
        if chunk == b"\n":
            yield line.decode("utf-8").rstrip("\r\n")
            line.clear()


class _DeadlineScope:
    """Everything one bounded wait() can block on. At the deadline every
    connection's socket is shut down and the resolver child is killed, so
    nothing the call started outlives it. All connections come from the wait's
    private pool, so none belongs to another caller."""

    def __init__(self, timeout):
        self._lock = threading.Lock()
        self._sockets = []
        self._child = None
        self.addresses = {}
        self.expired = False
        self.deadline = time.monotonic() + timeout

    def remaining(self):
        left = self.deadline - time.monotonic()
        if self.expired or left <= 0:
            raise socket.timeout("wait deadline reached")
        return left

    def add(self, connection, sock):
        entry = (connection, sock, sock.fileno())
        with self._lock:
            if not self.expired:
                self._sockets.append(entry)
                return
        _reap(entry)

    def discard(self, sock):
        """Forget a socket the caller closed itself, so its handle is never touched again."""
        with self._lock:
            self._sockets = [entry for entry in self._sockets if entry[1] is not sock]

    def attach_child(self, child):
        with self._lock:
            self._child = child
            if not self.expired:
                return
        child.kill()

    def expire(self):
        with self._lock:
            self.expired = True
            sockets, child = list(self._sockets), self._child
        for entry in sockets:
            _reap(entry)
        if child is not None:
            child.kill()

    def close(self):
        with self._lock:
            self._sockets = []


def _reap(entry):
    """Shut down the live socket of a registered connection. TLS wrapping
    detaches the raw socket object and hands its handle to an SSLSocket; while
    that connect() is still in progress the handle is shut down directly,
    through a non-owning wrapper that is detached again, never closed."""
    connection, raw, handle = entry
    target = connection.sock if connection.sock is not None else raw
    try:
        if target.fileno() != -1:
            target.shutdown(socket.SHUT_RDWR)
        elif getattr(connection, "_beast_connecting", False):
            borrowed = socket.socket(fileno=handle)
            try:
                borrowed.shutdown(socket.SHUT_RDWR)
            finally:
                borrowed.detach()
    except OSError:
        pass  # already closed by the peer or by urllib3


_ACTIVE_SCOPE = threading.local()

# getaddrinfo cannot be interrupted inside this process, so a bounded wait
# resolves names in an owned child it can kill and reap at the deadline.
_RESOLVER_CHILD = ("import json, socket, sys; "
                   "print(json.dumps(socket.getaddrinfo(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), "
                   "socket.SOCK_STREAM)))")
_RESOLVER_ENV = ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "HOSTALIASES", "RES_OPTIONS", "LOCALDOMAIN")


def _resolve(host, port, scope):
    family = allowed_gai_family()
    try:
        ipaddress.ip_address(host)
        return socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)  # literal: no lookup
    except ValueError:
        pass
    key = (host, port, family)
    if key in scope.addresses:
        return scope.addresses[key]
    child = subprocess.Popen(
        [sys.executable, "-I", "-c", _RESOLVER_CHILD, host, str(port), str(int(family))],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env={k: v for k, v in os.environ.items() if k.upper() in _RESOLVER_ENV},
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    scope.attach_child(child)
    try:
        out, err = child.communicate(timeout=scope.remaining())
    except (subprocess.TimeoutExpired, socket.timeout):
        child.kill()
        child.communicate()
        raise socket.timeout(f"resolving {host} exceeded the wait deadline")
    if scope.expired:
        raise socket.timeout(f"resolving {host} exceeded the wait deadline")
    if child.returncode:
        raise socket.gaierror(f"could not resolve {host}: {err.strip().splitlines()[-1:] or child.returncode}")
    addresses = [(family_, kind, proto, name, tuple(address))
                 for family_, kind, proto, name, address in json.loads(out)]
    scope.addresses[key] = addresses
    return addresses


def _bounded_new_conn(connection, scope):
    """urllib3's create_connection with the lookup bounded and every socket
    registered with the deadline scope before connect() can block."""
    host = connection._dns_host
    host = host.strip("[]") if host.startswith("[") else host
    try:
        addresses = _resolve(host, connection.port, scope)
        error = OSError("getaddrinfo returns an empty list")
        for entry in list(addresses):
            family, kind, proto, _, address = entry
            sock = socket.socket(family, kind, proto)
            scope.add(connection, sock)
            try:
                for option in connection.socket_options or ():
                    sock.setsockopt(*option)
                limit = connection.timeout if isinstance(connection.timeout, (int, float)) else None
                sock.settimeout(scope.remaining() if limit is None else min(limit, scope.remaining()))
                if connection.source_address:
                    sock.bind(connection.source_address)
                sock.connect(address)
                if addresses and addresses[0] is not entry:  # later connections of this wait try it first
                    addresses.remove(entry)
                    addresses.insert(0, entry)
                return sock
            except OSError as attempt:
                error = attempt
                scope.discard(sock)
                sock.close()
        raise error
    except socket.timeout as e:
        raise ConnectTimeoutError(connection, f"Connection to {connection.host} timed out: {e}") from e
    except OSError as e:
        raise NewConnectionError(connection, f"Failed to establish a new connection: {e}") from e


def _track(connection):
    scope = getattr(_ACTIVE_SCOPE, "scope", None)
    if scope is not None and connection.sock is not None:
        scope.add(connection, connection.sock)


class _TrackedHTTPConnection(HTTPConnection):
    # Inside a deadline scope a new socket registers before connect(), so the
    # connect, any proxy CONNECT, TLS handshake and response reads all end at
    # the deadline; a pooled socket registers again when reused.
    def _new_conn(self):
        scope = getattr(_ACTIVE_SCOPE, "scope", None)
        return super()._new_conn() if scope is None else _bounded_new_conn(self, scope)

    def connect(self):
        self._beast_connecting = True
        try:
            return super().connect()
        finally:
            self._beast_connecting = False

    def getresponse(self, *args, **kwargs):
        _track(self)
        return super().getresponse(*args, **kwargs)


class _TrackedHTTPSConnection(HTTPSConnection):
    def _new_conn(self):
        scope = getattr(_ACTIVE_SCOPE, "scope", None)
        return super()._new_conn() if scope is None else _bounded_new_conn(self, scope)

    def connect(self):
        self._beast_connecting = True
        try:
            return super().connect()
        finally:
            self._beast_connecting = False

    def getresponse(self, *args, **kwargs):
        _track(self)
        return super().getresponse(*args, **kwargs)


class _TrackedHTTPPool(HTTPConnectionPool):
    ConnectionCls = _TrackedHTTPConnection


class _TrackedHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = _TrackedHTTPSConnection


_TRACKED_POOLS = {"http": _TrackedHTTPPool, "https": _TrackedHTTPSPool}


class _DeadlineRetry(Retry):
    """The caller's urllib3 retry policy, unchanged, except that no delay may
    outlast the wait deadline. A delay that fits is slept as usual; one that
    would cross the deadline expires the wait at once instead of sleeping
    (Retry.new() keeps this class across attempts)."""

    def sleep(self, response=None):
        delay = 0.0
        if self.respect_retry_after_header and response:
            delay = self.get_retry_after(response) or 0.0
        if not delay:
            delay = max(0.0, self.get_backoff_time())
        scope = getattr(_ACTIVE_SCOPE, "scope", None)
        if scope is None:
            return super().sleep(response)
        if delay >= scope.remaining():  # raises once the deadline has passed
            scope.expire()
            raise socket.timeout(f"retry delay {delay:.3f}s exceeds the wait deadline")
        if delay:
            time.sleep(delay)


_SESSION_STATE = frozenset({"adapters", "auth", "cert", "cookies", "headers", "hooks", "max_redirects",
                            "params", "proxies", "stream", "trust_env", "verify"})


def _shadowed(obj, cls):
    """Instance attributes that replace a method of cls: caller code the bounded copy would drop or bypass.
    Only call this once type(obj) is cls, so vars() is the plain instance dict."""
    names = list(vars(obj))
    if any(type(name) is not str for name in names):
        return ["<non-string attribute>"]
    return sorted(name for name in names if callable(getattr(cls, name, None)))


_SCALARS = (type(None), bool, int, float, str, bytes)
_COLLECTIONS = (tuple, list, set, frozenset)


def _plain(value, depth=0):
    """True if value is built only from exact builtin scalar and collection types, checked by type()
    before anything is iterated, so inspecting it can never run caller code."""
    kind = type(value)
    if kind in _SCALARS:
        return True
    if depth < 3 and kind in _COLLECTIONS:
        return all(_plain(item, depth + 1) for item in value)
    if depth < 3 and kind is dict:
        return all(_plain(key, depth + 1) and _plain(item, depth + 1) for key, item in value.items())
    return False


_PROXY_POOL_KEYS = frozenset({"_proxy", "_proxy_headers", "_proxy_config"})  # set by urllib3 from the proxy URL
_PROXY_STATE = frozenset({"proxy", "proxy_headers", "proxy_ssl_context", "proxy_config"})


def _same_table(table, default):
    """An exact dict of str keys whose values are the very objects of the stock table (no caller functions)."""
    return (type(table) is dict and all(type(key) is str for key in table) and set(table) == set(default)
            and all(table[key] is default[key] for key in table))


def _pool_problem(manager, reference, cls, label):
    """A pool manager the private copy rebuilds must hold exactly a stock manager's state: same attribute set,
    equal plain settings, and the stock pool-class and pool-key function tables by identity. Its live pools are
    not reused and not inspected; urllib3's own proxy metadata is checked by type only."""
    if type(manager) is not cls or _shadowed(manager, cls):
        return f"the custom {label} {type(manager).__name__}"
    state = vars(manager)
    default = vars(reference.poolmanager)
    allowed = _PROXY_STATE if cls is ProxyManager else frozenset()
    if any(type(name) is not str for name in state) or set(state) - allowed != set(default):
        return f"customized {label} attributes"
    if type(state["pools"]) is not urllib3._collections.RecentlyUsedContainer:
        return f"a custom {label} pool container"
    if not _same_table(state["pool_classes_by_scheme"], default["pool_classes_by_scheme"]):
        return f"customized {label} pool classes"
    if not _same_table(state["key_fn_by_scheme"], default["key_fn_by_scheme"]):
        return f"customized {label} pool-key functions"
    if not (_plain(state["headers"]) and state["headers"] == default["headers"]):
        return f"customized {label} headers"
    kw = state["connection_pool_kw"]
    if type(kw) is not dict or not all(type(key) is str for key in kw):
        return f"customized {label} settings"
    own = {key: value for key, value in kw.items() if not (cls is ProxyManager and key in _PROXY_POOL_KEYS)}
    if not (_plain(own) and own == default["connection_pool_kw"]):
        return f"customized {label} settings {sorted(own)}"
    if cls is ProxyManager and (state["proxy_ssl_context"] is not None or not _plain(state["proxy_headers"])
                                or type(state["proxy"]) is not urllib3.util.url.Url
                                or type(state["proxy_config"]) is not urllib3.poolmanager.ProxyConfig):
        return f"customized {label} proxy settings"
    return None


def _caller_policy_problem(session):
    """Why the bounded path cannot carry this session faithfully, or None.

    Every object the private session rebuilds or reuses must be the exact standard type with no per-instance
    method overrides and carry no configuration a fresh standard object would lose. Each value's exact type is
    established with type() before any of its methods are called, so this check itself never runs caller code."""
    if type(session) is not requests.Session:
        return f"the Session subclass {type(session).__name__}"
    state = vars(session)
    if any(type(name) is not str for name in state):
        return "non-string Session attributes"
    extra = sorted(name for name in state if name not in _SESSION_STATE)
    if extra:
        return f"per-instance Session attributes {extra}"
    for name in ("stream", "verify", "cert", "max_redirects", "trust_env", "proxies", "params"):
        if not _plain(state.get(name)):
            return f"the custom session {name} value {type(state.get(name)).__name__}"
    if type(state.get("proxies")) is not dict or type(state.get("params")) is not dict:
        return "a custom proxies or params mapping"
    headers = state.get("headers")
    if type(headers) is requests.structures.CaseInsensitiveDict:
        if _shadowed(headers, requests.structures.CaseInsensitiveDict):
            return "an overridden header mapping"
        store = vars(headers).get("_store")
        if type(store) is not collections.OrderedDict or not all(
                type(entry) is tuple and _plain(entry) for entry in store.values()):
            return "custom header values"
    elif not (type(headers) is dict and _plain(headers)):
        return f"the custom header mapping {type(headers).__name__}"
    hooks = state.get("hooks")
    if type(hooks) is not dict:
        return f"the custom hooks container {type(hooks).__name__}"
    for event, callbacks in hooks.items():
        if type(event) is not str or type(callbacks) is not list or callbacks:
            return "session hooks"
    auth = state.get("auth")
    if auth is not None:
        if type(auth) is tuple:
            if len(auth) != 2 or not all(type(part) in (str, bytes) for part in auth):
                return "a custom session auth tuple"
        elif type(auth) is requests.auth.HTTPBasicAuth:
            if _shadowed(auth, requests.auth.HTTPBasicAuth) or not all(
                    type(vars(auth).get(part)) in (str, bytes) for part in ("username", "password")):
                return "a customized HTTPBasicAuth"
        else:
            return f"the custom session auth {type(auth).__name__}"
    jar = state.get("cookies")
    if type(jar) is not requests.cookies.RequestsCookieJar or _shadowed(jar, requests.cookies.RequestsCookieJar):
        return f"the custom cookie jar {type(jar).__name__}"
    policy = vars(jar).get("_policy")
    if type(policy) is not http.cookiejar.DefaultCookiePolicy or _shadowed(policy, http.cookiejar.DefaultCookiePolicy):
        return f"the custom cookie policy {type(policy).__name__}"
    if not _plain(vars(policy)):
        return "customized cookie policy settings"
    domains = vars(jar).get("_cookies")
    if type(domains) is not dict:
        return "a custom cookie store"
    for paths in domains.values():
        if type(paths) is not dict:
            return "a custom cookie store"
        for names in paths.values():
            if type(names) is not dict:
                return "a custom cookie store"
            for cookie in names.values():
                if type(cookie) is not http.cookiejar.Cookie or _shadowed(cookie, http.cookiejar.Cookie) or not _plain(
                        vars(cookie)):
                    return "a custom cookie"
    adapters = state.get("adapters")
    if type(adapters) is not collections.OrderedDict:
        return f"the custom adapter mapping {type(adapters).__name__}"
    for prefix, adapter in adapters.items():
        if type(prefix) is not str:
            return "a custom adapter prefix"
        if type(adapter) is not requests.adapters.HTTPAdapter or _shadowed(adapter, requests.adapters.HTTPAdapter):
            return f"the custom transport adapter {type(adapter).__name__} mounted at {prefix!r}"
        settings = vars(adapter)
        sizes = [settings.get(name) for name in ("_pool_connections", "_pool_maxsize", "_pool_block")]
        config = settings.get("config")
        if not all(type(size) in (int, bool) for size in sizes) or type(config) is not dict or config:
            return f"customized pool settings on the adapter mounted at {prefix!r}"
        reference = requests.adapters.HTTPAdapter(*sizes[:2], pool_block=sizes[2])
        problem = _pool_problem(settings.get("poolmanager"), reference, PoolManager, "connection pool")
        if problem:
            return f"{problem} on the adapter mounted at {prefix!r}"
        proxies = settings.get("proxy_manager")
        if type(proxies) is not dict:
            return f"a custom proxy-manager mapping on the adapter mounted at {prefix!r}"
        for proxy, manager in proxies.items():
            if type(proxy) is not str:
                return "a custom proxy key"
            problem = _pool_problem(manager, reference, ProxyManager, "proxy manager")
            if problem:
                return f"{problem} for {proxy!r}"
        retries = settings.get("max_retries")
        if type(retries) is not Retry or _shadowed(retries, Retry) or not _plain(vars(retries)):
            return f"the custom retry policy {type(retries).__name__} mounted at {prefix!r}"
    return None


def _deadline_retries(retries, prefix):
    if type(retries) is not Retry:
        raise BeastStudioError(
            f"wait(timeout=...) cannot bound the custom retry policy {type(retries).__name__} mounted at "
            f"{prefix!r}; nothing was sent. Use wait() without a timeout, or urllib3's Retry.")
    bounded = copy.copy(retries)
    bounded.__class__ = _DeadlineRetry
    return bounded


class _DeadlineAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = _TRACKED_POOLS

    def proxy_manager_for(self, proxy, **kwargs):
        manager = super().proxy_manager_for(proxy, **kwargs)
        if type(manager) is ProxyManager:  # SOCKS managers keep their own pools
            manager.pool_classes_by_scheme = _TRACKED_POOLS
        return manager


class BeastStudioError(RuntimeError):
    """Raised only for transport-level failures (connection refused, non-JSON
    response). API-level errors (validation, not-found, backend-down) are
    NOT raised by default — they come back as {"error": ..., "code": ...}
    dicts, matching AGENT_ACCESS.md's contract, unless raise_for_status=True
    was passed to the client constructor."""


class BeastStudioClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL,
                 session: Optional[requests.Session] = None,
                 timeout: float = 30, raise_for_status: bool = False):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout
        self.raise_for_status = raise_for_status

    # ---- transport ----

    def _request(self, method: str, path: str, *, json_body: Any = None,
                 headers: Optional[dict] = None, timeout: Optional[float] = None,
                 deadline: Optional[float] = None, http: Any = None) -> Any:
        url = f"{self.base_url}{path}"
        try:
            if deadline is not None:
                budget = max(0.001, min(self.timeout, deadline - time.monotonic()))
                with (http or self.session).request(method, url, json=json_body, headers=headers,
                                          timeout=(budget, budget), stream=True) as r:
                    if self.raise_for_status:
                        r.raise_for_status()
                    body = bytearray()
                    for chunk in r.iter_content(chunk_size=1):
                        if time.monotonic() >= deadline:
                            raise BeastStudioError(f"{method} {path} exceeded wait deadline")
                        body.extend(chunk)
                        if len(body) > 1_048_576:
                            raise BeastStudioError("job status exceeds 1MiB")
                    try:
                        return json.loads(body)
                    except ValueError as e:
                        raise BeastStudioError(f"{method} {path} returned non-JSON") from e
            r = self.session.request(method, url, json=json_body, headers=headers,
                                     timeout=self.timeout if timeout is None else timeout)
        except requests.RequestException as e:
            raise BeastStudioError(f"{method} {path} failed: {e}") from e
        if self.raise_for_status:
            r.raise_for_status()
        try:
            return r.json()
        except ValueError as e:
            raise BeastStudioError(
                f"{method} {path} returned non-JSON (status {r.status_code}): "
                f"{r.text[:200]}") from e

    def _get(self, path: str) -> Any:
        return self._request("GET", path)

    def _post(self, path: str, body: dict, *, headers: Optional[dict] = None,
              timeout: Optional[float] = None) -> Any:
        return self._request(
            "POST", path, json_body=body, headers=headers, timeout=timeout)

    # ---- sync endpoints (result in the response) ----

    def recipes(self) -> List[Dict[str, str]]:
        return self._get("/api/recipes")

    def upload(self, name: str, data: str) -> Dict[str, Any]:
        """`data` is a dataURL or raw base64 string."""
        return self._post("/api/upload", {"name": name, "data": data})

    def expand(self, brief: str, recipe: str = "cinematic-scene") -> Dict[str, Any]:
        return self._post("/api/expand", {"brief": brief, "recipe": recipe})

    def judge(self, file: str, brief: str) -> Dict[str, Any]:
        return self._post("/api/judge", {"file": file, "brief": brief})

    def tts(self, text: str, voice: str = "af_heart") -> Dict[str, Any]:
        return self._post("/api/tts", {"text": text, "voice": voice})

    def backends(self) -> List[Dict[str, Any]]:
        return self._get("/api/backends")

    def backend(self, name: str, action: BackendAction,
                timeout: Optional[float] = None) -> Dict[str, Any]:
        """Start/stop a backend synchronously.

        NIM starts wait for server-side readiness (up to 25 minutes for WAN,
        eight minutes for other NIMs), so their transport timeout is longer
        than the client's normal 30-second request timeout. Pass ``timeout``
        to choose a shorter or longer explicit limit.
        """
        if timeout is None and name in NIM_BACKENDS:
            timeout = (BACKEND_START_TIMEOUTS.get(
                name, DEFAULT_NIM_START_TIMEOUT)
                if action == "start" else NIM_STOP_TIMEOUT)
        return self._post(
            "/api/backend", {"name": name, "action": action}, timeout=timeout)

    def health(self) -> Dict[str, Any]:
        return self._get("/api/health")

    def registry(self, kind: Optional[str] = None,
                 content_class: str = "general",
                 allow_cloud: bool = True) -> Dict[str, Any]:
        """Capability discovery. With ``kind``, returns the resolution order
        (local-first, then authenticated cloud) plus per-backend skip reasons;
        without it, the full capability map."""
        from urllib.parse import urlencode
        params = {"content_class": content_class,
                  "allow_cloud": str(allow_cloud).lower()}
        if kind:
            params["kind"] = kind
        return self._get(f"/api/registry?{urlencode(params)}")

    def ledger_verify(self) -> Dict[str, Any]:
        """Walk the tamper-evident provenance chain; names the first break."""
        return self._get("/api/ledger/verify")

    def runs(self) -> List[Dict[str, Any]]:
        return self._get("/api/runs")

    # ---- async-submit endpoints (return {id, idempotent_replay}) ----

    def run(self, brief: str, prompt: str = "",
            variations: Optional[List[str]] = None,
            model: ImageModel = "local:flux.1-schnell",
            aspect_ratio: AspectRatio = "1:1", reference: str = "",
            idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._post("/api/run", {
            "brief": brief, "prompt": prompt, "variations": variations or [],
            "model": model, "aspect_ratio": aspect_ratio, "reference": reference,
        }, headers=headers)

    def refine(self, file: str, instruction: str, brief: str = "",
               allow_cloud_fallback: bool = False) -> Dict[str, Any]:
        """allow_cloud_fallback=True spends the human's Higgsfield credits —
        only pass True when explicitly told to (AGENT_ACCESS.md rule 1)."""
        return self._post("/api/refine", {
            "file": file, "instruction": instruction, "brief": brief,
            "allow_cloud_fallback": allow_cloud_fallback,
        })

    def animate(self, file: str, motion: str = "slow cinematic dolly-in, subtle ambient movement",
                duration: AnimateDuration = 5, quality: AnimateQuality = "fast",
                allow_cloud_fallback: bool = False) -> Dict[str, Any]:
        """allow_cloud_fallback=True spends the human's Higgsfield credits —
        only pass True when explicitly told to."""
        return self._post("/api/animate", {
            "file": file, "motion": motion, "duration": duration,
            "quality": quality, "allow_cloud_fallback": allow_cloud_fallback,
        })

    def to3d(self, file: str, allow_hosted_fallback: bool = False) -> Dict[str, Any]:
        """allow_hosted_fallback=True lets the image LEAVE this machine to
        NVIDIA's hosted API — only pass True when explicitly told to."""
        return self._post("/api/to3d", {
            "file": file, "allow_hosted_fallback": allow_hosted_fallback,
        })

    def to_ue(self, file: str) -> Dict[str, Any]:
        """`file` is runs/<id>/model.glb."""
        return self._post("/api/to_ue", {"file": file})

    # ---- status / control ----

    def status(self, run_id: str) -> Dict[str, Any]:
        return self._get(f"/api/run/{quote(run_id, safe='')}")

    def cancel(self, run_id: str) -> Dict[str, Any]:
        return self._post(f"/api/job/{quote(run_id, safe='')}/cancel", {})

    def retry(self, run_id: str) -> Dict[str, Any]:
        return self._post(f"/api/job/{quote(run_id, safe='')}/retry", {})

    def events_url(self, run_id: str) -> str:
        """URL of the SSE stream for this job — GET it with any SSE client,
        or use stream_events() below for a dependency-free generator."""
        return f"{self.base_url}/api/events/{quote(run_id, safe='')}"

    def stream_events(self, run_id: str) -> Iterator[Dict[str, Any]]:
        """Yield each JSON status snapshot as the server emits it over SSE,
        stopping after a terminal phase (done/failed/cancelled) or when the
        stream closes. Supports multiline data and CRLF; malformed events
        raise BeastStudioError. Use wait(timeout=...) for a total deadline."""
        return self._stream_events(run_id)

    def _stream_events(self, run_id: str, timeout: Optional[float] = None,
                       http: Any = None) -> Iterator[Dict[str, Any]]:
        deadline = None if timeout is None else time.monotonic() + timeout
        # The server emits only on phase change, so an unbounded stream must not
        # time out while a long phase is quiet; a deadline bounds every read.
        connect_timeout = self.timeout if timeout is None else min(self.timeout, timeout)
        read_timeout = None if timeout is None else connect_timeout
        try:
            with (http or self.session).get(self.events_url(run_id), stream=True,
                                  timeout=(connect_timeout, read_timeout)) as r:
                if r.status_code >= 400:
                    raise BeastStudioError(f"GET /api/events/{run_id} returned HTTP {r.status_code}")
                data_lines = []
                event_size = 0
                for raw in _bounded_lines(r, deadline):
                    if deadline is not None and time.monotonic() >= deadline:
                        raise BeastStudioError(f"GET /api/events/{run_id} timed out")
                    if raw.startswith("data:"):
                        value = raw[len("data:"):]
                        value = value[1:] if value.startswith(" ") else value
                        event_size += len(value)
                        if event_size > 1_048_576:
                            raise BeastStudioError("SSE event exceeds 1MiB")
                        data_lines.append(value)
                        continue
                    if raw or not data_lines:
                        continue
                    payload = "\n".join(data_lines)
                    data_lines.clear()
                    event_size = 0
                    if not payload.strip():
                        continue
                    snap = json.loads(payload)
                    if not isinstance(snap, dict) or not isinstance(snap.get("phase"), str):
                        raise BeastStudioError("SSE event is not a job status snapshot")
                    yield snap
                    if snap.get("phase") in TERMINAL_PHASES:
                        return
        except (requests.RequestException, ValueError) as e:
            raise BeastStudioError(f"GET /api/events/{run_id} interrupted or malformed: {e}") from e

    def wait(self, run_id: str, poll_interval: float = 3,
             timeout: Optional[float] = None, use_sse: bool = True) -> Dict[str, Any]:
        """Wait for terminal status. A finite timeout bounds the whole call,
        including transport reads: the call runs in the caller's thread and, at
        the deadline, every socket it is blocked on is shut down and any name
        lookup child is killed, so nothing keeps running after wait() returns.
        A finite timeout needs a requests.Session with standard adapters; any
        other transport is refused before a request is sent.
        """
        if not math.isfinite(poll_interval) or poll_interval < 0 or (
                timeout is not None and (not math.isfinite(timeout) or timeout < 0)):
            raise BeastStudioError("wait intervals and timeout must be finite and nonnegative")
        if timeout is None:
            return self._wait_impl(run_id, poll_interval, None, use_sse)
        if timeout == 0:
            raise BeastStudioError(f"job {run_id} did not reach a terminal phase within 0s")
        scope = _DeadlineScope(timeout)
        http = self._deadline_session()  # refuses before anything is sent
        timer = threading.Timer(timeout, scope.expire)
        timer.name = "beast-wait-deadline"
        timer.daemon = True
        outer = getattr(_ACTIVE_SCOPE, "scope", None)
        _ACTIVE_SCOPE.scope = scope
        timer.start()
        try:
            return self._wait_impl(run_id, poll_interval, timeout, use_sse, http)
        except BeastStudioError as error:
            if scope.expired or time.monotonic() >= scope.deadline:
                raise BeastStudioError(
                    f"job {run_id} did not reach a terminal phase within {timeout}s") from error
            raise
        finally:
            timer.cancel()
            timer.join()
            _ACTIVE_SCOPE.scope = outer
            http.close()
            scope.close()

    def _deadline_session(self) -> Any:
        """A private session and connection pool for one bounded wait, so one
        wait's deadline can never cut a connection another call borrowed.

        It carries the caller's session state (headers, cookies, auth, proxies,
        TLS settings) and reproduces every standard requests HTTPAdapter mount at
        its prefix with the same retry and pool settings. Anything the deadline
        cannot reach (a custom adapter or Retry class, custom auth callable,
        session hooks or cookie jar, a Session subclass or non-requests
        session) is refused here, before any
        callback runs or request is sent, rather than silently replaced or left
        unbounded."""
        base = self.session
        if not isinstance(base, requests.Session):
            raise BeastStudioError(
                "wait(timeout=...) needs a plain requests.Session to enforce its deadline; got "
                f"{type(base).__name__}; nothing was sent. Use wait() without a timeout for a custom session.")
        problem = _caller_policy_problem(base)
        if problem:
            raise BeastStudioError(
                f"wait(timeout=...) cannot carry {problem} through its deadline; nothing was sent and no caller "
                "code was called. Use wait() without a timeout for a customized session.")
        private = requests.Session()
        private.adapters.clear()
        for prefix, adapter in base.adapters.items():
            private.mount(prefix, _DeadlineAdapter(
                pool_connections=adapter._pool_connections, pool_maxsize=adapter._pool_maxsize,
                max_retries=_deadline_retries(adapter.max_retries, prefix), pool_block=adapter._pool_block))
        for name in ("headers", "cookies", "auth", "proxies", "hooks", "params",
                     "verify", "cert", "trust_env", "max_redirects"):
            setattr(private, name, getattr(base, name))
        return private

    def _wait_impl(self, run_id: str, poll_interval: float,
                   timeout: Optional[float], use_sse: bool, http: Any = None) -> Dict[str, Any]:
        """Block until the job reaches a terminal phase, return its final
        status. Prefers SSE (one connection, pushed updates); falls back to
        polling status() if use_sse=False or the stream errors."""
        t0 = time.monotonic()
        if not math.isfinite(poll_interval) or poll_interval < 0 or (
                timeout is not None and (not math.isfinite(timeout) or timeout < 0)):
            raise BeastStudioError("wait intervals and timeout must be finite and nonnegative")

        def remaining():
            if timeout is None:
                return None
            value = timeout - (time.monotonic() - t0)
            if value <= 0:
                raise BeastStudioError(
                    f"job {run_id} did not reach a terminal phase within {timeout}s")
            return value

        if use_sse:
            try:
                last = None
                for snap in self._stream_events(run_id, timeout=remaining(), http=http):
                    last = snap
                    remaining()
                if last is not None and last.get("phase") in TERMINAL_PHASES:
                    return last
            except BeastStudioError:
                pass  # fall through to polling
        while True:
            budget = remaining()
            try:
                snap = self.status(run_id) if budget is None else self._request(
                    "GET", f"/api/run/{quote(run_id, safe='')}",
                    timeout=min(self.timeout, budget), deadline=t0 + timeout, http=http)
            except BeastStudioError:
                remaining()  # a transport failure at the deadline is the deadline
                raise
            remaining()
            if not isinstance(snap, dict):
                raise BeastStudioError(f"job {run_id} returned invalid status: {snap}")
            if snap.get("phase") in TERMINAL_PHASES:
                return snap
            if not isinstance(snap.get("phase"), str):
                raise BeastStudioError(f"job {run_id} returned no phase: {snap}")
            time.sleep(poll_interval if budget is None else min(poll_interval, remaining()))
