"""One entry point joining existing Watch ingestion, measurement, review and draft rendering."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import watch_video, watch_perception, build_watch_review, render_watch_training
from watch.inspection_runtime import retain


def prepare(args: argparse.Namespace) -> Path:
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    retain(output / "intent.json", {"operation": "watch_training_prepare", "source": args.source,
        "bundle": str(args.bundle) if args.bundle else None, "publication_allowed": False})
    try:
        if args.bundle:
            bundle = args.bundle.resolve()
        else:
            options = [args.source, "--out", str(output / "bundle"), "--max-frames", "96",
                       "--periodic", "0.5", "--height", "720", "--no-transcribe"]
            for key in ("start", "end"):
                if getattr(args, key) is not None:
                    options.extend(["--"+key, getattr(args, key)])
            bundle = watch_video.run(watch_video.parser().parse_args(options))
        pixels = args.pixels.resolve() if args.pixels else output / "pixels"
        if not args.pixels:
            watch_perception.run(bundle, pixels, None)
        data = build_watch_review.build(bundle, pixels, output / "review")
        retain(output / "report.json", {"status": "editorial_review_required", "frames": len(data["frames"]),
            "review": "review/index.html", "publication_allowed": False, "generated_visuals": 0,
            "next": "Review actual footage, download the segment plan, then use watch-training render."})
        return output / "review/index.html"
    except Exception as exc:
        retain(output / "failure.json", {"type": type(exc).__name__, "error": str(exc)})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare", help="video or existing Watch bundle -> source-linked review player")
    source = prep.add_mutually_exclusive_group(required=True)
    source.add_argument("--source")
    source.add_argument("--bundle", type=Path)
    prep.add_argument("--pixels", type=Path, help="reuse matching retained measurements; never rerun them")
    prep.add_argument("--start")
    prep.add_argument("--end")
    prep.add_argument("--output", type=Path, required=True)
    render = commands.add_parser("render", help="reviewed editorial plan -> real-footage captioned draft")
    for name in ("review", "plan", "output"):
        render.add_argument("--"+name, type=Path, required=True)
    render.add_argument("--ffmpeg", default="ffmpeg")
    render.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            if args.bundle and (args.start or args.end):
                raise ValueError("existing bundles already define their source range")
            if args.pixels and not args.bundle:
                raise ValueError("retained pixels require their existing bundle")
            result = {"review": str(prepare(args)), "publication_allowed": False}
        else:
            render_watch_training.render(args.review, args.plan, args.output, args.ffmpeg, args.ffprobe)
            result = {"video": str(args.output / "training-draft.mp4"), "publication_allowed": False}
        sys.stdout.write(json.dumps(result)+"\n")
        return 0
    except Exception as exc:
        sys.stderr.write(json.dumps({"error": str(exc), "type": type(exc).__name__})+"\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
