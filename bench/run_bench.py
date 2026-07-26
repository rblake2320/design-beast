#!/usr/bin/env python3
"""Beast Studio benchmark runner (P1).

Runs every brief in briefs.json through the full quality loop against a live
Studio server, records score / latency / phase / improvement usage, and writes
versioned results to bench/results/<timestamp>_<model>.json + a markdown summary.

Usage:
    python bench/run_bench.py [--model local:flux.1-schnell] [--ids prod-01,ui-02]
"""
import argparse
import json
import statistics
import time
from pathlib import Path

import requests

B = "http://127.0.0.1:8787"
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RESULTS.mkdir(exist_ok=True)


def run_one(entry: dict, model: str) -> dict:
    t0 = time.time()
    r = requests.post(f"{B}/api/run", json={
        "brief": entry["brief"], "prompt": entry["prompt"],
        "variations": [entry["variation"]], "model": model}, timeout=30).json()
    jid = r["id"]
    while True:
        time.sleep(10)
        s = requests.get(f"{B}/api/run/{jid}", timeout=30).json()
        if s.get("phase") in ("done", "failed", "cancelled"):
            break
        if time.time() - t0 > 1800:
            s = {"phase": "timeout"}
            break
    cands = s.get("candidates", [])
    win = next((c for c in cands if c["i"] == s.get("winner")), None)
    return {
        "id": entry["id"], "category": entry["category"], "job": jid,
        "phase": s.get("phase"), "error": s.get("error"),
        "winner_score": win.get("score") if win else None,
        "auto_improved": bool(win and win.get("auto_improved")),
        "candidates": [{"i": c["i"], "score": c.get("score"), "kill": c.get("kill")}
                       for c in cands],
        "latency_s": round(time.time() - t0, 1),
        "upscaled": s.get("upscaled"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="local:flux.1-schnell")
    ap.add_argument("--ids", default="")
    args = ap.parse_args()

    briefs = json.loads((HERE / "briefs.json").read_text(encoding="utf-8"))["image_briefs"]
    if args.ids:
        keep = set(args.ids.split(","))
        briefs = [b for b in briefs if b["id"] in keep]

    health = requests.get(f"{B}/api/health", timeout=10).json()
    assert health["ok"], "server unhealthy — aborting benchmark"

    results = []
    for i, entry in enumerate(briefs, 1):
        print(f"[{i}/{len(briefs)}] {entry['id']} ...", flush=True)
        results.append(run_one(entry, args.model))
        print(f"    -> {results[-1]['phase']} score={results[-1]['winner_score']} "
              f"{results[-1]['latency_s']}s", flush=True)

    scores = [r["winner_score"] for r in results if r["winner_score"] is not None]
    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": args.model,
        "n": len(results),
        "completed": sum(1 for r in results if r["phase"] == "done"),
        "failed": sum(1 for r in results if r["phase"] != "done"),
        "mean_score": round(statistics.mean(scores), 2) if scores else None,
        "median_score": statistics.median(scores) if scores else None,
        "auto_improved_count": sum(1 for r in results if r["auto_improved"]),
        "mean_latency_s": round(statistics.mean(r["latency_s"] for r in results), 1),
        "results": results,
    }
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = RESULTS / f"{stamp}_{args.model.replace(':', '_')}.json"
    out.write_text(json.dumps(summary, indent=1))

    md = [f"# Bench {stamp} — {args.model}",
          f"- briefs: {summary['n']} · done: {summary['completed']} · failed: {summary['failed']}",
          f"- mean score: {summary['mean_score']} · median: {summary['median_score']}",
          f"- auto-improved winners: {summary['auto_improved_count']}",
          f"- mean latency: {summary['mean_latency_s']}s", "",
          "| id | cat | phase | score | improved | latency |", "|---|---|---|---|---|---|"]
    md += [f"| {r['id']} | {r['category']} | {r['phase']} | {r['winner_score']} | "
           f"{'yes' if r['auto_improved'] else ''} | {r['latency_s']}s |" for r in results]
    (RESULTS / f"{stamp}_{args.model.replace(':', '_')}.md").write_text(
        "\n".join(md), encoding="utf-8")
    print(f"\nwrote {out.name}: mean {summary['mean_score']} over {summary['n']} briefs")


if __name__ == "__main__":
    main()
