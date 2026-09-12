"""Offline tests: real SQLite store, real Pillow images, real hashing and file operations."""
from __future__ import annotations

import hashlib
import random
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from library import dedup, inventory, organize  # noqa: E402
from library.store import STAGES, Store  # noqa: E402


def _photo(path: Path, seed: int, size=(1600, 1200)) -> Image.Image:
    rnd = random.Random(seed)
    im = Image.new("RGB", size)
    d = ImageDraw.Draw(im)
    for _ in range(40):
        x, y, r = rnd.randint(0, size[0]), rnd.randint(0, size[1]), rnd.randint(40, 300)
        d.ellipse([x, y, x + r, y + r], fill=tuple(rnd.randint(0, 255) for _ in range(3)))
    im.save(path, quality=92)
    return im


@pytest.fixture
def library(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    beach = _photo(src / "beach.jpg", 1)
    _photo(src / "truck.jpg", 2)
    _photo(src / "party.jpg", 3)
    beach.save(src / "beach_copy.jpg", quality=92)                   # exact duplicate
    beach.resize((800, 600)).save(src / "beach_small.jpg", quality=80)  # near duplicate
    doc = Image.new("RGB", (1240, 1754), "white")
    ImageDraw.Draw(doc).text((80, 60), "INVOICE total $13.00", fill="black")
    doc.save(src / "receipt.png")
    store = Store(tmp_path / "lib.db")
    inventory.scan(store, src)
    return store, src, tmp_path


def test_scan_inventories_hashes_thumbs_and_queues(library):
    store, src, _ = library
    assets = store.assets()
    assert len(assets) == 6
    beach = next(a for a in assets if a["path"].endswith("beach.jpg"))
    assert beach["sha256"] == hashlib.sha256((src / "beach.jpg").read_bytes()).hexdigest()
    assert (beach["width"], beach["height"]) == (1600, 1200)
    assert len(beach["phash"]) == 16 and beach["taken_at"]
    assert store.get_thumb(beach["id"])[:2] == b"\xff\xd8"          # JPEG thumbnail stored
    assert store.queue_counts() == {s: {"pending": 6} for s in STAGES}
    again = inventory.scan(store, src)
    assert again["unchanged"] == 6 and again["added_or_updated"] == 0


def test_dedup_folds_exact_and_resized_copies_into_representative(library):
    store, _, _ = library
    out = dedup.cluster(store, embed_model=None)
    assert out == {"assets": 6, "clusters": 4, "duplicates": 2,
                   "edges": {"sha256": 1, "phash": 3, "embedding": 0}}
    by_name = {Path(a["path"]).name: a for a in store.assets()}
    rep = by_name["beach.jpg"]["id"]
    assert by_name["beach.jpg"]["dup_of"] is None
    assert by_name["beach_copy.jpg"]["dup_of"] == rep
    assert by_name["beach_small.jpg"]["dup_of"] == rep
    assert all(by_name[n]["dup_of"] is None for n in ("truck.jpg", "party.jpg", "receipt.png"))


def test_queue_claims_are_exclusive_and_requeueable(library):
    store, _, _ = library
    first, second = store.claim("embed", "w1"), store.claim("embed", "w2")
    assert first != second and first is not None and second is not None
    store.finish(first, "embed")
    store.finish(second, "embed", "error", "boom")
    assert store.queue_counts()["embed"] == {"pending": 4, "done": 1, "error": 1}
    assert store.requeue("embed") == 1
    assert store.queue_counts()["embed"]["pending"] == 5


def _fake_free_review(store: Store, name_to_album: dict[str, str]):
    """Real reviews rows written through the store API (no model needed for the organizer)."""
    for a in store.assets():
        album = name_to_album.get(Path(a["path"]).name)
        if album:
            store.put_review(a["id"], "fast", "test", {"caption": "x", "categories": [], "objects": [],
                                                       "people_count": 0, "scene": "s",
                                                       "quality": {"score": .9, "blur": False,
                                                                   "underexposed": False, "overexposed": False},
                                                       "document": album == "Receipts", "text_present": False,
                                                       "sensitive": False, "suggested_album": album,
                                                       "confidence": 0.9}, "t", 1)
    store.commit()


def test_plan_approve_apply_never_touches_source_and_is_idempotent(library):
    store, src, tmp = library
    dedup.cluster(store, embed_model=None)
    _fake_free_review(store, {"beach.jpg": "Beach trip", "truck.jpg": "Beach trip",
                              "party.jpg": "Birthday", "receipt.png": "Receipts"})
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in src.iterdir()}
    dest = tmp / "organized"
    out = organize.plan(store, dest, ollama_url="http://127.0.0.1:9/api/generate")  # embedder unreachable → names kept
    assert out["link"] == 4 and out["duplicate"] == 2
    pending = store.proposals("pending")
    assert {p["album"] for p in pending if p["action"] == "link"} == {"Beach trip", "Birthday", "Receipts"}
    assert all(p["dest"] is None for p in pending if p["action"] == "duplicate")

    assert organize.approve(store, everything=True) == 6
    applied = organize.apply(store)
    assert applied == {"applied": 4, "already_present": 0, "duplicates_noted": 2, "failed": 0}
    placed = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    assert len(placed) == 4 and placed[0].startswith("Beach trip/")
    for p in dest.rglob("*.jpg"):
        assert hashlib.sha256(p.read_bytes()).hexdigest() in before.values()
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in src.iterdir()} == before
    assert organize.apply(store) == {"applied": 0, "already_present": 0, "duplicates_noted": 0, "failed": 0}

    # a different file already at the destination is never overwritten
    victim = next(dest.rglob("*_party.jpg"))
    victim.write_bytes(b"not the photo")
    store.execute("UPDATE proposals SET status = 'approved' WHERE action = 'link'")
    store.commit()
    out = organize.apply(store)
    assert out["applied"] == 1 and out["already_present"] == 3
    assert victim.read_bytes() == b"not the photo"
    assert any(p.name.startswith("20") and "_party_" in p.name for p in dest.rglob("*.jpg"))
    assert len(organize.manifest_hash(store)) == 64


def test_plan_prefers_group_albums_over_per_image_review_names(library):
    store, _, tmp = library
    dedup.cluster(store, embed_model=None)
    _fake_free_review(store, {"beach.jpg": "Sea day", "truck.jpg": "Ocean trip", "party.jpg": "Birthday"})
    for a in store.assets(representatives_only=True):
        if Path(a["path"]).name in ("beach.jpg", "truck.jpg"):
            store.put_album(a["id"], "Beach trip", "group", 1)
    store.commit()
    organize.plan(store, tmp / "out", ollama_url="http://127.0.0.1:9/api/generate")
    albums = {Path(p["path"]).name: p["album"] for p in store.proposals("pending") if p["action"] == "link"}
    assert albums == {"beach.jpg": "Beach trip", "truck.jpg": "Beach trip",
                      "party.jpg": "Birthday", "receipt.png": "Unsorted"}
    assert store.counts()["albums"] == 1


def test_cli_help_lists_every_stage():
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "library.py"), "--help"],
                         capture_output=True, text=True, check=True).stdout
    for word in ("scan", "dedup", "embed", "faces", "ocr", "review", "search", "plan", "approve", "apply"):
        assert word in out
