"""Stage 4: InsightFace detection + embedding + incremental person grouping (local only)."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

from .store import Store

MODEL_PACK = "buffalo_l"
SAME_PERSON_COSINE = 0.55   # buffalo_l normed embeddings; 0.5-0.6 is the usual band
MIN_DET_SCORE = 0.6
MIN_FACE_PX = 40
_app = None


def load():
    global _app
    if _app is None:
        from insightface.app import FaceAnalysis
        _app = FaceAnalysis(name=MODEL_PACK, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        _app.prepare(ctx_id=0, det_size=(640, 640))
    return _app


def detect(image: Image.Image) -> list[dict]:
    app = load()
    bgr = np.asarray(image.convert("RGB"))[:, :, ::-1]
    out = []
    for f in app.get(bgr):
        x1, y1, x2, y2 = f.bbox
        if f.det_score < MIN_DET_SCORE or min(x2 - x1, y2 - y1) < MIN_FACE_PX:
            continue
        out.append({"bbox": [float(x1), float(y1), float(x2), float(y2)],
                    "score": float(f.det_score),
                    "vec": np.asarray(f.normed_embedding, dtype=np.float32)})
    return out


def assign_person(store: Store, vec: np.ndarray, persons: list) -> int:
    """Greedy nearest-centroid grouping; centroids move with each new face."""
    best, best_sim = None, SAME_PERSON_COSINE
    for i, (pid, _, centroid, n) in enumerate(persons):
        sim = float(vec @ centroid / (np.linalg.norm(centroid) + 1e-9))
        if sim >= best_sim:
            best, best_sim = i, sim
    if best is None:
        pid = store.new_person(vec)
        persons.append((pid, None, vec.copy(), 1))
        return pid
    pid, label, centroid, n = persons[best]
    centroid = (centroid * n + vec) / (n + 1)
    persons[best] = (pid, label, centroid, n + 1)
    store.update_person(pid, centroid, n + 1)
    return pid


def run(store: Store, worker: str = "local", limit: int | None = None) -> dict:
    persons = store.persons()
    done = failed = faces = 0
    while limit is None or done + failed < limit:
        aid = store.claim("faces", worker)
        if aid is None:
            break
        thumb = store.get_thumb(aid)
        if not thumb:
            store.skip(aid, "faces", "no thumbnail"); continue
        try:
            found = detect(Image.open(io.BytesIO(thumb)))
            with store.tx():
                store.execute("DELETE FROM faces WHERE asset_id = ?", (aid,))
                for f in found:
                    pid = assign_person(store, f["vec"], persons)
                    store.put_face(aid, f["bbox"], f["score"], f["vec"], pid)
            faces += len(found)
            store.finish(aid, "faces")
            done += 1
        except Exception as exc:  # noqa: BLE001
            store.finish(aid, "faces", "error", f"{type(exc).__name__}: {exc}"[:300])
            failed += 1
    summary = {"images": done, "failed": failed, "faces": faces, "persons": len(persons)}
    store.log("faces", summary)
    store.commit()
    return summary
