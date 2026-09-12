"""Stage 5: OCR for documents, screenshots and receipts (easyocr, GPU when available)."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

from .store import Store

ENGINE = "easyocr"
_reader = None


def load(langs=("en",)):
    global _reader
    if _reader is None:
        import easyocr
        import torch
        _reader = easyocr.Reader(list(langs), gpu=torch.cuda.is_available(), verbose=False)
    return _reader


def read(image: Image.Image) -> tuple[str, float]:
    reader = load()
    results = reader.readtext(np.asarray(image.convert("RGB")), paragraph=False)
    if not results:
        return "", 0.0
    text = "\n".join(str(r[1]) for r in results)
    conf = float(np.mean([float(r[2]) for r in results]))
    return text, conf


def is_document(store: Store, asset_id: int) -> bool:
    review = store.review(asset_id)
    return bool(review and (review.get("document") or "document" in review.get("categories", [])
                            or "screenshot" in review.get("categories", [])))


def run(store: Store, worker: str = "local", documents_only: bool = True,
        limit: int | None = None) -> dict:
    done = skipped = failed = 0
    while limit is None or done + failed + skipped < limit:
        aid = store.claim("ocr", worker)
        if aid is None:
            break
        if documents_only and not is_document(store, aid):
            store.skip(aid, "ocr", "not a document"); skipped += 1; continue
        source = store.asset(aid)
        try:
            image = None
            if source and source["path"]:
                try:
                    image = Image.open(source["path"])   # full resolution when reachable
                    image.load()
                except OSError:
                    image = None
            if image is None:
                thumb = store.get_thumb(aid)
                if not thumb:
                    store.skip(aid, "ocr", "no image"); skipped += 1; continue
                image = Image.open(io.BytesIO(thumb))
            text, conf = read(image)
            with store.tx():
                store.put_ocr(aid, text, conf, ENGINE)
            store.finish(aid, "ocr")
            done += 1
        except Exception as exc:  # noqa: BLE001
            store.finish(aid, "ocr", "error", f"{type(exc).__name__}: {exc}"[:300])
            failed += 1
    summary = {"done": done, "skipped": skipped, "failed": failed}
    store.log("ocr", summary)
    store.commit()
    return summary
