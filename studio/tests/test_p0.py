"""P0 integration tests — run against a live Studio server (localhost:8787).

    cd design-beast && python -m pytest studio/tests/test_p0.py -q

GPU-free: covers validation, idempotency, lifecycle metadata, cancel/retry rules,
and health. Restart-recovery is exercised by scripts (kills the server) — see
ROADMAP P0 notes; it is verified manually: orphaned running jobs must become
failed/INTERNAL with 'server restarted mid-job'.
"""
import uuid

import requests

B = "http://127.0.0.1:8787"


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
    if s.get("phase") == "done":
        assert r.status_code == 400  # done jobs are not retryable
    else:
        assert r.status_code == 200 and "id" in r.json()


def test_unknown_job_404():
    assert requests.get(f"{B}/api/run/nope_0000", timeout=10).status_code == 404
    assert requests.post(f"{B}/api/job/nope_0000/cancel", timeout=10).status_code == 404
