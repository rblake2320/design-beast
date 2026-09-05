"""Rewind/forward around uncertain Beast Watch evidence at adaptive density."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from watch.core import parse_timecode
from watch.seek import SEEK_LEVELS, SeekError, reinspect, resolve_center

from scripts.tool_paths import find_tool, missing_tool_message


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle")
    center = parser.add_mutually_exclusive_group(required=True)
    center.add_argument("--at", help="original source timestamp")
    center.add_argument("--frame-id")
    parser.add_argument("--level", type=int, choices=SEEK_LEVELS, default=2)
    parser.add_argument("--direction", choices=("back", "forward", "both"), default="both")
    parser.add_argument("--before", type=float)
    parser.add_argument("--after", type=float)
    parser.add_argument("--fps", type=float)
    parser.add_argument("--reason", default="uncertain visual action")
    args = parser.parse_args()
    bundle = Path(args.bundle).expanduser().resolve()
    try:
        timeline = json.loads((bundle / "timeline.json").read_text(encoding="utf-8"))
        at = parse_timecode(args.at) if args.at else None
        selected = resolve_center(timeline, at=at, frame_id=args.frame_id)
        ffmpeg = find_tool("ffmpeg")
        if not ffmpeg:
            raise SeekError(missing_tool_message("ffmpeg"))
        result = reinspect(bundle, ffmpeg, center=selected, level=args.level,
                           direction=args.direction, before=args.before, after=args.after,
                           fps=args.fps, reason=args.reason)
        print(json.dumps(result, indent=2))
        if (bundle / "visual-index.json").exists():
            print("visual index marked stale; rerun beast watch-index for semantic search")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, SeekError) as exc:
        print(f"beast watch-seek: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
