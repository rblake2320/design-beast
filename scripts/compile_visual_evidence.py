"""Compile frame-linked observations into fail-closed typed state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from watch.typed_evidence import TypedEvidenceError, compile_typed_state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        target = json.loads(args.target.read_text(encoding="utf-8"))
        observations = json.loads(args.observations.read_text(encoding="utf-8"))
        timeline = json.loads(args.timeline.read_text(encoding="utf-8"))
        result = compile_typed_state(target, observations, timeline,
                                     args.timeline.resolve().parent)
    except (OSError, json.JSONDecodeError, TypedEvidenceError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": result["status"] == "answered",
                      "status": result["status"],
                      "output": str(args.output),
                      "fingerprint": result["compilation_fingerprint"]}))
    return 0 if result["status"] == "answered" else 1


if __name__ == "__main__":
    raise SystemExit(main())
