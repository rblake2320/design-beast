"""Library tab API against a real temporary store (FastAPI TestClient, no mocks)."""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "studio"))

from library import dedup, inventory, organize  # noqa: E402
from library.store import Store  # noqa: E402
from library.tests.test_library import _fake_free_review, _photo  # noqa: E402


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    db = tmp_path / "lib.db"
    monkeypatch.setenv("BEAST_LIBRARY_DB", str(db))
    monkeypatch.setenv("BEAST_LIBRARY_DSN", "")
    src = tmp_path / "src"; src.mkdir()
    for i, n in enumerate(("a.jpg", "b.jpg")):
        _photo(src / n, 200 + i)
    store = Store(db); inventory.scan(store, src); dedup.cluster(store, embed_model=None)
    _fake_free_review(store, {"a.jpg": "Trip", "b.jpg": "Trip"})
    organize.plan(store, tmp_path / "out", ollama_url="http://127.0.0.1:9/api/generate")
    store.close()
    import library_api
    importlib.reload(library_api)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI(); app.include_router(library_api.router); app.get("/library")(library_api.page)
    return TestClient(app), tmp_path


def test_page_status_thumb_and_proposal_flow(client):
    c, tmp = client
    assert c.get("/library").status_code == 200 and b"BEAST" in c.get("/library").content
    st = c.get("/api/library/status").json()
    assert st["counts"]["assets"] == 2 and st["counts"]["proposals_pending"] == 2
    aid = c.get("/api/library/search?k=5").json()["results"][0]["id"]
    assert c.get(f"/api/library/thumb/{aid}").headers["content-type"] == "image/jpeg"
    assert c.get("/api/library/thumb/999999").status_code == 404
    pr = c.get("/api/library/proposals").json()
    assert pr["total"] == 2 and pr["albums"][0]["album"] == "Trip"
    assert c.post("/api/library/proposals/approve", json={"album": "Trip"}).json() == {"approved": 2}
    out = c.post("/api/library/apply").json()
    assert out["applied"] == 2 and out["failed"] == 0
    assert sorted(p.name for p in (tmp / "out" / "Trip").rglob("*.jpg")) == ["20260912_a.jpg", "20260912_b.jpg"] or \
        len(list((tmp / "out" / "Trip").rglob("*.jpg"))) == 2
    rec = c.post("/api/library/recover").json()
    assert rec["integrity"] == "ok" and rec["verify"]["ok"] == 2
    assert c.get("/api/library/people").json() == {"people": []}
    assert c.get("/api/library/people/merges").json() == {"merges": []}
