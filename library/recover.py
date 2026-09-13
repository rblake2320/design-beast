"""Recovery: one command that puts the library back on its feet after any failure.

Failure classes and what `recover` does about each:
  worker/process died mid-stage   -> stale 'running' claims are handed back (also automatic at stage start)
  model server was down           -> rows the outage returned to 'pending' simply run again; 'error' rows
                                     are requeued once here so a transient fault is not permanent
  crash mid-copy                  -> `.beast-partial` files are deleted; the proposal is still 'approved'
                                     and is redone by the next `apply`
  organized file changed/removed  -> `verify` re-hashes placed files and reports drift; a missing file is
                                     re-approved so `apply` restores it from the untouched source
  store corrupted or lost         -> `backup` / `restore` (SQLite online backup), or `rebuild_from_manifest`
                                     recreates the placement record from `<dest>/.beast/manifest.json`
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from .inventory import sha256_file
from .store import STAGES, Store


def run(store: Store, verify: str = "sample", sample: int = 50) -> dict:
    out: dict = {"integrity": store.integrity(), "reclaimed": {}, "requeued_errors": {}, "partials_removed": 0}
    for stage in STAGES:
        out["reclaimed"][stage] = store.reclaim_stale(stage, minutes=0)
        n = store.requeue(stage, statuses=("error",))
        if n:
            out["requeued_errors"][stage] = n
    row = store.fetchone("SELECT detail FROM ledger WHERE event = 'plan' ORDER BY id DESC LIMIT 1")
    if row:
        root = Path(json.loads(row[0])["dest_root"])
        if root.exists():
            for partial in root.rglob("*.beast-partial"):
                partial.unlink(); out["partials_removed"] += 1
        out["verify"] = verify_placed(store, "all" if verify == "all" else sample)
    out["counts"] = store.counts()
    store.log("recover", {k: v for k, v in out.items() if k != "counts"})
    store.commit()
    return out


def verify_placed(store: Store, how: int | str = 50) -> dict:
    """Re-hash placed files. Missing -> re-approved (apply restores it); changed -> reported, left alone."""
    placed = [p for p in store.proposals("applied") if p["dest"] and not p["action"].startswith("move:")]
    if how != "all":
        import random
        random.seed(int(time.time()))
        placed = random.sample(placed, min(int(how), len(placed)))
    ok = missing = changed = 0
    for p in placed:
        dest = Path(p["dest"])
        sha = store.asset(p["asset_id"])["sha256"]
        if not dest.exists():
            missing += 1
            store.execute("UPDATE proposals SET status = 'approved', applied_at = NULL WHERE id = ?", (p["id"],))
            store.log("verify.missing", {"dest": str(dest), "proposal": p["id"]})
        elif sha256_file(dest) != sha:
            changed += 1
            store.log("verify.changed", {"dest": str(dest), "proposal": p["id"]})
        else:
            ok += 1
    store.commit()
    return {"checked": len(placed), "ok": ok, "missing_reapproved": missing, "changed": changed}


def backup(store: Store, dest_dir: Path) -> dict:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = dest_dir / f"beast-library-{stamp}.{'dump' if store.pg else 'db'}"
    store.backup(target)
    keep = sorted(dest_dir.glob("beast-library-*"))[:-7]        # rolling: keep the last 7
    for old in keep:
        old.unlink()
    store.log("backup", {"path": str(target), "bytes": target.stat().st_size})
    store.commit()
    return {"path": str(target), "bytes": target.stat().st_size, "kept": 7}


def restore(backup_path: Path, db_path: Path) -> dict:
    """SQLite only: replace the store with a backup (the current file is kept as .before-restore)."""
    if not backup_path.exists():
        raise FileNotFoundError(backup_path)
    try:
        check = Store(backup_path).integrity()
    except Exception as exc:  # noqa: BLE001 — unreadable is as bad as failing the check
        raise RuntimeError(f"backup is not a usable store: {type(exc).__name__}: {exc}") from exc
    if check != "ok":
        raise RuntimeError(f"backup fails integrity_check: {check}")
    if db_path.exists():
        shutil.copy2(db_path, db_path.with_suffix(db_path.suffix + ".before-restore"))
    for side in ("-wal", "-shm"):
        p = Path(str(db_path) + side)
        if p.exists():
            p.unlink()
    shutil.copy2(backup_path, db_path)
    return {"restored": str(db_path), "from": str(backup_path), "counts": Store(db_path).counts()}


def rebuild_from_manifest(store: Store, dest_root: Path) -> dict:
    """Store lost but the organized tree exists: re-inventory the sources named in the manifest
    and mark their placements applied, so nothing is copied twice and moves still work."""
    manifest = json.loads((dest_root / ".beast" / "manifest.json").read_text(encoding="utf-8"))
    from .inventory import analyze, analyze_video, VIDEO_EXT
    restored = missing = 0
    with store.tx():
        for e in manifest["entries"]:
            src, dest = Path(e["src"]), Path(e["dest"])
            if not dest.exists():
                missing += 1; continue
            if store.fetchone("SELECT id FROM assets WHERE path = ?", (str(src),)) is None:
                if not src.exists():
                    missing += 1; continue
                row, thumb = analyze_video(src) if src.suffix.lower() in VIDEO_EXT else analyze(src)
                aid = store.upsert_asset(row); store.put_thumb(aid, thumb)
            aid = store.fetchone("SELECT id FROM assets WHERE path = ?", (str(src),))[0]
            store.put_proposal(int(aid), e["action"], str(dest), e.get("album"), "rebuilt from manifest")
            store.execute("UPDATE proposals SET status = 'applied', applied_at = ? WHERE asset_id = ? AND action = ?",
                          (time.strftime("%Y-%m-%dT%H:%M:%S"), int(aid), e["action"]))
            restored += 1
        store.log("plan", {"dest_root": str(dest_root), "rebuilt": True})
    store.commit()
    return {"restored": restored, "missing": missing, "manifest_count": manifest["count"]}
