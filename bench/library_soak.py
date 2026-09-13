#!/usr/bin/env python3
"""Soak + fault injection for `beast library watch`.

Feeds new photos into a source folder every FEED_EVERY seconds, runs `watch` under a
supervisor, and injects real faults on a schedule:
  * kills the watch process mid-cycle (supervisor restarts it)
  * stops the vLLM container (fast tier must fall back to Ollama, loudly) and restarts it
  * drops a half-written `.beast-partial` file into the organized tree
At the end: `recover --all` and an audit — every fed file placed exactly once, no partials,
integrity ok, cycle/error rows in the ledger. Writes bench/results/library-soak-<date>.json.

  python bench/library_soak.py --seed-dir C:/Users/techai/Pictures --minutes 45
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from library import organize  # noqa: E402
from library.store import Store  # noqa: E402

FEED_EVERY = 90


def sh(*args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-dir", required=True, help="folder of real images to feed from")
    ap.add_argument("--minutes", type=int, default=45)
    ap.add_argument("--work", default=str(REPO / "library" / "data" / "soak"))
    ap.add_argument("--batch", type=int, default=6)
    args = ap.parse_args()

    work = Path(args.work); shutil.rmtree(work, ignore_errors=True)
    src, dest, db = work / "src", work / "dest", work / "soak.db"
    src.mkdir(parents=True); dest.mkdir()
    pool = sorted(p for p in Path(args.seed_dir).rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".heic"))
    random.seed(42); random.shuffle(pool)
    fed: dict[str, str] = {}
    events: list[dict] = []
    log = lambda **e: (events.append({"t": round(time.time() - t0, 1), **e}), print(json.dumps(events[-1]), flush=True))  # noqa: E731

    def feed(n: int):
        for p in pool[len(fed):len(fed) + n]:
            target = src / f"{len(fed):04d}_{p.name}"
            shutil.copy2(p, target)
            fed[str(target)] = hashlib.sha256(target.read_bytes()).hexdigest()
        log(event="feed", total=len(fed))

    def start_watch():
        return subprocess.Popen([sys.executable, str(REPO / "scripts" / "library.py"), "--db", str(db), "watch",
                                 str(src), "--dest", str(dest), "--interval", "45", "--parallel", "8"],
                                stdout=open(work / "watch.log", "a", encoding="utf-8"), stderr=subprocess.STDOUT)

    t0 = time.time()
    feed(args.batch)
    proc = start_watch(); log(event="watch.start", pid=proc.pid)
    deadline = t0 + args.minutes * 60
    next_feed = t0 + FEED_EVERY
    faults = {"first_approval": t0 + 150, "kill": t0 + 300, "vllm_stop": t0 + 480, "vllm_start": t0 + 720,
              "partial": t0 + 960}
    while time.time() < deadline:
        now = time.time()
        if proc.poll() is not None:                      # died (by us or on its own): supervisor restarts
            log(event="watch.exit", code=proc.returncode); proc = start_watch(); log(event="watch.restart", pid=proc.pid)
        if now >= next_feed and len(fed) < len(pool):
            feed(args.batch); next_feed = now + FEED_EVERY
        due = [k for k, when in faults.items() if now >= when and k != "first_approval"]
        for k in due:
            del faults[k]
            if k == "kill":
                proc.kill(); log(event="fault.kill_watch")
            elif k == "vllm_stop":
                log(event="fault.vllm_stop", out=sh("docker", "stop", "beast-vllm").stdout.strip())
            elif k == "vllm_start":
                log(event="fault.vllm_start", out=sh("docker", "start", "beast-vllm").stdout.strip())
            elif k == "partial":
                victims = [p for p in dest.rglob("*.jpg") if ".beast" not in p.parts]
                if victims:
                    v = random.choice(victims); v.unlink()
                    v.with_name(v.name + ".beast-partial").write_bytes(b"half")
                    log(event="fault.partial", file=str(v))
                else:
                    faults["partial"] = now + 120
        # the owner's one-time review: approve whatever is waiting once, so later cycles auto-apply
        if "first_approval" in faults and now >= faults["first_approval"] and db.exists():
            try:
                s = Store(db)
                n = organize.approve(s, everything=True); s.close()
                if n:
                    del faults["first_approval"]; log(event="owner.approve_all", count=n)
            except Exception as exc:  # noqa: BLE001 — the watch loop may hold the write lock
                log(event="owner.approve_retry", error=str(exc)[:80])
        time.sleep(5)
    proc.terminate()
    try:
        proc.wait(20)
    except subprocess.TimeoutExpired:
        proc.kill()
    log(event="watch.stop")

    # ---- audit ----
    rec = json.loads(sh(sys.executable, str(REPO / "scripts" / "library.py"), "--db", str(db), "recover", "--all").stdout)
    log(event="recover", integrity=rec["integrity"], verify=rec.get("verify"), partials=rec["partials_removed"])
    final = sh(sys.executable, str(REPO / "scripts" / "library.py"), "--db", str(db), "watch", str(src), "--dest",
               str(dest), "--once", "--parallel", "8")
    store = Store(db)
    placed = {p["path"]: p["dest"] for p in store.proposals("applied") if p["action"] == "link"}
    pending = len(store.proposals("pending"))
    dup = {p["path"] for p in store.proposals() if p["action"] == "duplicate"}
    missing = [s for s in fed if s not in placed and s not in dup]
    wrong_hash = [s for s, d in placed.items() if d and Path(d).exists()
                  and hashlib.sha256(Path(d).read_bytes()).hexdigest() != fed.get(s, "")]
    partials = list(dest.rglob("*.beast-partial"))
    cycles = store.fetchone("SELECT COUNT(*) FROM ledger WHERE event = 'watch.cycle'")[0]
    errors = [json.loads(r[0]) for r in store.fetchall("SELECT detail FROM ledger WHERE event = 'watch.error'")]
    reclaimed = store.fetchone("SELECT COUNT(*) FROM ledger WHERE event = 'queue.reclaim_stale'")[0]
    verdict = {"fed": len(fed), "placed": len(placed), "duplicates": len(dup), "awaiting_approval": pending,
               "unplaced_and_not_pending": [m for m in missing if m not in {p["path"] for p in store.proposals("pending")}],
               "wrong_hash": wrong_hash, "partials_left": [str(p) for p in partials], "cycles": int(cycles),
               "watch_errors": errors, "stale_reclaims": int(reclaimed), "integrity": store.integrity(),
               "counts": store.counts()}
    fired = {e["event"] for e in events}
    verdict["faults_fired"] = sorted(f for f in fired if f.startswith("fault."))
    verdict["pass"] = (not verdict["unplaced_and_not_pending"] and not wrong_hash and not partials
                       and verdict["integrity"] == "ok" and cycles >= 3 and len(placed) > 0
                       and {"fault.kill_watch", "fault.vllm_stop", "fault.vllm_start", "fault.partial"} <= fired)
    out = REPO / "bench" / "results" / f"library-soak-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps({"minutes": args.minutes, "events": events, "verdict": verdict}, indent=2, default=str),
                   encoding="utf-8")
    print(json.dumps(verdict, indent=2, default=str)); print("wrote", out)
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
