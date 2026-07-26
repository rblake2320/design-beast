"""P0 integration tests — run against a live Studio server (localhost:8787).

MARKED live_gpu: the idempotency/cancel/retry tests submit REAL /api/run jobs
that consume GPU time. Excluded from the default suite (pytest.ini) — run
intentionally with:

    cd design-beast && python -m pytest -m live_gpu -q

Never run alongside benchmarks or demos: the spawned jobs contend for the GPU
and contaminate timings (this bit us on 2026-07-26). Every spawned job is
cancelled in cleanup so nothing is left rendering after the suite exits.

Restart-recovery is exercised by scripts (kills the server) — verified
manually: orphaned running jobs must become failed/INTERNAL.
"""
import uuid

import pytest
import requests

pytestmark = pytest.mark.live_gpu

B = "http://127.0.0.1:8787"


def _cancel(job_id: str):
    """Best-effort cleanup so no test-spawned job keeps the GPU busy."""
    try:
        requests.post(f"{B}/api/job/{job_id}/cancel", timeout=10)
    except requests.RequestException:
        pass


def test_health():
    h = requests.get(f"{B}/api/health", timeout=10).json()
    assert h["db"] is True
    assert h["disk_free_gb"] > 5


def test_invalid_model_rejected():
    r = requests.post(f"{B}/api/run", json={"brief": "x y z", "model": "bogus"},
                      timeout=10)
    assert r.status_code == 422


def test_short_brief_rejected():
    r = requests.post(f"{B}/api/run", json={"brief": "ab"}, timeout=10)
    assert r.status_code == 422


def test_reference_with_local_model_rejected():
    r = requests.post(f"{B}/api/run",
                      json={"brief": "test ref", "reference": "foo.png"}, timeout=10)
    assert r.status_code == 400
    assert r.json()["code"] == "VALIDATION"


def test_bad_upload_rejected():
    r = requests.post(f"{B}/api/upload",
                      json={"name": "x.png", "data": "bm90YW5pbWFnZQ=="}, timeout=10)
    assert r.status_code == 422


def test_idempotency_and_cancel_and_retry_rules():
    key = f"pytest-{uuid.uuid4().hex[:8]}"
    body = {"brief": "pytest idempotency shape, tiny abstract"}
    hdr = {"Idempotency-Key": key}
    a = requests.post(f"{B}/api/run", json=body, headers=hdr, timeout=10).json()
    b = requests.post(f"{B}/api/run", json=body, headers=hdr, timeout=10).json()
    assert a["id"] == b["id"]
    assert b["idempotent_replay"] is True

    # cancel it (may already be running; both are legal)
    c = requests.post(f"{B}/api/job/{a['id']}/cancel", timeout=10).json()
    assert c["ok"] is True

    # retry only allowed from terminal failed/cancelled — poll until terminal
    import time
    for _ in range(60):
        s = requests.get(f"{B}/api/run/{a['id']}", timeout=10).json()
        if s.get("phase") in ("done", "failed", "cancelled"):
            break
        time.sleep(3)
    r = requests.post(f"{B}/api/job/{a['id']}/retry", timeout=15)
    try:
        if s.get("phase") == "done":
            assert r.status_code == 400  # done jobs are not retryable
        else:
            assert r.status_code == 200 and "id" in r.json()
    finally:
        # the retry spawns a REAL generation job — never leave it rendering
        if r.status_code == 200 and "id" in r.json():
            _cancel(r.json()["id"])
        _cancel(a["id"])


def test_unknown_job_404():
    assert requests.get(f"{B}/api/run/nope_0000", timeout=10).status_code == 404
    assert requests.post(f"{B}/api/job/nope_0000/cancel", timeout=10).status_code == 404
