"""Beast Studio — Library tab API (search, thumbnails, people naming, approvals, apply, recover).

Mounted by server.py; one Store connection per request (SQLite is fine with that, and it keeps
the worker queue semantics identical to the CLI).
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import config  # noqa: E402
from library import faces, organize, recover, search  # noqa: E402
from library.store import Store  # noqa: E402

router = APIRouter(prefix="/api/library", tags=["library"])
HERE = Path(__file__).resolve().parent


def _store() -> Store:
    return Store(config.get("library_dsn") or config.get("library_db"))


def _person(store: Store, ref: str) -> int:
    return int(ref) if str(ref).isdigit() else (store.person_by_label(ref) or -1)


@router.get("/status")
def status():
    s = _store()
    try:
        return {"store": "postgres" if s.pg else "sqlite", "counts": s.counts(), "queue": s.queue_counts(),
                "albums": {a: n for a, n in s.fetchall(
                    "SELECT album, COUNT(*) FROM albums GROUP BY album ORDER BY 2 DESC")}}
    finally:
        s.close()


@router.get("/search")
def do_search(q: str | None = None, text: str | None = None, person: str | None = None,
              album: str | None = None, date_from: str | None = None, date_to: str | None = None,
              k: int = Query(40, le=200)):
    s = _store()
    try:
        pid = _person(s, person) if person else None
        rows = search.search(s, query=q or None, text=text or None, k=k, model=config.get("library_embed_model"),
                             person=pid, date_from=date_from, date_to=date_to, album=album)
        return {"results": rows}
    finally:
        s.close()


@router.get("/thumb/{asset_id}")
def thumb(asset_id: int):
    s = _store()
    try:
        raw = s.get_thumb(asset_id)
    finally:
        s.close()
    if not raw:
        return Response(status_code=404)
    return Response(content=raw, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@router.get("/face/{face_id}")
def face_crop(face_id: int, pad: float = 0.35):
    """A square crop around one face from the stored thumbnail — the 'key face' a phone shows."""
    import io
    from PIL import Image
    s = _store()
    try:
        f = next((x for x in s.faces() if x["id"] == face_id), None)
        raw = s.get_thumb(f["asset_id"]) if f else None
    finally:
        s.close()
    if not raw:
        return Response(status_code=404)
    im = Image.open(io.BytesIO(raw))
    x1, y1, x2, y2 = f["bbox"]
    side = max(x2 - x1, y2 - y1) * (1 + 2 * pad)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    box = (max(0, cx - side / 2), max(0, cy - side / 2), min(im.width, cx + side / 2), min(im.height, cy + side / 2))
    out = io.BytesIO()
    im.crop(tuple(int(v) for v in box)).resize((192, 192)).save(out, "JPEG", quality=85)
    return Response(content=out.getvalue(), media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@router.get("/people")
def people():
    s = _store()
    try:
        out = faces.people(s)
        for p in out:                      # a key face to show: the first exemplar (best-quality seed)
            row = s.fetchone("SELECT face_id FROM exemplars WHERE person_id = ? ORDER BY id LIMIT 1", (p["id"],))
            p["key_face"] = int(row[0]) if row else None
        return {"people": out}
    finally:
        s.close()


@router.get("/people/merges")
def merges():
    s = _store()
    try:
        out = faces.suggest_merges(s)
        for m in out:
            for side in ("a", "b"):
                row = s.fetchone("SELECT face_id FROM exemplars WHERE person_id = ? ORDER BY id LIMIT 1", (m[side],))
                m[side + "_face"] = int(row[0]) if row else None
        return {"merges": out}
    finally:
        s.close()


@router.get("/people/{ref}/faces")
def person_faces(ref: str):
    s = _store()
    try:
        pid = _person(s, ref)
        out = []
        for f in s.faces(person_id=pid):
            a = s.asset(f["asset_id"])
            out.append({"face": f["id"], "asset": f["asset_id"], "bbox": f["bbox"], "confirmed": f["confirmed"],
                        "similarity": f["similarity"], "path": a["path"] if a else None})
        return {"person": pid, "faces": out}
    finally:
        s.close()


class Name(BaseModel):
    name: str


@router.post("/people/{ref}/label")
def label(ref: str, body: Name):
    s = _store()
    try:
        return faces.label(s, _person(s, ref), body.name.strip()[:60])
    finally:
        s.close()


@router.post("/people/{ref}/find")
def find(ref: str):
    s = _store()
    try:
        return faces.find(s, _person(s, ref))
    finally:
        s.close()


class FaceDecision(BaseModel):
    person: str


@router.post("/faces/{face_id}/confirm")
def confirm(face_id: int, body: FaceDecision):
    s = _store()
    try:
        return faces.confirm(s, face_id, _person(s, body.person))
    finally:
        s.close()


@router.post("/faces/{face_id}/reject")
def reject(face_id: int, body: FaceDecision):
    s = _store()
    try:
        return faces.reject(s, face_id, _person(s, body.person))
    finally:
        s.close()


class Merge(BaseModel):
    keep: str
    drop: str


@router.post("/people/merge")
def merge(body: Merge):
    s = _store()
    try:
        return faces.merge(s, _person(s, body.keep), _person(s, body.drop))
    finally:
        s.close()


@router.get("/proposals")
def proposals(status: str | None = "pending", album: str | None = None):
    s = _store()
    try:
        rows = s.proposals(status or None, album)
        albums: dict[str, dict] = {}
        for p in rows:
            a = albums.setdefault(p["album"] or "(duplicates / moves)", {"album": p["album"], "count": 0, "ids": [], "sample": []})
            a["count"] += 1; a["ids"].append(p["id"])
            if len(a["sample"]) < 8:
                a["sample"].append({"asset": p["asset_id"], "path": p["path"], "dest": p["dest"], "action": p["action"]})
        return {"albums": list(albums.values()), "total": len(rows)}
    finally:
        s.close()


class Decide(BaseModel):
    ids: list[int] | None = None
    album: str | None = None
    all: bool = False


@router.post("/proposals/approve")
def approve(body: Decide):
    s = _store()
    try:
        return {"approved": organize.approve(s, ids=body.ids, album=body.album, everything=body.all)}
    finally:
        s.close()


@router.post("/proposals/reject")
def reject_proposals(body: Decide):
    s = _store()
    try:
        return {"rejected": organize.approve(s, ids=body.ids, album=body.album, everything=body.all, status="rejected")}
    finally:
        s.close()


@router.post("/apply")
def apply():
    s = _store()
    try:
        return organize.apply(s)
    finally:
        s.close()


@router.post("/recover")
def do_recover():
    s = _store()
    try:
        return recover.run(s, verify="sample")
    finally:
        s.close()


@router.get("/asset/{asset_id}")
def asset(asset_id: int):
    s = _store()
    try:
        a = s.asset(asset_id)
        if not a:
            return JSONResponse({"error": "no such asset"}, status_code=404)
        return {**{k: v for k, v in a.items() if k != "exif"}, "review": s.review(asset_id),
                "people": s.people_in(asset_id), "album": (s.albums().get(asset_id) or (None,))[0]}
    finally:
        s.close()


def page() -> FileResponse:
    return FileResponse(HERE / "library.html")
