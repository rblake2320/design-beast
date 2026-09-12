"""Stage 4: people — detect, embed, and group faces the way a phone does.

How phones make it feel instant and right:
  * every face is embedded once at ingest (InsightFace buffalo_l, 512-d), matching is
    then just dot products against a small set of EXEMPLARS per person — not a centroid
    that drifts, and not a re-run of the model;
  * two thresholds: a strong match is assigned automatically, a weak one is only a
    suggestion until you confirm it;
  * poor faces (tiny, blurry, turned away) never seed a person — they are matched later;
  * naming a person is a query: "find everyone like these exemplars" runs over the whole
    library immediately, and every later scan matches new faces against named people first;
  * corrections stick: a rejected match is remembered, a confirmed face becomes an exemplar.
"""
from __future__ import annotations

import io
import math

import numpy as np
from PIL import Image

from .store import Store

MODEL_PACK = "buffalo_l"
MIN_DET_SCORE = 0.6
MIN_FACE_PX = 40
STRONG = 0.55          # buffalo_l cosine: same person is usually >= 0.5, different < 0.35
WEAK = 0.42            # suggestion band — shown, never trusted without confirmation
SEED_QUALITY = 0.35    # a new person needs at least this face quality to be created
EXEMPLAR_MAX = 12
EXEMPLAR_DIVERSITY = 0.85   # only keep an exemplar that adds something new
_app = None


