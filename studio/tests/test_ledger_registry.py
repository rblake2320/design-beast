"""Offline tests for the chained ledger and the backend registry resolver."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ledger
import registry


def _append(path, n):
    entries = []
    for i in range(n):
        entries.append(ledger.append(
            path, run_id=f"run{i}", kind="image", model="comfy:flux.1-schnell",
            manifest_sha256="ab" * 32,
            artifacts=[{"file": "cand0.png", "sha256": "cd" * 32}],
            outcome="done"))
    return entries


def test_ledger_chain_appends_and_verifies(tmp_path):
    path = tmp_path / "ledger.jsonl"
    entries = _append(path, 3)
    assert all(e is not None for e in entries)
    assert entries[0]["prev"] == "0" * 64
    assert entries[1]["prev"] == entries[0]["chain_hash"]
    ok, msg = ledger.verify(path)
    assert ok, msg
    assert "3 entries" in msg


def test_ledger_detects_modification(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _append(path, 3)
    lines = path.read_text().splitlines()
    doc = json.loads(lines[1])
    doc["model"] = "swapped-after-the-fact"
    lines[1] = json.dumps(doc, sort_keys=True)
    path.write_text("\n".join(lines) + "\n")
    ok, msg = ledger.verify(path)
    assert not ok and "line 2" in msg and "modified" in msg


def test_ledger_detects_deletion(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _append(path, 3)
    lines = path.read_text().splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n")
    ok, msg = ledger.verify(path)
    assert not ok and "prev-link broken" in msg


_BACKENDS = [
    {"id": "local-a", "kind": "image", "hosting": "local", "auth": "none",
     "content_classes": ["general", "mature"]},
    {"id": "cloud-byok", "kind": "image", "hosting": "cloud", "auth": "byok",
     "key_env": "TEST_FAKE_KEY", "content_classes": ["general"]},
    {"id": "cloud-sub", "kind": "image", "hosting": "cloud", "auth": "subscription",
     "auth_cmd": "definitely-not-a-command", "content_classes": ["general"]},
    {"id": "video-only", "kind": "video", "hosting": "local", "auth": "none",
     "content_classes": ["general"]},
]


def test_resolve_local_first_and_reasons(monkeypatch):
    monkeypatch.delenv("TEST_FAKE_KEY", raising=False)
    out = registry.resolve("image", backends=_BACKENDS)
    ids = [b["id"] for b in out["eligible"]]
    assert ids[0] == "local-a"
    assert "cloud-sub" in ids  # unprobed subscription stays eligible
    reasons = {s["id"]: s["reason"] for s in out["skipped"]}
    assert "TEST_FAKE_KEY" in reasons["cloud-byok"]


def test_resolve_byok_unlocks_cloud(monkeypatch):
    monkeypatch.setenv("TEST_FAKE_KEY", "sk-live-whatever")
    out = registry.resolve("image", backends=_BACKENDS)
    ids = [b["id"] for b in out["eligible"]]
    assert ids.index("local-a") < ids.index("cloud-byok")


def test_resolve_content_class_policy(monkeypatch):
    monkeypatch.setenv("TEST_FAKE_KEY", "sk-live-whatever")
    out = registry.resolve("image", content_class="mature", backends=_BACKENDS)
    assert [b["id"] for b in out["eligible"]] == ["local-a"]
    reasons = {s["id"]: s["reason"] for s in out["skipped"]}
    assert "provider terms" in reasons["cloud-byok"]


def test_resolve_cloud_disabled(monkeypatch):
    monkeypatch.setenv("TEST_FAKE_KEY", "sk-live-whatever")
    out = registry.resolve("image", allow_cloud=False, backends=_BACKENDS)
    assert [b["id"] for b in out["eligible"]] == ["local-a"]


def test_shipped_registry_file_loads_and_covers_kinds():
    entries = registry.load()
    kinds = {b["kind"] for b in entries}
    assert {"image", "video", "tts", "music", "judge"} <= kinds
    for b in entries:
        assert b.get("hosting") in ("local", "cloud"), b["id"]
        assert b.get("content_classes"), b["id"]
    # every kind has at least one free local default — the product promise
    for kind in kinds:
        assert any(b["kind"] == kind and b["hosting"] == "local"
                   for b in entries), f"no local default for {kind}"
