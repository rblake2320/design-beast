"""Stage 9a: album discovery — group representatives, then name each group once.

A VLM asked image-by-image invents a new album name for almost every picture (304 names
for 382 images in the first real run). Grouping first on a joint image+caption embedding
and naming each group once — with the list of names already chosen — gives albums that
are consistent by construction. Small groups borrow the nearest named album when close
enough, otherwise keep their own consolidated review name.
"""
from __future__ import annotations

import json
import urllib.request

import numpy as np

from . import embed
from .store import Store

TEXT_MODEL = "bge-m3"
TEXT_WEIGHT = 0.5          # calibrated 2026-09-12 on 382 real screenshots/photos
GROUP_DISTANCE = 0.30      # average-linkage cosine distance cut
MIN_GROUP = 3              # groups this size or larger get an LLM name
BORROW_MIN_COSINE = 0.70   # smaller groups join the nearest named group above this
NAME_SCHEMA = {"type": "object", "properties": {"album": {"type": "string"}}, "required": ["album"]}
NAME_PROMPT = """You are naming photo albums for a personal library. Below are captions and
suggested names for a group of pictures that belong together, plus album names that already
exist. Reply in JSON with one short, specific album name (2-4 words, no dates, no slashes).
If one of the existing album names clearly fits this group, reuse it EXACTLY.

Existing album names: {existing}
Date range: {dates}
Pictures:
{lines}"""


def text_embeddings(texts: list[str], ollama_url: str, chunk: int = 32) -> np.ndarray | None:
    url = ollama_url.rsplit("/api/", 1)[0] + "/api/embed"
    out: list[list[float]] = []
    try:
        for i in range(0, len(texts), chunk):
            body = json.dumps({"model": TEXT_MODEL, "input": texts[i:i + chunk]}).encode()
            req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                out += json.loads(r.read())["embeddings"]
    except Exception:  # noqa: BLE001 — callers degrade to review names
        return None
    vecs = np.asarray(out, dtype=np.float32)
    return vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)


def _describe(review: dict) -> str:
    return (f"{review.get('suggested_album', '')}. {review.get('caption', '')} "
            f"Tags: {', '.join(review.get('categories', []))}")


def features(store: Store, ollama_url: str, image_model: str = embed.DEFAULT_MODEL):
    reps = [a for a in store.assets(representatives_only=True) if store.review(a["id"])]
    ids, img = store.embeddings(image_model, [a["id"] for a in reps])
    by_id = {a["id"]: a for a in reps}
    reviews = [store.review(i) for i in ids]
    txt = text_embeddings([_describe(r) for r in reviews], ollama_url)
    if txt is None:
        return ids, by_id, reviews, None
    feat = np.concatenate([img * np.sqrt(1 - TEXT_WEIGHT), txt * np.sqrt(TEXT_WEIGHT)], axis=1)
    return ids, by_id, reviews, feat


def group(feat: np.ndarray, distance: float = GROUP_DISTANCE) -> np.ndarray:
    from scipy.cluster.hierarchy import fcluster, linkage
    if len(feat) < 2:
        return np.ones(len(feat), dtype=int)
    return fcluster(linkage(feat, method="average", metric="cosine"), t=distance, criterion="distance")


def name_group(reviews: list[dict], dates: tuple[str, str], existing: list[str], ollama_url: str,
               model: str) -> str:
    lines = "\n".join(f"- {_describe(r)[:160]}" for r in reviews[:12])
    prompt = NAME_PROMPT.format(existing=", ".join(existing[-40:]) or "(none yet)",
                                dates=f"{dates[0][:10]} to {dates[1][:10]}", lines=lines)
    body = json.dumps({"model": model, "prompt": prompt, "stream": False, "format": NAME_SCHEMA,
                       "think": False, "options": {"temperature": 0.1, "num_predict": 60}}).encode()
    req = urllib.request.Request(ollama_url, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        out = json.loads(r.read())
    name = json.loads(out["response"] or out.get("thinking", "{}")).get("album", "").strip()
    return name[:40] or "Unsorted"


def run(store: Store, ollama_url: str, model: str, image_model: str = embed.DEFAULT_MODEL) -> dict:
    ids, by_id, reviews, feat = features(store, ollama_url, image_model)
    if feat is None or not ids:
        summary = {"skipped": "text embedder unavailable" if ids else "no reviewed representatives"}
        store.log("albums", summary)
        return summary
    labels = group(feat)
    sizes = np.bincount(labels)
    named: dict[int, str] = {}
    centroids: dict[int, np.ndarray] = {}
    existing: list[str] = []
    for g in sorted(set(labels.tolist()), key=lambda g: -sizes[g]):
        members = np.where(labels == g)[0]
        if len(members) < MIN_GROUP:
            continue
        dates = sorted(by_id[ids[i]]["taken_at"] or "" for i in members)
        name = name_group([reviews[i] for i in members], (dates[0], dates[-1]), existing, ollama_url, model)
        named[g] = name
        if name not in existing:
            existing.append(name)
        c = feat[members].mean(axis=0)
        centroids[g] = c / (np.linalg.norm(c) + 1e-9)
    counts = {"event": 0, "grouped": 0, "borrowed": 0, "own": 0}
    with store.tx():
        store.clear_albums()
        for i, aid in enumerate(ids):
            g = int(labels[i])
            if by_id[aid].get("event_title"):      # time+GPS event with a real place wins
                store.put_album(aid, by_id[aid]["event_title"], "event", by_id[aid]["event_id"])
                counts["event"] += 1
                continue
            if g in named:
                store.put_album(aid, named[g], "group", g); counts["grouped"] += 1
                continue
            best, best_sim = None, BORROW_MIN_COSINE
            for cg, c in centroids.items():
                sim = float(feat[i] @ c)
                if sim >= best_sim:
                    best, best_sim = cg, sim
            if best is not None:
                store.put_album(aid, named[best], "borrowed", best); counts["borrowed"] += 1
            else:
                own = (reviews[i].get("suggested_album") or "").strip()[:40]
                if own and reviews[i].get("confidence", 0) >= 0.5:
                    store.put_album(aid, own, "review", g); counts["own"] += 1
    summary = {"representatives": len(ids), "groups": int(labels.max()), "named_groups": len(named),
               "albums": len(set(named.values())), **counts, "model": model}
    store.log("albums", summary)
    store.commit()
    return summary
