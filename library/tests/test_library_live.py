"""Live tests: real SigLIP2, InsightFace, easyocr and Ollama. Run intentionally:

    pytest -m live_gpu library/tests/test_library_live.py

Each test states the real service it needs and skips (visibly) when that service is absent —
never a mock. BEAST_LIBRARY_FACE_IMAGE=<jpg with >=1 face> enables the face test.
"""
from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "studio"))

import config  # noqa: E402
from library import dedup, embed, faces, inventory, ocr, organize, review, search  # noqa: E402
from library.store import Store  # noqa: E402

pytestmark = pytest.mark.live_gpu


def _ollama_up() -> bool:
    try:
        urllib.request.urlopen(config.get("ollama_url").replace("/api/generate", "/api/tags"), timeout=3)
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture
def library(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    sky = Image.new("RGB", (1200, 800), (90, 150, 230))
    ImageDraw.Draw(sky).ellipse([900, 80, 1080, 260], fill=(255, 240, 120))
    sky.save(src / "blue_sky_sun.jpg", quality=90)
    doc = Image.new("RGB", (1240, 1754), "white")
    d = ImageDraw.Draw(doc)
    for i in range(20):
        d.text((80, 80 + i * 60), f"INVOICE line {i}  total ${13 * i}.00  due 2026-09-30", fill="black")
    doc.save(src / "invoice.png")
    store = Store(tmp_path / "lib.db")
    inventory.scan(store, src)
    return store, src


def test_siglip2_embeds_and_text_search_ranks_the_right_image(library):
    store, _ = library
    out = embed.run(store, config.get("library_embed_model"))
    assert out["done"] == 2 and out["failed"] == 0
    ids, mat = store.embeddings(config.get("library_embed_model"))
    assert mat.shape == (2, 1152)
    top = search.search(store, query="a printed invoice with lines of text", k=1)[0]
    assert top["path"].endswith("invoice.png")
    top = search.search(store, query="blue sky with the sun", k=1)[0]
    assert top["path"].endswith("blue_sky_sun.jpg")
    assert dedup.cluster(store, embed_model=config.get("library_embed_model"))["clusters"] == 2


def test_ollama_fast_review_flags_document_and_ocr_reads_it(library):
    if not _ollama_up():
        pytest.skip("Ollama is not listening — start `ollama serve`")
    store, _ = library
    db = store.con  # noqa: F841 — keep the fixture connection alive for the worker threads below
    path = store.fetchone("PRAGMA database_list")[2]
    out = review.run(lambda: Store(path), "fast", config.get("library_fast_model"),
                     config.get("ollama_url"), parallel=2)
    assert out["done"] == 2 and out["failed"] == 0
    invoice = next(a for a in store.assets() if a["path"].endswith("invoice.png"))
    verdict = store.review(invoice["id"], "fast")
    assert verdict["document"] is True and 0 <= verdict["confidence"] <= 1
    out = ocr.run(Store(path))
    assert out["done"] == 1 and out["skipped"] == 1        # only the document was OCR'd
    text = Store(path).fetchone("SELECT text FROM ocr WHERE asset_id = ?", (invoice["id"],))[0]
    assert "INVOICE" in text.upper() and "2026" in text


def test_album_consolidation_merges_synonyms_only():
    if not _ollama_up():
        pytest.skip("Ollama is not listening — start `ollama serve`")
    vecs = organize._text_embeddings(["Beach trip", "Beach vacation", "Invoice Records", "Receipts"],
                                     config.get("ollama_url"))
    sims = vecs @ vecs.T
    assert sims[0, 1] >= organize.ALBUM_MERGE_COSINE          # synonyms merge
    assert sims[0, 2] < organize.ALBUM_MERGE_COSINE           # unrelated albums stay apart
    assert sims[2, 3] < organize.ALBUM_MERGE_COSINE           # "close but different" stays apart


def test_insightface_groups_the_same_face(tmp_path: Path):
    src_img = os.environ.get("BEAST_LIBRARY_FACE_IMAGE")
    if not src_img or not Path(src_img).exists():
        pytest.skip("set BEAST_LIBRARY_FACE_IMAGE to a photo with a face")
    src = tmp_path / "src"
    src.mkdir()
    with Image.open(src_img) as im:
        im.convert("RGB").save(src / "a.jpg", quality=92)
        im.convert("RGB").resize((im.width * 3 // 4, im.height * 3 // 4)).save(src / "b.jpg", quality=85)
    store = Store(tmp_path / "lib.db")
    inventory.scan(store, src)
    out = faces.run(store)
    assert out["faces"] >= 2 and out["persons"] >= 1
    people = [store.people_in(a["id"]) for a in store.assets()]
    assert people[0] and people[0] == people[1]              # same person across both sizes
