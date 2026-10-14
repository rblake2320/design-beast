"""Real HTTP regressions for POST /api/upload.

Runs the actual app under uvicorn on a loopback port. Uploads are redirected to
a throwaway directory so the live uploads/ folder is never touched.
"""
import base64
import io
import json
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest
import uvicorn
from PIL import Image

import server


def _png_b64() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (200, 30, 30)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.fixture(scope="module")
def base_url(tmp_path_factory):
    uploads = tmp_path_factory.mktemp("uploads")
    original = server.UPLOADS
    server.UPLOADS = uploads
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    config = uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="warning")
    running = uvicorn.Server(config)
    thread = threading.Thread(target=running.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not running.started and time.time() < deadline:
        time.sleep(0.05)
    assert running.started, "uvicorn did not start"
    yield f"http://127.0.0.1:{port}", uploads
    running.should_exit = True
    thread.join(timeout=10)
    server.UPLOADS = original


def _post(base, body: dict):
    req = urllib.request.Request(
        f"{base}/api/upload",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _files(uploads):
    return sorted(p.name for p in uploads.iterdir())


def test_valid_png_is_stored_and_reported(base_url):
    base, uploads = base_url
    before = _files(uploads)
    status, body = _post(base, {"name": "ok.png", "data": _png_b64()})
    assert status == 200
    assert body["file"].endswith("_ok.png")
    assert (uploads / body["file"]).exists()
    assert _files(uploads) != before


def test_malformed_base64_is_typed_422_and_writes_nothing(base_url):
    base, uploads = base_url
    before = _files(uploads)
    status, body = _post(base, {"name": "bad.png", "data": "x"})
    assert status == 422
    assert body["code"] == server.E_VALIDATION
    assert _files(uploads) == before


def test_malformed_base64_with_data_url_prefix_is_typed_422(base_url):
    base, uploads = base_url
    before = _files(uploads)
    status, body = _post(base, {"name": "bad.png", "data": "data:image/png;base64,x"})
    assert status == 422
    assert body["code"] == server.E_VALIDATION
    assert _files(uploads) == before


def test_decodable_base64_that_is_not_an_image_is_422_with_no_residue(base_url):
    base, uploads = base_url
    before = _files(uploads)
    status, body = _post(base, {"name": "text.png", "data": base64.b64encode(b"hello world").decode()})
    assert status == 422
    assert body["code"] == server.E_VALIDATION
    assert _files(uploads) == before


def _png_bytes(color) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color).save(buf, format="PNG")
    return buf.getvalue()


def test_same_name_uploads_keep_both_originals(base_url):
    base, uploads = base_url
    first = _png_bytes((255, 0, 0))
    second = _png_bytes((0, 0, 255))
    assert first != second
    status_a, body_a = _post(base, {"name": "same.png", "data": base64.b64encode(first).decode()})
    status_b, body_b = _post(base, {"name": "same.png", "data": base64.b64encode(second).decode()})
    assert status_a == 200 and status_b == 200
    assert body_a["file"] != body_b["file"]
    assert body_a["file"].endswith("_same.png") and body_b["file"].endswith("_same.png")
    assert (uploads / body_a["file"]).read_bytes() == first
    assert (uploads / body_b["file"]).read_bytes() == second


def test_alphabet_invalid_prefix_is_422_and_writes_nothing(base_url):
    base, uploads = base_url
    before = _files(uploads)
    payload = "!!!!" + base64.b64encode(_png_bytes((9, 9, 9))).decode("ascii")
    status, body = _post(base, {"name": "owned-invalid.png", "data": payload})
    assert status == 422
    assert body["code"] == server.E_VALIDATION
    assert _files(uploads) == before


def test_non_ascii_data_is_422_and_writes_nothing(base_url):
    base, uploads = base_url
    before = _files(uploads)
    status, body = _post(base, {"name": "owned-unicode.png", "data": "\u2603"})
    assert status == 422
    assert body["code"] == server.E_VALIDATION
    assert _files(uploads) == before


def test_data_url_with_valid_base64_is_still_accepted(base_url):
    base, uploads = base_url
    raw = _png_bytes((0, 200, 0))
    data_url = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    status, body = _post(base, {"name": "owned-dataurl.png", "data": data_url})
    assert status == 200
    assert (uploads / body["file"]).read_bytes() == raw
