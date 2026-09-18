"""Execute a bounded Blender procedure, optionally binding freshly compiled Watch evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from beast.blender_contract import bind_fields, require
from beast.blender_runner import execute, read_json
from studio import config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("procedure", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="new directory; parent must exist")
    parser.add_argument("--blender", default=config.get("blender"))
    parser.add_argument("--allow-execute", action="store_true")
    parser.add_argument("--timeout", type=float, default=120, help="seconds per child, 1..600")
    parser.add_argument("--target", type=Path)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--timeline", type=Path)
    args = parser.parse_args(argv)
    try:
        plan = read_json(args.procedure)
        paths = [args.target, args.observations, args.timeline]
        require(not any(paths) or all(paths), "target, observations and timeline are required together")
        evidence = None
        if all(paths):
            from watch.typed_evidence import compile_typed_state
            state = compile_typed_state(read_json(args.target), read_json(args.observations),
                                        read_json(args.timeline), args.timeline.resolve().parent)
            plan, fields = bind_fields(plan, state)
            evidence = {"state": state, "bound_fields": fields,
                        "boundary": "Unbound scaffold is authored; pixel receipts do not establish semantic correctness."}
        result = execute(plan, args.output, args.blender, allow_execute=args.allow_execute,
                         timeout=args.timeout, evidence=evidence)
        print(json.dumps({"ok": result["ok"], "status": result["status"],
                          "receipt": str(args.output / "receipt.json"), "error": result.get("error")}))
        return 0 if result["ok"] else 1
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        print(json.dumps({"ok": False, "status": "rejected", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
