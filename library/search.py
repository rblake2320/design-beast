"""Stage 8: search — natural language, similar-image, people, dates, and OCR/caption text."""
from __future__ import annotations

import io

from PIL import Image

from . import embed
from .store import Store


def _passes(store: Store, asset: dict, person: int | None, date_from: str | None,
            date_to: str | None, album: str | None) -> bool:
    if person is not None and person not in store.people_in(asset["id"]):
        return False
    taken = asset.get("taken_at") or ""
    if date_from and taken < date_from:
        return False
    if date_to and taken[:len(date_to)] > date_to:
        return False
    if album:
        review = store.review(asset["id"]) or {}
        if album.lower() not in review.get("suggested_album", "").lower():
            return False
    return True


def search(store: Store, query: str | None = None, like: str | None = None, text: str | None = None,
           k: int = 20, model: str = embed.DEFAULT_MODEL, person: int | None = None,
           date_from: str | None = None, date_to: str | None = None, album: str | None = None) -> list[dict]:
    scored: list[tuple[int, float]]
    if query:
        vec = embed.embed_texts([query], model)[0]
        scored = store.nearest(model, vec, k * 5)
    elif like:
        with Image.open(like) as im:
            vec = embed.embed_images([im], model)[0]
        scored = store.nearest(model, vec, k * 5 + 1)
    else:
        scored = [(a["id"], 0.0) for a in store.assets(representatives_only=True)]

    if text:
        needle = f"%{text.lower()}%"
        hits = {r[0] for r in store.fetchall(
            "SELECT asset_id FROM ocr WHERE LOWER(text) LIKE ? UNION "
            "SELECT asset_id FROM reviews WHERE LOWER(result) LIKE ?", (needle, needle))}
        scored = [(aid, s) for aid, s in scored if aid in hits]

    assigned = store.albums()
    out = []
    for aid, score in scored:
        asset = store.asset(aid)
        if not asset or asset["dup_of"] is not None:
            continue
        if not _passes(store, asset, person, date_from, date_to, album):
            continue
        review = store.review(aid) or {}
        out.append({"id": aid, "score": round(score, 4), "path": asset["path"],
                    "taken_at": asset["taken_at"], "caption": review.get("caption"),
                    "album": assigned[aid][0] if aid in assigned else review.get("suggested_album"),
                    "people": store.people_in(aid)})
        if len(out) >= k:
            break
    return out


def thumbnail(store: Store, asset_id: int) -> Image.Image | None:
    raw = store.get_thumb(asset_id)
    return Image.open(io.BytesIO(raw)) if raw else None
