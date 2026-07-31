"""Optional OpenCLIP + Faiss semantic frame index for Beast Watch bundles."""
from __future__ import annotations

import json
from pathlib import Path


class VisualIndexError(RuntimeError):
    pass


def _deps():
    try:
        import faiss
        import numpy as np
        import open_clip
        import torch
        from PIL import Image
        return faiss, np, open_clip, torch, Image
    except ImportError as exc:
        raise VisualIndexError(
            "visual search needs open_clip_torch, faiss-cpu/faiss-gpu, torch, numpy, Pillow"
        ) from exc


def build(bundle: Path, model_name: str = "ViT-B-32",
          pretrained: str = "laion2b_s34b_b79k", batch_size: int = 32) -> dict:
    faiss, np, open_clip, torch, Image = _deps()
    timeline_path = bundle / "timeline.json"
    if not timeline_path.exists():
        raise VisualIndexError(f"timeline not found: {timeline_path}")
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    rows = [row for row in timeline.get("frames", []) if not row.get("near_duplicate")]
    if not rows:
        raise VisualIndexError("timeline has no indexable frames")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(
        model_name, pretrained=pretrained, device=device)
    model.eval()
    vectors = []
    for offset in range(0, len(rows), batch_size):
        batch_rows = rows[offset:offset + batch_size]
        tensors = []
        for row in batch_rows:
            with Image.open(bundle / row["file"]) as image:
                tensors.append(preprocess(image.convert("RGB")))
        images = torch.stack(tensors).to(device)
        with torch.inference_mode(), torch.autocast(
                device_type=device, enabled=device == "cuda"):
            encoded = model.encode_image(images)
            encoded /= encoded.norm(dim=-1, keepdim=True)
        vectors.append(encoded.float().cpu().numpy())
    matrix = np.ascontiguousarray(np.concatenate(vectors).astype("float32"))
    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)
    faiss.write_index(index, str(bundle / "frames.faiss"))
    np.save(bundle / "frames.embeddings.npy", matrix)
    metadata = {
        "schema": "beast.watch.visual-index/v1", "model": model_name,
        "pretrained": pretrained, "device": device, "dimension": matrix.shape[1],
        "count": len(rows), "frames": [{"id": row["id"], "file": row["file"],
                                         "source_seconds": row["source_seconds"],
                                         "source_time": row["source_time"]}
                                        for row in rows],
    }
    (bundle / "visual-index.json").write_text(json.dumps(metadata, indent=2),
                                               encoding="utf-8")
    return metadata


def search(bundle: Path, query: str, limit: int = 12) -> list[dict]:
    faiss, np, open_clip, torch, _ = _deps()
    meta_path = bundle / "visual-index.json"
    if not meta_path.exists():
        raise VisualIndexError("visual index missing; run beast watch-index BUNDLE first")
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, _ = open_clip.create_model_and_transforms(
        metadata["model"], pretrained=metadata["pretrained"], device=device)
    tokenizer = open_clip.get_tokenizer(metadata["model"])
    model.eval()
    tokens = tokenizer([query]).to(device)
    with torch.inference_mode():
        vector = model.encode_text(tokens)
        vector /= vector.norm(dim=-1, keepdim=True)
    index = faiss.read_index(str(bundle / "frames.faiss"))
    scores, indexes = index.search(
        np.ascontiguousarray(vector.float().cpu().numpy().astype("float32")),
        min(limit, index.ntotal))
    return [{**metadata["frames"][int(position)], "score": round(float(score), 4)}
            for score, position in zip(scores[0], indexes[0]) if position >= 0]
