#!/usr/bin/env python3
"""beast library — organize, dedupe, index, review and search a media collection.

  beast library run  D:\\Photos --dest D:\\Organized     # every stage, then a plan to approve
  beast library scan D:\\Photos                         # inventory + thumbnails (read-only)
  beast library dedup | embed | faces | ocr [--all]
  beast library review --tier fast|deep [--parallel 4] [--ollama http://spark-1:11434/api/generate]
  beast library search "dog beside red truck" [--person 3] [--from 2024-01] [--text receipt]
  beast library people [--label 3 "Grandma"]
  beast library albums                                  # group representatives, name each group once
  beast library plan --dest D:\\Organized · proposals · approve --all|--album X|IDS · apply
  beast library status · requeue STAGE

Store: --db PATH (SQLite, default) or --dsn postgresql://... / BEAST_LIBRARY_DSN (shared,
multi-node). Workers on other machines only need the DSN and their own Ollama.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "studio"))
import config  # noqa: E402

from library import albums, dedup, embed, events, faces, inventory, ocr, organize, recover, review, search  # noqa: E402
from library.store import STAGES, Store  # noqa: E402


def _target(args) -> str:
    return args.dsn or config.get("library_dsn") or args.db or config.get("library_db")


def _store(args) -> Store:
    return Store(_target(args))


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def cmd_scan(args):
    store = _store(args)
    t0 = time.time()
    out = inventory.scan(store, Path(args.root),
                         progress=lambda i, n: print(f"  {i}/{n}", file=sys.stderr))
    out["seconds"] = round(time.time() - t0, 1)
    _print(out)


def cmd_dedup(args):
    _print(dedup.cluster(_store(args), embed_model=None if args.no_embeddings else config.get("library_embed_model")))


def cmd_embed(args):
    _print(embed.run(_store(args), config.get("library_embed_model"), worker=args.worker, limit=args.limit))


def cmd_faces(args):
    _print(faces.run(_store(args), worker=args.worker, limit=args.limit))


def cmd_ocr(args):
    _print(ocr.run(_store(args), worker=args.worker, documents_only=not args.all, limit=args.limit))


def _fast_backend(args):
    """(url, model) for the fast tier: the batched server when it answers, else Ollama — loudly."""
    url = args.ollama or config.get("library_review_url")
    if not url:
        url = review.batched_url_if_up(config.get("library_vllm_url")) or config.get("ollama_url")
        if "/v1/" not in url:
            print(f"  fast tier: batched server {config.get('library_vllm_url')} not listening — "
                  f"falling back to Ollama (~8x slower). See docs/LIBRARY.md to start it.", file=sys.stderr)
    model = config.get("library_review_model") if "/v1/" in url else config.get("library_fast_model")
    return url, model


def cmd_review(args):
    if args.tier == "fast" and not args.model:
        url, model = _fast_backend(args)
    else:
        model = args.model or config.get(f"library_{args.tier}_model")
        url = args.ollama or config.get("ollama_url")
    target = _target(args)

    def progress(stats, path, result):
        print(f"  [{stats['done']}] {Path(path).name}: {result.get('caption', '')[:70]}"
              f"  -> {result.get('suggested_album')} ({result.get('confidence'):.2f})", file=sys.stderr)

    _print(review.run(lambda: Store(target), args.tier, model, url, worker=args.worker,
                      parallel=args.parallel, deep_threshold=args.threshold, deep_all=args.all,
                      limit=args.limit, progress=progress, remote=args.remote))


def cmd_run(args):
    store = _store(args)
    url = args.ollama or config.get("ollama_url")
    target = _target(args)
    report = {"scan": inventory.scan(store, Path(args.root))}
    report["dedup_hash"] = dedup.cluster(store, embed_model=None)
    report["embed"] = embed.run(store, config.get("library_embed_model"), worker=args.worker)
    report["dedup"] = dedup.cluster(store, embed_model=config.get("library_embed_model"))
    if not args.no_faces:
        report["faces"] = faces.run(store, worker=args.worker)
    fast_url, fast_model = _fast_backend(args)
    report["review_fast"] = review.run(lambda: Store(target), "fast", fast_model, fast_url,
                                       worker=args.worker, parallel=args.parallel)
    report["ocr"] = ocr.run(store, worker=args.worker)
    if not args.no_deep:
        report["review_deep"] = review.run(lambda: Store(target), "deep", config.get("library_deep_model"),
                                           url, worker=args.worker, parallel=max(1, args.parallel // 2))
    report["events"] = events.run(store)
    report["albums"] = albums.run(store, url, config.get("library_deep_model"))
    if args.dest:
        report["plan"] = organize.plan(store, Path(args.dest), ollama_url=url)
    report["status"] = store.counts()
    _print(report)


def cmd_watch(args):
    """Keep a folder organized: poll, process only what is new, auto-apply into albums you
    have already approved once; anything that needs a new album waits for you."""
    url = args.ollama or config.get("ollama_url")
    target = _target(args)
    failures = 0
    cycles = 0
    while True:
        cycle = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        try:
            store = Store(target)                       # a fresh connection per cycle: no stale handles
            if cycles % 24 == 0:                        # periodic self-check + rolling backup
                cycle["recover"] = recover.run(store, verify="sample", sample=20)
                cycle["backup"] = recover.backup(store, Path(args.dest) / ".beast" / "backups")
            scanned = inventory.scan(store, Path(args.root))
            cycle["new"] = scanned["added_or_updated"]
            if scanned["added_or_updated"] or store.queue_counts().get("review_fast", {}).get("pending"):
                dedup.cluster(store, embed_model=None)
                embed.run(store, config.get("library_embed_model"), worker=args.worker)
                dedup.cluster(store, embed_model=config.get("library_embed_model"))
                faces.run(store, worker=args.worker)
                fast_url, fast_model = _fast_backend(args)
                cycle["review"] = review.run(lambda: Store(target), "fast", fast_model, fast_url,
                                             worker=args.worker, parallel=args.parallel)
                ocr.run(store, worker=args.worker)
                events.run(store)
                albums.run(store, url, config.get("library_deep_model"))
                cycle["plan"] = organize.plan(store, Path(args.dest), ollama_url=url)
                known = organize.approved_albums(store)
                auto = [p["id"] for p in store.proposals("pending")
                        if p["action"] == "duplicate" or p["action"].startswith("move:") or p["album"] in known]
                organize.approve(store, ids=auto)
                cycle["auto_applied"] = organize.apply(store)
                cycle["awaiting_approval"] = len(store.proposals("pending"))
            store.log("watch.cycle", cycle)
            store.commit(); store.close()
            failures = 0
        except Exception as exc:  # noqa: BLE001 — the loop must outlive any single failure
            failures += 1
            cycle["error"] = f"{type(exc).__name__}: {exc}"[:300]
            try:
                s = Store(target); s.log("watch.error", cycle); s.commit(); s.close()
            except Exception:  # noqa: BLE001
                pass
        print(json.dumps(cycle, default=str), flush=True)
        cycles += 1
        if args.once:
            return
        time.sleep(min(args.interval * (2 ** min(failures, 4)), 3600))   # back off while something is broken


def cmd_recover(args):
    _print(recover.run(_store(args), verify="all" if args.all else "sample"))


def cmd_backup(args):
    _print(recover.backup(_store(args), Path(args.dir)))


def cmd_restore(args):
    target = _target(args)
    if target.startswith("postgres"):
        raise SystemExit("restore is for the SQLite store; for Postgres use pg_restore on the .dump")
    _print(recover.restore(Path(args.backup), Path(target)))


def cmd_rebuild(args):
    _print(recover.rebuild_from_manifest(_store(args), Path(args.dest)))


def cmd_status(args):
    store = _store(args)
    _print({"store": "postgres" if store.pg else "sqlite", "counts": store.counts(),
            "queue": store.queue_counts()})


def cmd_requeue(args):
    _print({"requeued": _store(args).requeue(args.stage)})


def cmd_search(args):
    store = _store(args)
    rows = search.search(store, query=args.query, like=args.like, text=args.text, k=args.k,
                         model=config.get("library_embed_model"),
                         person=_person_id(store, args.person) if args.person else None,
                         date_from=args.date_from, date_to=args.date_to, album=args.album)
    if args.json:
        _print(rows); return
    for r in rows:
        people = f" people={r['people']}" if r["people"] else ""
        print(f"{r['score']:.3f}  {r['path']}\n       {r['taken_at']}  [{r['album']}]{people}  {r['caption'] or ''}")


def _person_id(store, ref: str) -> int:
    if ref.isdigit():
        return int(ref)
    pid = store.person_by_label(ref)
    if pid is None:
        raise SystemExit(f"no person named {ref!r} — `beast library people` lists them")
    return pid


def cmd_people(args):
    store = _store(args)
    if args.label:
        _print(faces.label(store, _person_id(store, args.label[0]), args.label[1])); return
    if args.find:
        _print(faces.find(store, _person_id(store, args.find))); return
    if args.confirm:
        _print(faces.confirm(store, int(args.confirm[0]), _person_id(store, args.confirm[1]))); return
    if args.reject:
        _print(faces.reject(store, int(args.reject[0]), _person_id(store, args.reject[1]))); return
    if args.merge:
        _print(faces.merge(store, _person_id(store, args.merge[0]), _person_id(store, args.merge[1]))); return
    if args.recluster:
        _print(faces.recluster(store)); return
    if args.show:
        pid = _person_id(store, args.show)
        for f in store.faces(person_id=pid):
            a = store.asset(f["asset_id"])
            flag = {2: "confirmed", 1: "auto", 0: "SUGGESTED"}[f["confirmed"]]
            print(f"face {f['id']:>5}  {flag:<9} sim={f['similarity'] or 0:.2f}  {a['path'] if a else '?'}")
        return
    for p in faces.people(store):
        sugg = f"  ({p['suggested']} suggested)" if p["suggested"] else ""
        print(f"{p['id']:>4}  {p['faces']:>4} faces in {p['images']:>4} images  {p['label'] or '(unnamed)'}{sugg}")


def cmd_events(args):
    _print(events.run(_store(args)))


def cmd_albums(args):
    _print(albums.run(_store(args), args.ollama or config.get("ollama_url"),
                      args.model or config.get("library_deep_model")))


def cmd_plan(args):
    _print(organize.plan(_store(args), Path(args.dest), people=not args.no_people,
                         ollama_url=args.ollama or config.get("ollama_url")))


def cmd_proposals(args):
    for p in _store(args).proposals(args.status, args.album):
        print(f"{p['id']:>6} {p['status']:<9} {p['action']:<12} {p['album'] or '-':<28} {p['path']}"
              + (f"\n       -> {p['dest']}" if p["dest"] else f"\n       {p['reason']}"))


def cmd_approve(args):
    _print({"approved": organize.approve(_store(args), ids=[int(i) for i in args.ids],
                                         album=args.album, everything=args.all)})


def cmd_reject(args):
    _print({"rejected": organize.approve(_store(args), ids=[int(i) for i in args.ids],
                                         album=args.album, everything=args.all, status="rejected")})


def cmd_apply(args):
    store = _store(args)
    out = organize.apply(store, hardlink=args.hardlink)
    out["manifest_sha256"] = organize.manifest_hash(store)
    _print(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="beast library", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="SQLite path (default: config library_db)")
    ap.add_argument("--dsn", help="postgresql://... (or BEAST_LIBRARY_DSN)")
    ap.add_argument("--worker", default=os.environ.get("COMPUTERNAME", "local"))
    ap.add_argument("--remote", action="store_true",
                    help="this worker is on another machine: never receives private assets")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("scan"); p.add_argument("root"); p.set_defaults(fn=cmd_scan)
    p = sub.add_parser("dedup"); p.add_argument("--no-embeddings", action="store_true"); p.set_defaults(fn=cmd_dedup)
    for name, fn in (("embed", cmd_embed), ("faces", cmd_faces)):
        p = sub.add_parser(name); p.add_argument("--limit", type=int); p.set_defaults(fn=fn)
    p = sub.add_parser("ocr"); p.add_argument("--all", action="store_true", help="OCR every image, not only documents")
    p.add_argument("--limit", type=int); p.set_defaults(fn=cmd_ocr)
    p = sub.add_parser("review"); p.add_argument("--tier", choices=("fast", "deep"), default="fast")
    p.add_argument("--model"); p.add_argument("--ollama"); p.add_argument("--parallel", type=int, default=2)
    p.add_argument("--threshold", type=float, default=0.7); p.add_argument("--all", action="store_true")
    p.add_argument("--limit", type=int); p.set_defaults(fn=cmd_review)
    p = sub.add_parser("run"); p.add_argument("root"); p.add_argument("--dest")
    p.add_argument("--ollama"); p.add_argument("--parallel", type=int, default=2)
    p.add_argument("--no-faces", action="store_true"); p.add_argument("--no-deep", action="store_true")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("status"); p.set_defaults(fn=cmd_status)
    p = sub.add_parser("watch", help="keep ROOT organized into DEST unattended")
    p.add_argument("root"); p.add_argument("--dest", required=True); p.add_argument("--interval", type=int, default=300)
    p.add_argument("--ollama"); p.add_argument("--parallel", type=int, default=16); p.add_argument("--once", action="store_true")
    p.set_defaults(fn=cmd_watch)
    p = sub.add_parser("recover", help="reclaim stale work, requeue errors, remove partial files, verify placed files")
    p.add_argument("--all", action="store_true", help="re-hash every placed file, not a sample"); p.set_defaults(fn=cmd_recover)
    p = sub.add_parser("backup"); p.add_argument("--dir", required=True); p.set_defaults(fn=cmd_backup)
    p = sub.add_parser("restore"); p.add_argument("backup"); p.set_defaults(fn=cmd_restore)
    p = sub.add_parser("rebuild", help="lost store: rebuild placements from DEST/.beast/manifest.json")
    p.add_argument("--dest", required=True); p.set_defaults(fn=cmd_rebuild)
    p = sub.add_parser("requeue"); p.add_argument("stage", choices=STAGES); p.set_defaults(fn=cmd_requeue)
    p = sub.add_parser("search"); p.add_argument("query", nargs="?"); p.add_argument("--like")
    p.add_argument("--text"); p.add_argument("-k", type=int, default=20); p.add_argument("--person", metavar="ID|NAME")
    p.add_argument("--from", dest="date_from"); p.add_argument("--to", dest="date_to")
    p.add_argument("--album"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_search)
    p = sub.add_parser("people", help="list people; --label ID NAME names one and finds them everywhere")
    p.add_argument("--label", nargs=2, metavar=("ID|NAME", "NEWNAME")); p.add_argument("--find", metavar="ID|NAME")
    p.add_argument("--confirm", nargs=2, metavar=("FACE", "ID|NAME")); p.add_argument("--reject", nargs=2, metavar=("FACE", "ID|NAME"))
    p.add_argument("--merge", nargs=2, metavar=("KEEP", "DROP")); p.add_argument("--recluster", action="store_true")
    p.add_argument("--show", metavar="ID|NAME"); p.set_defaults(fn=cmd_people)
    p = sub.add_parser("events"); p.set_defaults(fn=cmd_events)
    p = sub.add_parser("albums"); p.add_argument("--ollama"); p.add_argument("--model"); p.set_defaults(fn=cmd_albums)
    p = sub.add_parser("plan"); p.add_argument("--dest", required=True); p.add_argument("--ollama")
    p.add_argument("--no-people", action="store_true"); p.set_defaults(fn=cmd_plan)
    p = sub.add_parser("proposals"); p.add_argument("--status"); p.add_argument("--album"); p.set_defaults(fn=cmd_proposals)
    for name, fn in (("approve", cmd_approve), ("reject", cmd_reject)):
        p = sub.add_parser(name); p.add_argument("ids", nargs="*"); p.add_argument("--album")
        p.add_argument("--all", action="store_true"); p.set_defaults(fn=fn)
    p = sub.add_parser("apply"); p.add_argument("--hardlink", action="store_true",
                                                help="share bytes with originals (edits propagate!) instead of copying")
    p.set_defaults(fn=cmd_apply)

    args = ap.parse_args(argv)
    args.fn(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
