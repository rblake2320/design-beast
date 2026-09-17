"""Stage 2: exact + near-duplicate clustering (SHA-256, pHash/dHash, optional embeddings).

Every asset gets a cluster_id; non-representatives get dup_of = representative id.
Representative = highest resolution, then largest file. Nothing is deleted.
"""
from __future__ import annotations

import numpy as np

from .store import Store

PHASH_MAX_DISTANCE = 6      # 64-bit pHash; <=6 bits differ = same picture, re-encoded/resized
EMBED_MIN_COSINE = 0.965    # SigLIP2 cosine; catches crops/edits pHash misses
EMBED_PHASH_GUARD = 18      # embedding edges still need loosely related pHashes (of 64 bits)


def _hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


class _UnionFind:
    def __init__(self, ids):
        self.parent = {i: i for i in ids}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def cluster(store: Store, embed_model: str | None = None, phash_max: int = PHASH_MAX_DISTANCE,
            embed_min: float = EMBED_MIN_COSINE) -> dict:
    assets = store.assets()
    uf = _UnionFind([a["id"] for a in assets])
    edges = {"sha256": 0, "phash": 0, "embedding": 0}

    by_sha: dict[str, int] = {}
    for a in assets:
        if a["sha256"] in by_sha:
            uf.union(by_sha[a["sha256"]], a["id"]); edges["sha256"] += 1
        else:
            by_sha[a["sha256"]] = a["id"]

    # pHash: bucket by the top 16 bits so we compare only plausible pairs (O(n) buckets, not O(n²)).
    buckets: dict[str, list[dict]] = {}
    for a in assets:
        if a["phash"]:
            buckets.setdefault(a["phash"][:4], []).append(a)
    hashed = [a for a in assets if a["phash"]]
    pairs = _candidate_pairs(hashed, buckets)
    for a, b in pairs:
        if _hamming(a["phash"], b["phash"]) <= phash_max and _hamming(a["dhash"], b["dhash"]) <= phash_max + 4:
            if _is_burst_pair(a, b):
                continue            # same camera, seconds apart, same size: a burst frame, not a copy
            uf.union(a["id"], b["id"]); edges["phash"] += 1

    if embed_model:
        # Embeddings confirm crops/edits that pHash misses, but only when the hashes are
        # still loosely related — otherwise semantically similar photos (a burst, a series
        # of screenshots) would collapse into one cluster.
        phash_of = {a["id"]: a["phash"] for a in assets}
        ids, mat = store.embeddings(embed_model)
        if len(ids) > 1:
            sims = mat @ mat.T
            np.fill_diagonal(sims, 0)
            for i, j in zip(*np.where(np.triu(sims) >= embed_min)):
                a, b = ids[int(i)], ids[int(j)]
                if phash_of.get(a) and phash_of.get(b) and \
                        _hamming(phash_of[a], phash_of[b]) <= EMBED_PHASH_GUARD:
                    uf.union(a, b); edges["embedding"] += 1

    groups: dict[int, list[dict]] = {}
    for a in assets:
        groups.setdefault(uf.find(a["id"]), []).append(a)
    with store.tx():
        for members in groups.values():
            rep = max(members, key=lambda m: ((m["width"] or 0) * (m["height"] or 0), m["size"] or 0))
            for m in members:
                store.set_cluster(m["id"], rep["id"], None if m["id"] == rep["id"] else rep["id"])
    summary = {"assets": len(assets), "clusters": len(groups),
               "duplicates": len(assets) - len(groups), "edges": edges}
    summary["stacks"] = stacks(store, embed_model)
    store.log("dedup", summary)
    store.commit()
    return summary


STACK_SECONDS = 90          # burst = same subject within this window …
STACK_PHASH_MAX = 20        # … and loosely similar hashes
STACK_EMBED_MIN = 0.90      # … or clearly the same scene by embedding


