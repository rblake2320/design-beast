"""Stage 6: tiered VLM review of cluster representatives via Ollama (local, structured JSON).

fast tier  -> every representative (small vision model, ~1-2 s/image on a 5090)
deep tier  -> low-confidence, document, or sensitive results only (27B model)
Duplicates are never reviewed; the representative's verdict covers its cluster.
Any node with the DSN and an Ollama can run a worker: thumbnails come from the store.
"""
from __future__ import annotations

import base64
import json
import threading
import time
import urllib.request

from .store import Store

SCHEMA = {
    "type": "object",
    "properties": {
        "caption": {"type": "string"},
        "categories": {"type": "array", "items": {"type": "string"}},
        "objects": {"type": "array", "items": {"type": "string"}},
        "people_count": {"type": "integer"},
        "scene": {"type": "string"},
        "quality": {"type": "object", "properties": {
            "score": {"type": "number"}, "blur": {"type": "boolean"},
            "underexposed": {"type": "boolean"}, "overexposed": {"type": "boolean"}},
            "required": ["score", "blur", "underexposed", "overexposed"]},
        "document": {"type": "boolean"},
        "text_present": {"type": "boolean"},
        "sensitive": {"type": "boolean"},
        "suggested_album": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["caption", "categories", "objects", "people_count", "scene", "quality",
                 "document", "text_present", "sensitive", "suggested_album", "confidence"],
}

PROMPT = """You are cataloguing a personal photo library. Look at the image and answer in JSON only.

- caption: one factual sentence, no speculation about identities.
- categories: 1-4 tags from: people, portrait, group, pet, animal, food, vehicle, landscape, city,
  indoors, outdoors, event, travel, sport, art, document, screenshot, receipt, product, meme, other.
- objects: up to 8 concrete nouns visible.
- people_count: number of people visible (0 if none).
- scene: 2-5 words (e.g. "backyard barbecue", "office desk", "mountain trail").
- quality.score: 0-1 for sharpness, exposure and composition; set blur/underexposed/overexposed flags.
- document: true for scanned pages, screenshots, receipts, forms, slides, whiteboards.
- text_present: true if readable text is a major part of the image.
- sensitive: true for IDs, cards, medical, nudity, or private documents.
- suggested_album: a short album name a person would use (e.g. "Beach trip", "Kids sports",
  "Receipts", "Screenshots", "Home renovation"). Prefer specific over generic.
- confidence: 0-1 for how sure you are of the whole answer."""


def _generate(url: str, model: str, prompt: str, image_b64: str, num_predict: int, timeout: int) -> dict:
    body = json.dumps({
        "model": model, "prompt": prompt, "images": [image_b64], "stream": False,
        "format": SCHEMA, "think": False,
        "options": {"temperature": 0.1, "num_predict": num_predict},
    }).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read())
    return json.loads(out["response"] or out.get("thinking", "{}"))


def review_image(jpeg: bytes, model: str, ollama_url: str, num_predict: int = 350,
                 timeout: int = 600) -> dict:
    result = _generate(ollama_url, model, PROMPT, base64.b64encode(jpeg).decode(), num_predict, timeout)
    result["confidence"] = float(max(0.0, min(1.0, result.get("confidence", 0))))
    result["suggested_album"] = str(result.get("suggested_album", "")).strip()[:60]
    return result


def needs_deep(store: Store, asset_id: int, threshold: float) -> bool:
    """Low self-reported confidence or a sensitive flag. Documents are NOT routed here by
    default (in a screenshot-heavy library that would be most of it); use --all."""
    fast = store.review(asset_id, "fast")
    if not fast:
        return True
    return fast["confidence"] < threshold or bool(fast.get("sensitive"))


def run(store_factory, tier: str, model: str, ollama_url: str, worker: str = "local",
        parallel: int = 1, deep_threshold: float = 0.7, deep_all: bool = False,
        limit: int | None = None, progress=None) -> dict:
    stage = f"review_{tier}"
    lock = threading.Lock()
    stats = {"done": 0, "skipped": 0, "failed": 0, "ms_total": 0}

    def loop(slot: int):
        store = store_factory()
        name = f"{worker}#{slot}"
        try:
            while True:
                with lock:
                    if limit is not None and stats["done"] + stats["failed"] >= limit:
                        return
                aid = store.claim(stage, name)
                if aid is None:
                    return
                asset = store.asset(aid)
                if asset is None or asset["dup_of"] is not None:
                    store.skip(aid, stage, "duplicate of representative")
                    with lock:
                        stats["skipped"] += 1
                    continue
                if tier == "deep" and not deep_all and not needs_deep(store, aid, deep_threshold):
                    store.skip(aid, stage, "fast review confident")
                    with lock:
                        stats["skipped"] += 1
                    continue
                thumb = store.get_thumb(aid)
                if not thumb:
                    store.skip(aid, stage, "no thumbnail")
                    with lock:
                        stats["skipped"] += 1
                    continue
                t0 = time.time()
                try:
                    result = review_image(thumb, model, ollama_url)
                    ms = int((time.time() - t0) * 1000)
                    with store.tx():
                        store.put_review(aid, tier, model, result, name, ms)
                    store.finish(aid, stage)
                    with lock:
                        stats["done"] += 1; stats["ms_total"] += ms
                        if progress:
                            progress(stats, asset["path"], result)
                except Exception as exc:  # noqa: BLE001
                    store.finish(aid, stage, "error", f"{type(exc).__name__}: {exc}"[:300])
                    with lock:
                        stats["failed"] += 1
        finally:
            store.close()

    threads = [threading.Thread(target=loop, args=(i,), daemon=True) for i in range(max(1, parallel))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    summary = {"tier": tier, "model": model, **stats,
               "avg_ms": int(stats["ms_total"] / stats["done"]) if stats["done"] else None}
    store = store_factory()
    store.log(f"review_{tier}", summary)
    store.commit(); store.close()
    return summary
