#!/usr/bin/env python3
"""Measure the fast review tier: images/second vs concurrency, per backend.

  python bench/library_review_bench.py --db library/data/beast-library.db \
      --backend "ollama=http://localhost:11434/api/generate|qwen3-vl:8b" \
      --backend "vllm=http://127.0.0.1:8021/v1/chat/completions|Qwen/Qwen3-VL-8B-Instruct-FP8" \
      --n 48 --parallel 1 4 8 16

Uses thumbnails already in the store (same bytes the real stage sends). Writes
bench/results/library-review-<date>.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from library import review  # noqa: E402
from library.store import Store  # noqa: E402


def run_once(url: str, model: str, thumbs: list[bytes], parallel: int) -> dict:
    ok = fail = 0
    t0 = time.time()
    with ThreadPoolExecutor(parallel) as pool:
        for r in pool.map(lambda b: _one(url, model, b), thumbs):
            ok += r; fail += (not r)
    dt = time.time() - t0
    return {"parallel": parallel, "images": len(thumbs), "ok": ok, "failed": fail,
            "seconds": round(dt, 1), "img_per_s": round(ok / dt, 2) if dt else None}


def _one(url: str, model: str, jpeg: bytes) -> bool:
    try:
        out = review.review_image(jpeg, model, url)
        return bool(out.get("caption"))
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--backend", action="append", required=True, help="name=url|model")
    ap.add_argument("--n", type=int, default=48)
    ap.add_argument("--parallel", type=int, nargs="+", default=[1, 4, 8, 16])
    args = ap.parse_args()
    store = Store(args.db)
    ids = [a["id"] for a in store.assets(representatives_only=True)][:args.n]
    thumbs = [store.get_thumb(i) for i in ids]
    results = {}
    for spec in args.backend:
        name, rest = spec.split("=", 1)
        url, model = rest.rsplit("|", 1)
        _one(url, model, thumbs[0])                          # warm-up / model load
        results[name] = {"url": url, "model": model, "runs": []}
        for p in args.parallel:
            r = run_once(url, model, thumbs, p)
            results[name]["runs"].append(r)
            print(f"{name:<8} parallel={p:<3} {r['img_per_s']} img/s  ({r['ok']}/{r['images']} ok, {r['seconds']}s)")
    out = REPO / "bench" / "results" / f"library-review-{time.strftime('%Y%m%d-%H%M')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"n": args.n, "results": results}, indent=2), encoding="utf-8")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
