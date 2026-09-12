"""Stages 9-10: propose an album structure, queue it for approval, apply by hard-link/copy.

Invariants: the source tree is never written to; nothing is deleted; an existing
destination is never overwritten (a differing file gets a hash suffix); every applied
operation is hash-verified and ledgered.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path

from .inventory import sha256_file
from .store import Store

RECURRING_PERSON_MIN_FACES = 3
_SAFE = re.compile(r"[^A-Za-z0-9 _.,-]+")


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
    elif asset.get("event_title"):
        name = _SAFE.sub("", asset["event_title"]).strip(" .")[:40]
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


def _propose(store: Store, applied: dict, asset_id: int, action: str, dest: str | None,
             album: str | None, reason: str) -> str:
    """A proposal for a file already placed elsewhere becomes a move inside the organized tree."""
    old = applied.get((asset_id, action))
    if old and dest and Path(old) != Path(dest):
        store.put_proposal(asset_id, f"move:{action}", dest, album, f"from {old}")
        return "move"
    store.put_proposal(asset_id, action, dest, album, reason)
    return "same" if old else "new"


def plan(store: Store, dest_root: Path, people: bool = True,
         ollama_url: str = "http://localhost:11434/api/generate") -> dict:
    dest_root = dest_root.resolve()
    persons = {pid: (label or f"Person-{pid}", n) for pid, label, _, n in store.persons()}
    canonical = consolidate_albums(store, ollama_url)
    assigned = store.albums()
    n_link = n_dup = n_people = n_move = 0
    applied_dest = {(p["asset_id"], p["action"]): p["dest"] for p in store.proposals("applied") if p["dest"]}
    with store.tx():
        for asset in store.assets():
            if asset["dup_of"] is not None:
                rep = store.asset(asset["dup_of"])
                store.put_proposal(asset["id"], "duplicate", None, None,
                                   f"duplicate of {rep['path'] if rep else asset['dup_of']}")
                n_dup += 1
                continue
            if asset["stack_of"] is not None:      # burst frame: kept, filed under its best shot
                rep = store.asset(asset["stack_of"]) or asset
                album, folder = album_name(store, rep, canonical, assigned)
                stack_dir = f"{folder}/stack-{Path(rep['path']).stem}"
                n_move += _propose(store, applied_dest, asset["id"], "link", str(_dest(dest_root, stack_dir, asset)),
                                   album, f"burst frame; best shot is {Path(rep['path']).name}") == "move"
                n_link += 1
                continue
            album, folder = album_name(store, asset, canonical, assigned)
            n_move += _propose(store, applied_dest, asset["id"], "link", str(_dest(dest_root, folder, asset)), album,
                               "album from review" if album != "Unsorted" else "no confident review") == "move"
            n_link += 1
            if people:
                for pid in store.people_in(asset["id"]):
                    label, n = persons.get(pid, (None, 0))
                    if label and n >= RECURRING_PERSON_MIN_FACES:
                        n_move += _propose(store, applied_dest, asset["id"], f"person:{pid}",
                                           str(_dest(dest_root, f"People/{label}", asset)),
                                           f"People/{label}", f"{n} faces of {label}") == "move"
                        n_people += 1
    summary = {"dest_root": str(dest_root), "link": n_link, "duplicate": n_dup, "people": n_people,
               "moves": n_move, "albums": len(set(canonical.values())) or 1}
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
    organized file would edit the source — only for read-only libraries, by opt-in.

    Writes go to a temp name and are renamed into place, so a crash mid-copy can never
    leave a half file at a final path; leftover `.beast-partial` files are simply redone."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if hardlink:
        try:
            if os.name == "nt" and src.drive.lower() != dest.drive.lower():
                raise OSError("cross-volume")
            os.link(src, dest)
            return "hardlink"
        except OSError:
            pass
    tmp = dest.with_name(dest.name + ".beast-partial")
    shutil.copy2(src, tmp)
    with open(tmp, "rb+") as fh:
        os.fsync(fh.fileno())
    os.replace(tmp, dest)
    return "copy"


def approved_albums(store: Store) -> set[str]:
    """Albums a person has already said yes to — new photos may join them unattended."""
    return {p["album"] for p in store.proposals() if p["album"] and p["status"] in ("approved", "applied")
            and p["action"] == "link"}


def apply(store: Store, hardlink: bool = False) -> dict:
    applied = skipped = failed = noted = moved = 0
    for p in store.proposals("approved"):
        if not p["dest"]:   # informational (duplicate) — nothing to place
            store.set_proposal_status([p["id"]], "applied"); noted += 1
            continue
        if p["action"].startswith("move:"):
            try:
                _move(store, p)
                moved += 1
            except Exception as exc:  # noqa: BLE001
                store.log("apply.error", {"proposal": p["id"], "error": f"{type(exc).__name__}: {exc}"})
                failed += 1
            store.commit()
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
    summary = {"applied": applied, "moved": moved, "already_present": skipped, "duplicates_noted": noted,
               "failed": failed}
    store.log("apply.summary", summary)
    store.commit()
    if applied or moved:
        write_manifest(store)
    return summary


def write_manifest(store: Store) -> Path | None:
    """`<dest_root>/.beast/manifest.json`: every placed file with its source and SHA-256, so the
    organized tree explains itself even if the store is lost (see recover.rebuild_from_manifest)."""
    placed = [p for p in store.proposals("applied") if p["dest"] and not p["action"].startswith("move:")]
    row = store.fetchone("SELECT detail FROM ledger WHERE event = 'plan' ORDER BY id DESC LIMIT 1")
    if not placed or not row:
        return None
    root = Path(json.loads(row[0])["dest_root"])
    entries = [{"src": p["path"], "dest": p["dest"], "sha256": store.asset(p["asset_id"])["sha256"],
                "album": p["album"], "action": p["action"]} for p in placed]
    manifest = {"schema": "beast.library.manifest/v1", "written": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "count": len(entries), "entries": entries}
    out = root / ".beast" / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.partial")
    tmp.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    os.replace(tmp, out)
    return out


def _move(store: Store, p: dict) -> None:
    """Move an already-placed file inside the organized tree; the source library is never touched."""
    base_action = p["action"].split(":", 1)[1]
    base = next((b for b in store.proposals("applied") if b["asset_id"] == p["asset_id"]
                 and b["action"] == base_action), None)
    if not base or not base["dest"]:
        raise FileNotFoundError(f"no applied {base_action} for asset {p['asset_id']}")
    old, new = Path(base["dest"]), Path(p["dest"])
    asset = store.asset(p["asset_id"])
    if not old.exists():
        raise FileNotFoundError(old)
    if sha256_file(old) != asset["sha256"]:
        raise RuntimeError(f"{old} no longer matches the library copy — left alone")
    if new.exists():
        if sha256_file(new) == asset["sha256"]:
            old.unlink()                       # the same bytes are already at the new place
        else:
            new = new.with_name(f"{new.stem}_{asset['sha256'][:8]}{new.suffix}")
    if old.exists():
        new.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(old, new)               # same volume: atomic rename
        except OSError:
            _place(old, new, False)            # cross volume: temp+rename copy, then drop the old
            old.unlink()
    if sha256_file(new) != asset["sha256"]:
        raise RuntimeError(f"hash mismatch after move: {new}")
    store.execute("UPDATE proposals SET dest = ? WHERE id = ?", (str(new), base["id"]))
    store.set_proposal_status([p["id"]], "applied")
    store.log("apply.move", {"from": str(old), "to": str(new), "sha256": asset["sha256"]})
    try:                                       # tidy empty album folders left behind
        old.parent.rmdir()
        old.parent.parent.rmdir()
    except OSError:
        pass


def manifest_hash(store: Store) -> str:
    """Hash of every applied (src, dest, sha) triple — a receipt for the organized tree."""
    h = hashlib.sha256()
    for p in store.proposals("applied"):
        if p["dest"]:
            h.update(f"{p['path']}|{p['dest']}\n".encode())
    return h.hexdigest()
