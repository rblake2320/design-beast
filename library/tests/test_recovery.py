"""Fault injection: every failure class in library/recover.py, reproduced for real (no mocks)."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from library import dedup, inventory, organize, recover, review  # noqa: E402
from library.store import Store  # noqa: E402
from library.tests.test_library import _fake_free_review, _photo  # noqa: E402


@pytest.fixture
def placed(tmp_path: Path):
    src = tmp_path / "src"; src.mkdir()
    for i, name in enumerate(("a.jpg", "b.jpg", "c.jpg")):
        _photo(src / name, 100 + i)
    store = Store(tmp_path / "lib.db")
    inventory.scan(store, src)
    dedup.cluster(store, embed_model=None)
    _fake_free_review(store, {"a.jpg": "Trip", "b.jpg": "Trip", "c.jpg": "Home"})
    dest = tmp_path / "out"
    organize.plan(store, dest, ollama_url="http://127.0.0.1:9/api/generate")
    organize.approve(store, everything=True)
    assert organize.apply(store)["applied"] == 3
    return store, src, dest


def test_worker_death_mid_stage_is_reclaimed_automatically(tmp_path: Path):
    src = tmp_path / "src"; src.mkdir(); _photo(src / "a.jpg", 1)
    store = Store(tmp_path / "lib.db"); inventory.scan(store, src)
    aid = store.claim("embed", "worker-that-died")
    store.execute("UPDATE queue SET claimed_at = '2000-01-01T00:00:00' WHERE asset_id = ? AND stage = 'embed'", (aid,))
    store.commit()
    assert store.queue_counts()["embed"] == {"running": 1}
    assert store.reclaim_stale("embed") == 1                    # what every stage does at start
    assert store.queue_counts()["embed"] == {"pending": 1}
    assert store.claim("embed", "fresh-worker") == aid
    assert store.reclaim_stale("embed") == 0                    # a live claim is left alone


def test_model_server_outage_returns_work_to_pending_not_error(tmp_path: Path):
    src = tmp_path / "src"; src.mkdir()
    for i in range(3):
        _photo(src / f"{i}.jpg", 10 + i)
    store = Store(tmp_path / "lib.db"); inventory.scan(store, src); dedup.cluster(store, embed_model=None)
    review.BACKEND_DOWN_AFTER, saved = 2, review.BACKEND_DOWN_AFTER
    try:
        t0 = time.time()
        out = review.run(lambda: Store(tmp_path / "lib.db"), "fast", "any", "http://127.0.0.1:9/api/generate",
                         parallel=1)
    finally:
        review.BACKEND_DOWN_AFTER = saved
    assert out["backend_down"] is True and out["failed"] == 0 and "backend_error" in out
    assert store.queue_counts()["review_fast"] == {"pending": 3}   # nothing marked error
    assert time.time() - t0 < 30


def test_crash_mid_copy_leaves_no_half_file_and_is_redone(placed):
    store, src, dest = placed
    victim = next(dest.rglob("*_a.jpg"))
    partial = victim.with_name(victim.name + ".beast-partial")
    victim.unlink()
    partial.write_bytes(b"half of a photo")                     # what a crash during copy leaves behind
    out = recover.run(store, verify="all")
    assert out["partials_removed"] == 1 and out["verify"]["missing_reapproved"] == 1
    assert not partial.exists()
    assert organize.apply(store)["applied"] == 1
    assert hashlib.sha256(victim.read_bytes()).hexdigest() == \
        hashlib.sha256((src / "a.jpg").read_bytes()).hexdigest()


def test_changed_organized_file_is_reported_never_overwritten(placed):
    store, src, dest = placed
    edited = next(dest.rglob("*_b.jpg"))
    edited.write_bytes(b"user edited this copy")
    out = recover.verify_placed(store, "all")
    assert out == {"checked": 3, "ok": 2, "missing_reapproved": 0, "changed": 1}
    assert organize.apply(store)["applied"] == 0
    assert edited.read_bytes() == b"user edited this copy"


def test_backup_restore_round_trip_and_integrity_gate(placed, tmp_path: Path):
    store, src, dest = placed
    out = recover.backup(store, tmp_path / "backups")
    bak = Path(out["path"])
    assert bak.exists() and Store(bak).integrity() == "ok"
    db = Path(store.target)
    store.close()
    db.write_bytes(b"corrupted beyond repair")
    with pytest.raises(Exception):
        Store(db).counts()
    res = recover.restore(bak, db)
    assert res["counts"]["assets"] == 3 and res["counts"]["proposals_applied"] == 3
    assert db.with_suffix(".db.before-restore").exists()
    bad = tmp_path / "bad.db"; bad.write_bytes(b"not a database")
    with pytest.raises(RuntimeError):
        recover.restore(bad, db)


def test_lost_store_rebuilt_from_manifest_without_recopying(placed, tmp_path: Path):
    store, src, dest = placed
    manifest = dest / ".beast" / "manifest.json"
    assert manifest.exists() and json.loads(manifest.read_text())["count"] == 3
    store.close()
    fresh = Store(tmp_path / "fresh.db")
    out = recover.rebuild_from_manifest(fresh, dest)
    assert out == {"restored": 3, "missing": 0, "manifest_count": 3}
    assert fresh.counts()["assets"] == 3 and fresh.counts()["proposals_applied"] == 3
    before = sorted(p.stat().st_mtime for p in dest.rglob("*.jpg"))
    assert organize.apply(fresh)["applied"] == 0                  # nothing copied twice
    assert sorted(p.stat().st_mtime for p in dest.rglob("*.jpg")) == before


def test_reconcile_moves_files_when_album_changes(placed):
    store, src, dest = placed
    b = next(a for a in store.assets() if a["path"].endswith("b.jpg"))
    store.put_album(b["id"], "Beach", "group", 1); store.commit()     # a later, better decision
    out = organize.plan(store, dest, ollama_url="http://127.0.0.1:9/api/generate")
    assert out["moves"] == 1
    move = next(p for p in store.proposals("pending") if p["action"] == "move:link")
    old = next(x for x in store.proposals("applied") if x["asset_id"] == b["id"] and x["action"] == "link")["dest"]
    assert "Trip" in old and "Beach" in move["dest"]
    organize.approve(store, everything=True)
    assert organize.apply(store)["moved"] == 1
    assert not Path(old).exists() and Path(move["dest"]).exists()
    assert not (dest / "Trip").exists() or any((dest / "Trip").rglob("*"))   # empty album dir tidied
    assert sorted(p.name for p in src.iterdir()) == ["a.jpg", "b.jpg", "c.jpg"]   # source untouched


def test_private_assets_never_reach_a_remote_worker(tmp_path: Path):
    src = tmp_path / "src"; (src / "IDs").mkdir(parents=True); (src / "Trips").mkdir()
    _photo(src / "IDs" / "passport.jpg", 5); _photo(src / "Trips" / "beach.jpg", 6)
    store = Store(tmp_path / "lib.db"); inventory.scan(store, src)
    private = {Path(a["path"]).parent.name: a["private"] for a in store.assets()}
    assert private == {"IDs": 1, "Trips": 0}
    got = store.claim("review_fast", "spark-1", remote=True)
    assert store.asset(got)["path"].endswith("beach.jpg")
    assert store.claim("review_fast", "spark-1", remote=True) is None       # the passport is never offered
    local = store.claim("review_fast", "local")
    assert store.asset(local)["path"].endswith("passport.jpg")
    assert store.get_thumb_for(local, remote=True) is None and store.get_thumb_for(local, remote=False)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_video_is_inventoried_through_a_real_frame(tmp_path: Path):
    src = tmp_path / "src"; src.mkdir()
    clip = src / "clip.mp4"
    subprocess.run([shutil.which("ffmpeg"), "-v", "quiet", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=10",
                    "-t", "3", "-pix_fmt", "yuv420p", str(clip)], check=True)
    store = Store(tmp_path / "lib.db")
    out = inventory.scan(store, src)
    assert out["added_or_updated"] == 1 and out["failed"] == 0
    a = store.assets()[0]
    assert a["format"] == "video" and (a["width"], a["height"]) == (640, 360) and 2.5 <= a["duration"] <= 3.5
    thumb = store.get_thumb(a["id"])
    assert thumb[:2] == b"\xff\xd8" and Image.open(__import__("io").BytesIO(thumb)).size[0] == 640
