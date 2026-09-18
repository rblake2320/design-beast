"""Real retained provider pixels through Studio's existing upload route."""
import base64
import hashlib
from pathlib import Path

from fastapi.testclient import TestClient
import server


def test_retained_higgsfield_asset_upload_and_resolve(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[2] / "proofs/higgsfield-creative/refined-4k.png"
    raw = source.read_bytes()
    monkeypatch.setattr(server, "UPLOADS", tmp_path)
    with TestClient(server.app) as client:
        response = client.post("/api/upload", json={
            "name": "higgsfield-refined.png", "data": base64.b64encode(raw).decode("ascii")})
    assert response.status_code == 200
    imported = tmp_path / response.json()["file"]
    assert hashlib.sha256(imported.read_bytes()).digest() == hashlib.sha256(raw).digest()
    # Existing refine/animate entrypoints use this same resolver.
    assert server._resolve(response.json()["file"]) == imported.resolve()
