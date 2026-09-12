"""Stage 1: read-only inventory — hashes, EXIF, dimensions, perceptual hashes, thumbnails."""
from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

from .store import Store

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif", ".avif"}
THUMB_LONG_SIDE = 1024
EXIF_KEEP = {271: "make", 272: "model", 274: "orientation", 306: "datetime",
             36867: "datetime_original", 33434: "exposure", 33437: "fnumber",
             34855: "iso", 37386: "focal_length", 42036: "lens"}

try:  # HEIC/HEIF (iPhone) — optional
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:  # noqa: BLE001
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def walk(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXT)


def _exif(img: Image.Image) -> dict:
    out: dict = {}
    try:
        raw = img.getexif()
        ifd = raw.get_ifd(0x8769) if raw else {}
        for tag, key in EXIF_KEEP.items():
            val = raw.get(tag, ifd.get(tag)) if raw else None
            if val is not None:
                out[key] = str(val)[:120]
        gps = raw.get_ifd(0x8825) if raw else {}
        if gps and 2 in gps and 4 in gps:
            out["gps"] = {"lat": _dms(gps[2], gps.get(1, "N")), "lon": _dms(gps[4], gps.get(3, "E"))}
    except Exception:  # noqa: BLE001 — EXIF is best-effort by nature
        pass
    return out


def _dms(dms, ref) -> float:
    deg = float(dms[0]) + float(dms[1]) / 60 + float(dms[2]) / 3600
    return round(-deg if ref in ("S", "W") else deg, 6)


def _taken_at(exif: dict, mtime: float) -> str:
    for key in ("datetime_original", "datetime"):
        val = exif.get(key)
        if val:
            try:
                return datetime.strptime(val[:19], "%Y:%m:%d %H:%M:%S").strftime("%Y-%m-%dT%H:%M:%S")
            except ValueError:
                continue
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M:%S")


def analyze(path: Path) -> tuple[dict, bytes]:
    """Return (asset row, thumbnail JPEG bytes). Never writes to `path`."""
    import imagehash
    stat = path.stat()
    with Image.open(path) as img:
        fmt = (img.format or path.suffix.lstrip(".")).lower()
        exif = _exif(img)
        img = ImageOps.exif_transpose(img)
        width, height = img.size
        rgb = img.convert("RGB")
        phash = str(imagehash.phash(rgb))
        dhash = str(imagehash.dhash(rgb))
        rgb.thumbnail((THUMB_LONG_SIDE, THUMB_LONG_SIDE))
        buf = io.BytesIO()
        rgb.save(buf, "JPEG", quality=88, optimize=True)
    row = {
        "path": str(path), "sha256": sha256_file(path), "size": stat.st_size,
        "mtime": stat.st_mtime, "width": width, "height": height, "format": fmt,
        "taken_at": _taken_at(exif, stat.st_mtime), "exif": json.dumps(exif),
        "phash": phash, "dhash": dhash,
    }
    return row, buf.getvalue()


def scan(store: Store, root: Path, progress=None) -> dict:
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    files = walk(root)
    known = {p: sha for p, sha in store.fetchall("SELECT path, sha256 FROM assets")}
    added = unchanged = failed = 0
    for i, path in enumerate(files, 1):
        key = str(path)
        if key in known and _cheap_same(store, key, path):
            unchanged += 1
            continue
        try:
            row, thumb = analyze(path)
        except Exception as exc:  # noqa: BLE001 — one bad file must not stop a scan
            failed += 1
            store.log("scan.error", {"path": key, "error": f"{type(exc).__name__}: {exc}"})
            continue
        with store.tx():
            aid = store.upsert_asset(row)
            store.put_thumb(aid, thumb)
        added += 1
        if progress and i % 50 == 0:
            progress(i, len(files))
    store.log("scan", {"root": str(root), "files": len(files), "added": added,
                       "unchanged": unchanged, "failed": failed})
    store.commit()
    return {"root": str(root), "files": len(files), "added_or_updated": added,
            "unchanged": unchanged, "failed": failed}


def _cheap_same(store: Store, key: str, path: Path) -> str | None:
    """Skip rehashing when size+mtime match the stored row; else return None to force re-analysis."""
    row = store.fetchone("SELECT sha256, size, mtime FROM assets WHERE path = ?", (key,))
    if not row:
        return None
    st = path.stat()
    return row[0] if (row[1] == st.st_size and abs(float(row[2]) - st.st_mtime) < 1) else None
