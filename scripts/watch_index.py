"""Build or query the semantic visual index for a Beast Watch bundle."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from watch.visual_index import VisualIndexError, build, search


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle")
    parser.add_argument("query", nargs="?")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--model", default="ViT-B-32")
    parser.add_argument("--pretrained", default="laion2b_s34b_b79k")
    args = parser.parse_args()
    bundle = Path(args.bundle).expanduser().resolve()
    try:
        if args.query:
            print(json.dumps(search(bundle, args.query, args.limit), indent=2))
        else:
            result = build(bundle, args.model, args.pretrained)
            print(f"indexed {result['count']} frames with {result['model']} on {result['device']}")
        return 0
    except VisualIndexError as exc:
        print(f"beast watch-index: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
