#!/usr/bin/env python3
"""Beast Studio benchmark runner (P1).

Runs every brief in briefs.json through the full quality loop against a live
Studio server, records score / latency / phase / improvement usage, and writes
versioned results to bench/results/<timestamp>_<model>.json + a markdown summary.

Protocol v0.2 (2026-07-26): each brief runs FOUR controlled candidates —
the base prompt, the brief's own variation, and two fixed control variations
shared by every brief. The server generates one candidate per entry in
`variations` (an empty string means the base prompt unchanged), so the
request below is what actually produces 4 candidates.

HISTORY / CORRECTION: runs before 2026-07-26 (protocol v0.1) sent
`variations=[<one variation>]`, which the server turns into a SINGLE
candidate whose prompt is "base; variation" — the base prompt alone never
ran. Those results are single-candidate and cannot substantiate any
multi-candidate quality-loop claim. They are preserved unmodified in
results/ for latency/score reference only.

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

PROTOCOL_VERSION = "0.2"
EXPECTED_CANDIDATES = 4
# Fixed control variations applied to every brief so all runs are comparable.
# Changing these invalidates cross-run comparisons — bump PROTOCOL_VERSION.
CONTROL_VARIATIONS = [
    "alternate camera angle, same subject, style and palette",
    "alternate lighting treatment, same subject, composition and style",
]


def build_variations(entry: dict) -> list[str]:
    """Four controlled candidates: base ("" = unchanged), the brief's own
    variation, and the two fixed controls."""
    return ["", entry["variation"], *CONTROL_VARIATIONS]


def primary_candidates(cands: list[dict]) -> list[dict]:
    """Primary generation candidates only — the auto-improvement pass appends
    candidates with i >= 90 and those must not count toward the protocol's four."""
    return [c for c in cands if c["i"] < 90]


def run_one(entry: dict, model: str) -> dict:
    variations = build_variations(entry)
    t0 = time.time()
    r = requests.post(f"{B}/api/run", json={
        "brief": entry["brief"], "prompt": entry["prompt"],
        "variations": variations, "model": model}, timeout=30).json()
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
    primary = primary_candidates(cands)
    count_ok = len(primary) == EXPECTED_CANDIDATES
    if not count_ok and s.get("phase") == "done":
        print(f"    !! candidate-count violation: expected {EXPECTED_CANDIDATES}, "
              f"got {len(primary)} — result marked invalid", flush=True)
    win = next((c for c in cands if c["i"] == s.get("winner")), None)
    return {
        "id": entry["id"], "category": entry["category"], "job": jid,
        "phase": s.get("phase"), "error": s.get("error"),
        "candidate_count_ok": count_ok,
        "winner_score": win.get("score") if win else None,
        "auto_improved": bool(win and win.get("auto_improved")),
        "candidates": [{"i": c["i"], "score": c.get("score"), "kill": c.get("kill")}
                       for c in cands],
        "latency_s": round(time.time() - t0, 1),
        "upscaled": s.get("upscaled"),
    }


def unique_path(p: Path) -> Path:
    """Never overwrite an existing results file — old runs are immutable."""
    if not p.exists():
        return p
    for k in range(1, 1000):
        alt = p.with_name(f"{p.stem}_{k}{p.suffix}")
        if not alt.exists():
            return alt
    raise RuntimeError(f"could not find a free results filename for {p}")


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

    valid = [r for r in results if r["phase"] == "done" and r["candidate_count_ok"]]
    scores = [r["winner_score"] for r in valid if r["winner_score"] is not None]
    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": args.model,
        "protocol": {
            "version": PROTOCOL_VERSION,
            "candidates_per_brief": EXPECTED_CANDIDATES,
            "control_variations": CONTROL_VARIATIONS,
            "note": "runs before 2026-07-26 were protocol v0.1: single-candidate "
                    "(base+variation merged); not comparable to v0.2 results",
        },
        "n": len(results),
        "completed": len(valid),
        "failed": sum(1 for r in results if r["phase"] != "done"),
        "invalid_candidate_count": sum(1 for r in results
                                       if r["phase"] == "done"
                                       and not r["candidate_count_ok"]),
        "mean_score": round(statistics.mean(scores), 2) if scores else None,
        "median_score": statistics.median(scores) if scores else None,
        "auto_improved_count": sum(1 for r in valid if r["auto_improved"]),
        "mean_latency_s": round(statistics.mean(r["latency_s"] for r in results), 1),
        "results": results,
    }
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = unique_path(RESULTS / f"{stamp}_{args.model.replace(':', '_')}.json")
    out.write_text(json.dumps(summary, indent=1))

    md = [f"# Bench {stamp} — {args.model} (protocol v{PROTOCOL_VERSION}, "
          f"{EXPECTED_CANDIDATES} candidates/brief)",
          f"- briefs: {summary['n']} · done+valid: {summary['completed']} · "
          f"failed: {summary['failed']} · invalid-count: {summary['invalid_candidate_count']}",
          f"- mean score: {summary['mean_score']} · median: {summary['median_score']}",
          f"- auto-improved winners: {summary['auto_improved_count']}",
          f"- mean latency: {summary['mean_latency_s']}s", "",
          "| id | cat | phase | cands ok | score | improved | latency |",
          "|---|---|---|---|---|---|---|"]
    md += [f"| {r['id']} | {r['category']} | {r['phase']} | "
           f"{'yes' if r['candidate_count_ok'] else 'NO'} | {r['winner_score']} | "
           f"{'yes' if r['auto_improved'] else ''} | {r['latency_s']}s |" for r in results]
    unique_path(out.with_suffix(".md")).write_text("\n".join(md), encoding="utf-8")
    print(f"\nwrote {out.name}: mean {summary['mean_score']} over "
          f"{summary['completed']}/{summary['n']} valid briefs")


if __name__ == "__main__":
    main()
