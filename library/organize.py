"""Stages 9-10: propose an album structure, queue it for approval, apply by hard-link/copy.

Invariants: the source tree is never written to; nothing is deleted; an existing
destination is never overwritten (a differing file gets a hash suffix); every applied
operation is hash-verified and ledgered.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
from pathlib import Path

from .inventory import sha256_file
from .store import Store

RECURRING_PERSON_MIN_FACES = 3
_SAFE = re.compile(r"[^A-Za-z0-9 _.-]+")


ALBUM_MERGE_COSINE = 0.80   # bge-m3: "Beach trip"~"Beach day" 0.88, "Receipts"~"Invoice Records" 0.62


def _candidate_names(store: Store) -> dict[str, int]:
    """Album names that will actually be used: the albums table if present, else review names."""
    counts: dict[str, int] = {}
    assigned = store.albums()
    for asset in store.assets(representatives_only=True):
        if asset["id"] in assigned:
            name = _SAFE.sub("", assigned[asset["id"]][0]).strip(" .")[:40]
        else:
            review = store.review(asset["id"]) or {}
            name = _SAFE.sub("", review.get("suggested_album") or "").strip(" .")[:40]
            if review.get("confidence", 0) < 0.5:
                name = ""
        if name:
            counts[name] = counts.get(name, 0) + 1
    return counts


def consolidate_albums(store: Store, ollama_url: str = "http://localhost:11434/api/generate") -> dict[str, str]:
    """Map every album name to a canonical one.

    Names still vary ("Beach trip", "Beach vacation", "Beach day") — text embeddings +
    union-find merge them and the most frequent spelling wins. SigLIP2's text tower is
    NOT used: its text-text cosines are anisotropic (unrelated names scored >0.85), so
    a sentence embedder (bge-m3 via Ollama, `albums.text_embeddings`) does it.
    """
    from .albums import text_embeddings
    counts = _candidate_names(store)
    names = sorted(counts, key=lambda n: (-counts[n], n))
    if len(names) < 2:
        return {n: n for n in names}
    vecs = text_embeddings(names, ollama_url)
    if vecs is None:
        store.log("albums.consolidate", {"names": len(names), "skipped": "text embedder unavailable"})
        return {n: n for n in names}
    sims = vecs @ vecs.T
    parent = list(range(len(names)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    lower = [n.lower() for n in names]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if sims[i, j] >= ALBUM_MERGE_COSINE or lower[i] == lower[j]:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)   # lower index = more frequent = canonical
    mapping = {names[i]: names[find(i)] for i in range(len(names))}
    merged = {k: v for k, v in mapping.items() if k != v}
    store.log("albums.consolidate", {"names": len(names), "merged": merged})
    return mapping


def album_name(store: Store, asset: dict, canonical: dict[str, str] | None = None,
               assigned: dict[int, tuple[str, str]] | None = None) -> tuple[str, str]:
    year_month = (asset.get("taken_at") or "0000-00")[:7]
    assigned = store.albums() if assigned is None else assigned
    if asset["id"] in assigned:
        name = _SAFE.sub("", assigned[asset["id"]][0]).strip(" .")[:40]
    else:
        review = store.review(asset["id"]) or {}
        name = _SAFE.sub("", review.get("suggested_album") or "").strip(" .")[:40]
        if review.get("confidence", 0) < 0.5:
            name = ""
    if name:
        name = (canonical or {}).get(name, name)
        return name, f"{name}/{year_month}"
    return "Unsorted", f"Unsorted/{year_month}"


def _dest(root: Path, folder: str, asset: dict) -> Path:
    src = Path(asset["path"])
    stamp = (asset.get("taken_at") or "")[:10].replace("-", "")
    return root / folder / f"{stamp}_{src.name}" if stamp else root / folder / src.name


def plan(store: Store, dest_root: Path, people: bool = True,
         ollama_url: str = "http://localhost:11434/api/generate") -> dict:
    dest_root = dest_root.resolve()
    persons = {pid: (label or f"Person-{pid}", n) for pid, label, _, n in store.persons()}
    canonical = consolidate_albums(store, ollama_url)
    assigned = store.albums()
    n_link = n_dup = n_people = 0
    with store.tx():
        for asset in store.assets():
            if asset["dup_of"] is not None:
                rep = store.asset(asset["dup_of"])
                store.put_proposal(asset["id"], "duplicate", None, None,
                                   f"duplicate of {rep['path'] if rep else asset['dup_of']}")
                n_dup += 1
                continue
            album, folder = album_name(store, asset, canonical, assigned)
            store.put_proposal(asset["id"], "link", str(_dest(dest_root, folder, asset)), album,
                               "album from review" if album != "Unsorted" else "no confident review")
            n_link += 1
            if people:
                for pid in store.people_in(asset["id"]):
                    label, n = persons.get(pid, (None, 0))
                    if label and n >= RECURRING_PERSON_MIN_FACES:
                        store.put_proposal(asset["id"], f"person:{pid}",
                                           str(_dest(dest_root, f"People/{label}", asset)),
                                           f"People/{label}", f"{n} faces of {label}")
                        n_people += 1
    summary = {"dest_root": str(dest_root), "link": n_link, "duplicate": n_dup, "people": n_people,
               "albums": len(set(canonical.values())) or 1}
    store.log("plan", summary)
    store.commit()
    return summary


def approve(store: Store, ids: list[int] | None = None, album: str | None = None,
            everything: bool = False, status: str = "approved") -> int:
    if everything:
        ids = [p["id"] for p in store.proposals("pending")]
    elif album:
        ids = [p["id"] for p in store.proposals("pending", album)]
    n = store.set_proposal_status(ids or [], status)
    store.log(status, {"count": n, "album": album, "all": everything})
    store.commit()
    return n


def _place(src: Path, dest: Path, hardlink: bool) -> str:
    """Copy by default. A hard link shares bytes with the original, so editing the
    organized file would edit the source — only for read-only libraries, by opt-in."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if hardlink:
        try:
            if os.name == "nt" and src.drive.lower() != dest.drive.lower():
                raise OSError("cross-volume")
            os.link(src, dest)
            return "hardlink"
        except OSError:
            pass
    shutil.copy2(src, dest)
    return "copy"