def sharpness(jpeg: bytes) -> float:
    """Variance of the Laplacian — the classic focus measure; higher = sharper."""
    import io
    import numpy as np
    from PIL import Image
    try:
        import cv2
        arr = np.asarray(Image.open(io.BytesIO(jpeg)).convert("L"))
        return float(cv2.Laplacian(arr, cv2.CV_64F).var())
    except ImportError:
        arr = np.asarray(Image.open(io.BytesIO(jpeg)).convert("L"), dtype=np.float32)
        lap = arr[:-2, 1:-1] + arr[2:, 1:-1] + arr[1:-1, :-2] + arr[1:-1, 2:] - 4 * arr[1:-1, 1:-1]
        return float(lap.var())


def stacks(store: Store, embed_model: str | None) -> dict:
    """Group burst shots (same moment, same scene) and pick the best one to represent them.

    A stack is NOT a duplicate: every frame is kept and placed; only the best shot is
    reviewed and shown first. Best = sharpest (Laplacian) with a resolution tie-break;
    faces and the VLM quality score refine the pick later if those stages have run.
    """
    from datetime import datetime
    reps = [a for a in store.assets() if a["dup_of"] is None]
    for a in reps:
        try:
            a["_t"] = datetime.fromisoformat(a["taken_at"]).timestamp()
        except (TypeError, ValueError):
            a["_t"] = None
    reps.sort(key=lambda a: (a["_t"] is None, a["_t"] or 0))
    vec: dict[int, np.ndarray] = {}
    if embed_model:
        ids, mat = store.embeddings(embed_model, [a["id"] for a in reps])
        vec = dict(zip(ids, mat))
    uf = _UnionFind([a["id"] for a in reps])
    for i, a in enumerate(reps):
        if a["_t"] is None:
            break
        for b in reps[i + 1:]:
            if b["_t"] is None or b["_t"] - a["_t"] > STACK_SECONDS:
                break
            close_hash = a["phash"] and b["phash"] and _hamming(a["phash"], b["phash"]) <= STACK_PHASH_MAX
            close_embed = (a["id"] in vec and b["id"] in vec
                           and float(vec[a["id"]] @ vec[b["id"]]) >= STACK_EMBED_MIN)
            if close_hash or close_embed:
                uf.union(a["id"], b["id"])
    groups: dict[int, list[dict]] = {}
    for a in reps:
        groups.setdefault(uf.find(a["id"]), []).append(a)
    n_stacks = n_members = 0
    with store.tx():
        for a in reps:
            store.set_stack(a["id"], None)
        for members in groups.values():
            if len(members) < 2:
                continue
            for m in members:
                thumb = store.get_thumb(m["id"])
                m["_sharp"] = sharpness(thumb) if thumb else 0.0
            best = max(members, key=lambda m: (m["_sharp"], (m["width"] or 0) * (m["height"] or 0)))
            for m in members:
                if m["id"] != best["id"]:
                    store.set_stack(m["id"], best["id"])
                    store.execute("UPDATE queue SET status = 'skipped', error = 'burst stack member' "
                                  "WHERE asset_id = ? AND stage IN ('review_fast', 'review_deep') "
                                  "AND status = 'pending'", (m["id"],))
            n_stacks += 1
            n_members += len(members) - 1
    return {"stacks": n_stacks, "members": n_members}


def _is_burst_pair(a: dict, b: dict) -> bool:
    """Near-identical hashes but distinct captures: same dimensions, different bytes, and
    EXIF times 1..STACK_SECONDS apart. A re-encode/resize keeps the timestamp or changes size."""
    from datetime import datetime
    if a["sha256"] == b["sha256"] or (a["width"], a["height"]) != (b["width"], b["height"]):
        return False
    try:
        gap = abs((datetime.fromisoformat(a["taken_at"]) - datetime.fromisoformat(b["taken_at"])).total_seconds())
    except (TypeError, ValueError):
        return False
    return 0 < gap <= STACK_SECONDS


def _candidate_pairs(hashed: list[dict], buckets: dict[str, list[dict]]):
    """All pairs inside a bucket, plus a full pass when the set is small enough to afford it."""
    if len(hashed) <= 4000:
        for i, a in enumerate(hashed):
            for b in hashed[i + 1:]:
                yield a, b
        return
    for members in buckets.values():
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                yield a, b
