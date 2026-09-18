from fastapi.testclient import TestClient
import server


def test_saved_assets_are_contained_images(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "UPLOADS", tmp_path)
    (tmp_path / "image.png").write_bytes(b"already uploaded")
    (tmp_path / "secret.json").write_text("private")
    (tmp_path / "directory.png").mkdir()
    with TestClient(server.app) as client:
        assert client.get("/api/uploads").json() == [{"file": "image.png"}]


def test_saved_assets_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "UPLOADS", tmp_path)
    with TestClient(server.app) as client:
        assert client.get("/api/uploads").json() == []