def apply(store: Store, hardlink: bool = False) -> dict:
    applied = skipped = failed = noted = 0
    for p in store.proposals("approved"):
        if not p["dest"]:   # informational (duplicate) — nothing to place
            store.set_proposal_status([p["id"]], "applied"); noted += 1
            continue
        src, dest = Path(p["path"]), Path(p["dest"])
        asset = store.asset(p["asset_id"])
        try:
            if not src.exists():
                raise FileNotFoundError(src)
            if dest.exists():
                if sha256_file(dest) == asset["sha256"]:
                    store.set_proposal_status([p["id"]], "applied"); skipped += 1
                    store.log("apply.exists", {"dest": str(dest)})
                    continue
                dest = dest.with_name(f"{dest.stem}_{asset['sha256'][:8]}{dest.suffix}")
            how = _place(src, dest, hardlink)
            if sha256_file(dest) != asset["sha256"]:
                raise RuntimeError(f"hash mismatch after {how}: {dest}")
            store.execute("UPDATE proposals SET dest = ? WHERE id = ?", (str(dest), p["id"]))
            store.set_proposal_status([p["id"]], "applied")
            store.log("apply", {"src": str(src), "dest": str(dest), "how": how, "sha256": asset["sha256"]})
            applied += 1
        except Exception as exc:  # noqa: BLE001
            store.log("apply.error", {"proposal": p["id"], "error": f"{type(exc).__name__}: {exc}"})
            failed += 1
        store.commit()
    summary = {"applied": applied, "already_present": skipped, "duplicates_noted": noted, "failed": failed}
    store.log("apply.summary", summary)
    store.commit()
    return summary


def manifest_hash(store: Store) -> str:
    """Hash of every applied (src, dest, sha) triple — a receipt for the organized tree."""
    h = hashlib.sha256()
    for p in store.proposals("applied"):
        if p["dest"]:
            h.update(f"{p['path']}|{p['dest']}\n".encode())
    return h.hexdigest()
