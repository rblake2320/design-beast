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
    store.log("dedup", summary)
    store.commit()
    return summary


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