def load():
    global _app
    if _app is None:
        from insightface.app import FaceAnalysis
        _app = FaceAnalysis(name=MODEL_PACK, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        _app.prepare(ctx_id=0, det_size=(640, 640))
    return _app


def _quality(f, width: float, height: float) -> float:
    """0..1: detector confidence x size x frontal-ness (yaw from InsightFace pose)."""
    size = min(width, height)
    frontal = 1.0
    pose = getattr(f, "pose", None)
    if pose is not None and len(pose) >= 2:
        frontal = max(0.0, math.cos(math.radians(float(pose[1]))))   # yaw
    return float(f.det_score) * min(1.0, size / 120.0) * (0.5 + 0.5 * frontal)


def detect(image: Image.Image) -> list[dict]:
    app = load()
    bgr = np.asarray(image.convert("RGB"))[:, :, ::-1]
    out = []
    for f in app.get(bgr):
        x1, y1, x2, y2 = f.bbox
        if f.det_score < MIN_DET_SCORE or min(x2 - x1, y2 - y1) < MIN_FACE_PX:
            continue
        out.append({"bbox": [float(x1), float(y1), float(x2), float(y2)], "score": float(f.det_score),
                    "quality": _quality(f, x2 - x1, y2 - y1),
                    "vec": np.asarray(f.normed_embedding, dtype=np.float32)})
    return out


class Matcher:
    """In-memory exemplar index: person_id -> matrix of exemplar vectors."""

    def __init__(self, store: Store):
        self.store = store
        self.ex: dict[int, list[tuple[int, np.ndarray]]] = store.exemplars()
        self.labels = {pid: label for pid, label, _, _ in store.persons()}
        self.rejects = store.rejects()

    def best(self, vec: np.ndarray, face_id: int | None = None, only: set[int] | None = None) -> tuple[int | None, float]:
        best_pid, best_sim = None, 0.0
        for pid, items in self.ex.items():
            if only is not None and pid not in only:
                continue
            if face_id is not None and (face_id, pid) in self.rejects:
                continue
            sims = np.stack([v for _, v in items]) @ vec
            s = float(sims.max())
            # named people win ties in the strong band: a known face beats an anonymous cluster
            if s > best_sim or (abs(s - best_sim) < 0.02 and self.labels.get(pid) and not self.labels.get(best_pid)):
                best_pid, best_sim = pid, s
        return best_pid, best_sim

    def add_exemplar(self, pid: int, face_id: int, vec: np.ndarray, quality: float) -> bool:
        items = self.ex.setdefault(pid, [])
        if quality < SEED_QUALITY or len(items) >= EXEMPLAR_MAX:
            return False
        if items and float((np.stack([v for _, v in items]) @ vec).max()) >= EXEMPLAR_DIVERSITY:
            return False
        items.append((face_id, vec))
        self.store.add_exemplar(pid, face_id, vec)
        return True

    def new_person(self, face_id: int, vec: np.ndarray) -> int:
        pid = self.store.new_person(vec)
        self.ex[pid] = [(face_id, vec)]
        self.store.add_exemplar(pid, face_id, vec)
        self.labels[pid] = None
        return pid


def assign(store: Store, m: Matcher, face_id: int, vec: np.ndarray, quality: float) -> tuple[int | None, float, int]:
    """Returns (person_id, similarity, confirmed) and records it."""
    pid, sim = m.best(vec, face_id)
    if pid is not None and sim >= STRONG:
        store.set_face_person(face_id, pid, sim, 1)
        m.add_exemplar(pid, face_id, vec, quality)
        return pid, sim, 1
    if pid is not None and sim >= WEAK:
        store.set_face_person(face_id, pid, sim, 0)      # suggestion only
        return pid, sim, 0
    if quality >= SEED_QUALITY:
        pid = m.new_person(face_id, vec)
        store.set_face_person(face_id, pid, 1.0, 1)
        return pid, 1.0, 1
    store.set_face_person(face_id, None, None, 0)
    return None, 0.0, 0


def run(store: Store, worker: str = "local", limit: int | None = None) -> dict:
    store.reclaim_stale("faces")
    m = Matcher(store)
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
                for f in sorted(found, key=lambda f: -f["quality"]):
                    fid = store.put_face(aid, f["bbox"], f["score"], f["vec"], None)
                    assign(store, m, fid, f["vec"], f["quality"])
            faces += len(found)
            store.finish(aid, "faces")
            done += 1
        except Exception as exc:  # noqa: BLE001
            store.finish(aid, "faces", "error", f"{type(exc).__name__}: {exc}"[:300])
            failed += 1
    _refresh_counts(store)
    summary = {"images": done, "failed": failed, "faces": faces, "persons": len(m.ex)}
    store.log("faces", summary)
    store.commit()
    return summary


def _refresh_counts(store: Store) -> None:
    for pid, _, _, _ in store.persons():
        n = store.fetchone("SELECT COUNT(*) FROM faces WHERE person_id = ?", (pid,))[0]
        store.execute("UPDATE persons SET n = ? WHERE id = ?", (int(n), pid))


# ---- the parts a person touches ------------------------------------------------------

def label(store: Store, person_id: int, name: str) -> dict:
    """Name a person, then immediately look for them across the whole library."""
    store.label_person(person_id, name)
    store.commit()
    return find(store, person_id)


def find(store: Store, person_id: int) -> dict:
    """Re-match every face that is not user-confirmed against this person's exemplars.
    Strong matches move to the person (even from an anonymous cluster); weak ones become suggestions."""
    m = Matcher(store)
    if person_id not in m.ex:
        return {"person": person_id, "error": "no exemplars"}
    moved = suggested = 0
    with store.tx():
        for f in store.faces():
            if f["confirmed"] == 2 or f["person_id"] == person_id or (f["id"], person_id) in m.rejects:
                continue
            sim = float((np.stack([v for _, v in m.ex[person_id]]) @ f["vec"]).max())
            current = f["similarity"] or 0.0
            if sim >= STRONG and (f["person_id"] is None or not m.labels.get(f["person_id"]) or sim > current):
                store.set_face_person(f["id"], person_id, sim, 1); moved += 1
            elif sim >= WEAK and f["person_id"] is None:
                store.set_face_person(f["id"], person_id, sim, 0); suggested += 1
        _refresh_counts(store)
    _drop_empty_anonymous(store)
    out = {"person": person_id, "label": m.labels.get(person_id), "moved": moved, "suggested": suggested,
           "total": int(store.fetchone("SELECT COUNT(*) FROM faces WHERE person_id = ?", (person_id,))[0])}
    store.log("people.find", out)
    store.commit()
    return out


def confirm(store: Store, face_id: int, person_id: int) -> dict:
    f = next((x for x in store.faces() if x["id"] == face_id), None)
    if not f:
        return {"error": f"no face {face_id}"}
    m = Matcher(store)
    with store.tx():
        store.set_face_person(face_id, person_id, 1.0, 2)
        if person_id not in m.ex:
            m.ex[person_id] = []
        m.add_exemplar(person_id, face_id, f["vec"], 1.0)
        _refresh_counts(store)
    store.commit()
    return find(store, person_id)


def reject(store: Store, face_id: int, person_id: int) -> dict:
    """'That is not her': remember it, unassign, and re-match the face elsewhere."""
    f = next((x for x in store.faces() if x["id"] == face_id), None)
    if not f:
        return {"error": f"no face {face_id}"}
    with store.tx():
        store.reject_face(face_id, person_id)
        store.execute("DELETE FROM exemplars WHERE face_id = ? AND person_id = ?", (face_id, person_id))
        store.set_face_person(face_id, None, None, 0)
    m = Matcher(store)
    with store.tx():
        pid, sim, conf = assign(store, m, face_id, f["vec"], 0.0)   # quality 0: never seeds a new person
        _refresh_counts(store)
    store.commit()
    return {"face": face_id, "rejected": person_id, "now": pid, "similarity": round(sim, 3)}


def merge(store: Store, keep: int, drop: int) -> dict:
    with store.tx():
        store.execute("UPDATE faces SET person_id = ? WHERE person_id = ?", (keep, drop))
        store.execute("UPDATE exemplars SET person_id = ? WHERE person_id = ?", (keep, drop))
        store.execute("DELETE FROM exemplars WHERE person_id = ? AND id NOT IN ("
                      "SELECT id FROM exemplars WHERE person_id = ? ORDER BY id LIMIT ?)", (keep, keep, EXEMPLAR_MAX))
        store.execute("DELETE FROM persons WHERE id = ?", (drop,))
        _refresh_counts(store)
    store.commit()
    return {"kept": keep, "dropped": drop,
            "faces": int(store.fetchone("SELECT COUNT(*) FROM faces WHERE person_id = ?", (keep,))[0])}


def recluster(store: Store) -> dict:
    """Rebuild the anonymous people from scratch (named people are fixed anchors)."""
    named = {pid for pid, lbl, _, _ in store.persons() if lbl}
    with store.tx():
        for pid, lbl, _, _ in store.persons():
            if pid not in named:
                store.execute("UPDATE faces SET person_id = NULL, similarity = NULL, confirmed = 0 "
                              "WHERE person_id = ? AND confirmed < 2", (pid,))
                store.delete_person(pid)
    m = Matcher(store)
    faces = store.faces(unassigned=True)
    # highest-quality first so clusters are seeded by good faces, like a phone's "key face"
    quality = {f["id"]: float(f["score"] or 0) for f in faces}
    with store.tx():
        for f in sorted(faces, key=lambda f: -quality[f["id"]]):
            assign(store, m, f["id"], f["vec"], quality[f["id"]])
        _refresh_counts(store)
    _drop_empty_anonymous(store)
    store.commit()
    return {"named": len(named), "persons": len(store.persons()), "faces": len(store.faces())}


def _drop_empty_anonymous(store: Store) -> None:
    for pid, lbl, _, n in store.persons():
        if not lbl and int(store.fetchone("SELECT COUNT(*) FROM faces WHERE person_id = ?", (pid,))[0]) == 0:
            store.delete_person(pid)


MERGE_SUGGEST = 0.38   # below WEAK: only ever a question to a person, never automatic


def suggest_merges(store: Store, limit: int = 20) -> list[dict]:
    """Pairs of people whose exemplars come close: 'same person?' prompts, like a phone's."""
    ex = store.exemplars()
    labels = {pid: lbl for pid, lbl, _, _ in store.persons()}
    pids = sorted(ex)
    out = []
    for i, a in enumerate(pids):
        ma = np.stack([v for _, v in ex[a]])
        for b in pids[i + 1:]:
            if labels.get(a) and labels.get(b):
                continue                     # two named people are two people
            sim = float((ma @ np.stack([v for _, v in ex[b]]).T).max())
            if sim >= MERGE_SUGGEST:
                out.append({"a": a, "b": b, "similarity": round(sim, 3),
                            "a_label": labels.get(a), "b_label": labels.get(b)})
    return sorted(out, key=lambda r: -r["similarity"])[:limit]


def people(store: Store) -> list[dict]:
    out = []
    for pid, lbl, _, n in store.persons():
        row = store.fetchone("SELECT COUNT(*), SUM(CASE WHEN confirmed = 0 THEN 1 ELSE 0 END) "
                             "FROM faces WHERE person_id = ?", (pid,))
        out.append({"id": pid, "label": lbl, "faces": int(row[0] or 0), "suggested": int(row[1] or 0),
                    "images": int(store.fetchone("SELECT COUNT(DISTINCT asset_id) FROM faces WHERE person_id = ?",
                                                 (pid,))[0])})
    return sorted(out, key=lambda p: (-bool(p["label"]), -p["faces"]))
