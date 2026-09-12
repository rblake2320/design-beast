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

from library import albums, dedup, embed, events, faces, inventory, ocr, organize, review, search  # noqa: E402
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
    """(url, model) for the fast tier: batched OpenAI-compatible server when configured."""
    url = args.ollama or config.get("library_review_url") or config.get("ollama_url")
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
                      limit=args.limit, progress=progress))


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


def cmd_status(args):
    store = _store(args)
    _print({"store": "postgres" if store.pg else "sqlite", "counts": store.counts(),
            "queue": store.queue_counts()})


def cmd_requeue(args):
    _print({"requeued": _store(args).requeue(args.stage)})


def cmd_search(args):
    rows = search.search(_store(args), query=args.query, like=args.like, text=args.text, k=args.k,
                         model=config.get("library_embed_model"), person=args.person,
                         date_from=args.date_from, date_to=args.date_to, album=args.album)
    if args.json:
        _print(rows); return
    for r in rows:
        people = f" people={r['people']}" if r["people"] else ""
        print(f"{r['score']:.3f}  {r['path']}\n       {r['taken_at']}  [{r['album']}]{people}  {r['caption'] or ''}")


def cmd_people(args):
    store = _store(args)
    if args.label:
        store.label_person(int(args.label[0]), args.label[1]); store.commit()
    for pid, label, _, n in store.persons():
        print(f"{pid:>4}  {n:>4} faces  {label or '(unlabelled)'}")


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
    p = sub.add_parser("requeue"); p.add_argument("stage", choices=STAGES); p.set_defaults(fn=cmd_requeue)
    p = sub.add_parser("search"); p.add_argument("query", nargs="?"); p.add_argument("--like")
    p.add_argument("--text"); p.add_argument("-k", type=int, default=20); p.add_argument("--person", type=int)
    p.add_argument("--from", dest="date_from"); p.add_argument("--to", dest="date_to")
    p.add_argument("--album"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_search)
    p = sub.add_parser("people"); p.add_argument("--label", nargs=2, metavar=("ID", "NAME")); p.set_defaults(fn=cmd_people)
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
