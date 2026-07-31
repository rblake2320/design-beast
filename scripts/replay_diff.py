"""beast replay — name every drifted component between a recorded run and now.

Usage:
  python scripts/replay_diff.py <run-id>            drift report for one run
  python scripts/replay_diff.py <run-id> --json     machine-readable
  python scripts/replay_diff.py --save-baseline     snapshot current env as baseline
  python scripts/replay_diff.py --check             drift vs saved baseline (doctor use)

Exit codes: 0 = no drift, 1 = drift found, 2 = cannot compare (missing data).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "studio"))

import config  # noqa: E402
import env_snapshot  # noqa: E402

RUNS = REPO / "studio" / "runs"
BASELINE = REPO / "studio" / ".beast_env_baseline.json"


def _current(graph: dict | None = None) -> dict:
    comfy_dir = Path(config.get("comfy_dir"))
    return env_snapshot.capture(comfy_dir, comfy_dir / config.get("comfy_python"), graph)


def _recorded(run_id: str) -> dict | None:
    run_dir = RUNS / run_id
    snap = env_snapshot.load(run_dir)
    if snap:
        return snap
    try:
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        return manifest.get("environment")
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_id", nargs="?", help="run id under studio/runs/")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--save-baseline", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="diff current env against the saved baseline")
    args = ap.parse_args()

    if args.save_baseline:
        BASELINE.write_text(json.dumps(_current(), indent=2, sort_keys=True),
                            encoding="utf-8")
        print(f"baseline saved: {BASELINE}")
        return 0

    if args.check:
        if not BASELINE.exists():
            print("no baseline saved — run with --save-baseline first")
            return 2
        recorded = json.loads(BASELINE.read_text(encoding="utf-8"))
        label = "baseline"
    elif args.run_id:
        recorded = _recorded(args.run_id)
        if recorded is None:
            print(f"run {args.run_id}: no environment snapshot recorded "
                  f"(pre-snapshot run, or non-Comfy backend)")
            return 2
        label = f"run {args.run_id}"
    else:
        ap.print_help()
        return 2

    drift = env_snapshot.diff(recorded, _current())
    if args.json:
        print(json.dumps({"compared_to": label, "drift": drift}, indent=2))
    elif drift:
        print(f"DRIFT vs {label} ({len(drift)} component(s)):")
        for line in drift:
            print(f"  - {line}")
        print("\nExact replay is NOT guaranteed. Pin the components above back to "
              "their recorded state, or accept and re-baseline.")
    else:
        print(f"no drift vs {label} — environment matches exactly")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
