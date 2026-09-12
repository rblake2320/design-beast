"""Stage 3: SigLIP2 image/text embeddings — the high-volume indexer (GPU, batched)."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

from .store import Store

DEFAULT_MODEL = "google/siglip2-so400m-patch14-384"
_cache: dict = {}


def load(model_name: str = DEFAULT_MODEL):
    if model_name in _cache:
        return _cache[model_name]
    import torch
    from transformers import AutoModel, AutoProcessor
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    model = AutoModel.from_pretrained(model_name, torch_dtype=dtype).to(device).eval()
    processor = AutoProcessor.from_pretrained(model_name)
    _cache[model_name] = (model, processor, device)
    return _cache[model_name]


def embed_images(images: list[Image.Image], model_name: str = DEFAULT_MODEL) -> np.ndarray:
    import torch
    model, processor, device = load(model_name)
    inputs = processor(images=[im.convert("RGB") for im in images], return_tensors="pt").to(device)
    inputs["pixel_values"] = inputs["pixel_values"].to(model.dtype)
    with torch.inference_mode():
        feats = model.get_image_features(**inputs)
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.float().cpu().numpy().astype(np.float32)


def embed_texts(texts: list[str], model_name: str = DEFAULT_MODEL) -> np.ndarray:
    import torch
    model, processor, device = load(model_name)
    inputs = processor(text=texts, padding="max_length", max_length=64, truncation=True,
                       return_tensors="pt").to(device)
    with torch.inference_mode():
        feats = model.get_text_features(**inputs)
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.float().cpu().numpy().astype(np.float32)


def run(store: Store, model_name: str = DEFAULT_MODEL, batch_size: int = 32, worker: str = "local",
        limit: int | None = None) -> dict:
    done = failed = 0
    batch: list[tuple[int, Image.Image]] = []

    def flush():
        nonlocal done, failed
        if not batch:
            return
        try:
            vecs = embed_images([im for _, im in batch], model_name)
            with store.tx():
                for (aid, _), vec in zip(batch, vecs):
                    store.put_embedding(aid, model_name, vec)
            for aid, _ in batch:
                store.finish(aid, "embed")
            done += len(batch)
        except Exception as exc:  # noqa: BLE001 — record, keep going
            for aid, _ in batch:
                store.finish(aid, "embed", "error", f"{type(exc).__name__}: {exc}"[:300])
            failed += len(batch)
        batch.clear()

    while limit is None or done + failed < limit:
        aid = store.claim("embed", worker)
        if aid is None:
            break
        thumb = store.get_thumb(aid)
        if not thumb:
            store.skip(aid, "embed", "no thumbnail"); continue
        batch.append((aid, Image.open(io.BytesIO(thumb))))
        if len(batch) >= batch_size:
            flush()
    flush()
    store.log("embed", {"model": model_name, "done": done, "failed": failed})
    store.commit()
    return {"model": model_name, "done": done, "failed": failed}
