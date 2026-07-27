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

import json
import time
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import quote

import requests

from .models import AnimateDuration, AnimateQuality, AspectRatio, BackendAction, ImageModel

DEFAULT_BASE_URL = "http://127.0.0.1:8787"
TERMINAL_PHASES = ("done", "failed", "cancelled")
NIM_BACKENDS = frozenset(
    ("nim-flux", "nim-kontext", "nim-flux2", "nim-trellis", "nim-wan"))
BACKEND_START_TIMEOUTS = {"nim-wan": 2130.0}
DEFAULT_NIM_START_TIMEOUT = 510.0
NIM_STOP_TIMEOUT = 150.0


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
                 headers: Optional[dict] = None, timeout: Optional[float] = None) -> Any:
        url = f"{self.base_url}{path}"
        try:
            r = self.session.request(method, url, json=json_body, headers=headers,
                                     timeout=timeout or self.timeout)
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
        stream closes. No external SSE dependency — parses `data: ` lines."""
        try:
            resp_ctx = self.session.get(self.events_url(run_id), stream=True,
                                        timeout=(self.timeout, None))
        except requests.RequestException as e:
            raise BeastStudioError(f"GET /api/events/{run_id} failed: {e}") from e
        with resp_ctx as r:
            for raw in r.iter_lines(decode_unicode=True):
                if not raw or not raw.startswith("data:"):
                    continue
                payload = raw[len("data:"):].strip()
                if not payload:
                    continue
                snap = json.loads(payload)
                yield snap
                if snap.get("phase") in TERMINAL_PHASES:
                    return

    def wait(self, run_id: str, poll_interval: float = 3,
             timeout: Optional[float] = None, use_sse: bool = True) -> Dict[str, Any]:
        """Block until the job reaches a terminal phase, return its final
        status. Prefers SSE (one connection, pushed updates); falls back to
        polling status() if use_sse=False or the stream errors."""
        t0 = time.monotonic()
        if use_sse:
            try:
                last = None
                for snap in self.stream_events(run_id):
                    last = snap
                    if timeout is not None and time.monotonic() - t0 > timeout:
                        break
                if last is not None and last.get("phase") in TERMINAL_PHASES:
                    return last
            except BeastStudioError:
                pass  # fall through to polling
        while True:
            snap = self.status(run_id)
            if snap.get("phase") in TERMINAL_PHASES:
                return snap
            if timeout is not None and time.monotonic() - t0 > timeout:
                raise BeastStudioError(
                    f"job {run_id} did not reach a terminal phase within {timeout}s "
                    f"(last phase: {snap.get('phase')})")
            time.sleep(poll_interval)
