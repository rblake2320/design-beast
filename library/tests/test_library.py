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
                   "edges": {"sha256": 1, "phash": 3, "embedding": 0},
                   "stacks": {"stacks": 0, "members": 0}}
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
    assert applied == {"applied": 4, "moved": 0, "already_present": 0, "duplicates_noted": 2, "failed": 0}
    placed = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file() and ".beast" not in p.parts)
    assert len(placed) == 4 and placed[0].startswith("Beach trip/")
    assert (dest / ".beast" / "manifest.json").exists()
    for p in dest.rglob("*.jpg"):
        assert hashlib.sha256(p.read_bytes()).hexdigest() in before.values()
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in src.iterdir()} == before
    assert organize.apply(store) == {"applied": 0, "moved": 0, "already_present": 0, "duplicates_noted": 0, "failed": 0}

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


def _with_exif(im: Image.Image, path: Path, taken: str, gps: tuple[float, float] | None = None):
    exif = Image.Exif()
    exif[306] = taken                                   # DateTime "YYYY:MM:DD HH:MM:SS"
    if gps:
        ifd = exif.get_ifd(0x8825)
        for tag, ref_tag, val in ((2, 1, gps[0]), (4, 3, gps[1])):
            d = abs(val); m = (d - int(d)) * 60; s = (m - int(m)) * 60
            ifd[tag] = (int(d), int(m), round(s, 2))
            ifd[ref_tag] = ("N" if val >= 0 else "S") if tag == 2 else ("E" if val >= 0 else "W")
    im.save(path, quality=92, exif=exif.tobytes())


def test_burst_stack_keeps_every_frame_and_picks_the_sharpest(tmp_path: Path):
    from PIL import ImageFilter
    src = tmp_path / "src"; src.mkdir()
    base = _photo(tmp_path / "base.jpg", 11)

    def frame(x: int, blur: float) -> Image.Image:        # a subject that moves between shots
        im = base.copy()
        ImageDraw.Draw(im).rectangle([x, 300, x + 350, 900], fill=(250, 250, 250))
        return im.filter(ImageFilter.GaussianBlur(blur)) if blur else im
    _with_exif(frame(100, 0), src / "burst_1.jpg", "2025:06:14 10:00:01")
    _with_exif(frame(220, 3), src / "burst_2.jpg", "2025:06:14 10:00:03")
    _with_exif(frame(340, 6), src / "burst_3.jpg", "2025:06:14 10:00:05")
    _with_exif(_photo(tmp_path / "other.jpg", 12), src / "later.jpg", "2025:06:14 15:00:00")
    store = Store(tmp_path / "lib.db")
    inventory.scan(store, src)
    out = dedup.cluster(store, embed_model=None)
    assert out["duplicates"] == 0, "moving subject must not read as an exact/near duplicate"
    by_name = {Path(a["path"]).name: a for a in store.assets()}
    assert by_name["burst_1.jpg"]["stack_of"] is None
    assert by_name["burst_2.jpg"]["stack_of"] == by_name["burst_1.jpg"]["id"]
    assert by_name["burst_3.jpg"]["stack_of"] == by_name["burst_1.jpg"]["id"]
    assert len(store.assets(representatives_only=True)) == 2
    assert out["stacks"] == {"stacks": 1, "members": 2}
    assert store.queue_counts()["review_fast"] == {"pending": 2, "skipped": 2}
    _fake_free_review(store, {"burst_1.jpg": "Lake day", "later.jpg": "Lake day"})
    organize.plan(store, tmp_path / "out", ollama_url="http://127.0.0.1:9/api/generate")
    dests = {Path(p["path"]).name: p["dest"] for p in store.proposals("pending") if p["action"] == "link"}
    assert len(dests) == 4 and "stack-burst_1" in dests["burst_2.jpg"] and "stack-" not in dests["burst_1.jpg"]


def test_gps_events_become_place_albums_offline(tmp_path: Path):
    from library import events
    src = tmp_path / "src"; src.mkdir()
    asheville, austin = (35.5951, -82.5515), (30.2672, -97.7431)
    for i in range(3):
        _with_exif(_photo(tmp_path / f"a{i}.jpg", 20 + i), src / f"ash_{i}.jpg", f"2025:06:1{i + 1} 12:00:00", asheville)
    for i in range(3):
        _with_exif(_photo(tmp_path / f"b{i}.jpg", 30 + i), src / f"aus_{i}.jpg", f"2025:09:0{i + 1} 12:00:00", austin)
    _with_exif(_photo(tmp_path / "c.jpg", 40), src / "nogps.jpg", "2025:09:02 12:30:00")
    store = Store(tmp_path / "lib.db")
    inventory.scan(store, src)
    out = events.run(store)
    assert out["with_gps"] == 6 and out["placed_by_gps"] == 7      # the no-GPS photo rides along
    titles = {Path(a["path"]).name: a["event_title"] for a in store.assets()}
    assert titles["ash_0.jpg"] == "Asheville, North Carolina - June 2025"
    assert titles["aus_2.jpg"] == "Austin, Texas - September 2025"
    assert titles["nogps.jpg"] == "Austin, Texas - September 2025"     # same time window, no GPS → rides along
    organize.plan(store, tmp_path / "out", people=False, ollama_url="http://127.0.0.1:9/api/generate")
    albums = {p["album"] for p in store.proposals("pending")}
    assert albums == {"Asheville, North Carolina - June 2025", "Austin, Texas - September 2025"}


def test_cli_help_lists_every_stage():
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "library.py"), "--help"],
                         capture_output=True, text=True, check=True).stdout
    for word in ("scan", "dedup", "embed", "faces", "ocr", "review", "search", "plan", "approve", "apply"):
        assert word in out
