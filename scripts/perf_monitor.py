"""beast perf - live FPS (Intel PresentMon) + GPU temp/fan/clock/power (nvidia-smi).

    python scripts/perf_monitor.py                              # foreground window, until Ctrl+C
    python scripts/perf_monitor.py --process RouteRush.exe --duration 60
    python scripts/perf_monitor.py --pid 1980 --interval 0.5
    python scripts/perf_monitor.py --no-fps --interval 2        # thermals only

fps backend: auto (default) = PresentMon shared service (no elevation) with the console app
as fallback; force with --fps-backend service|console.
Each sample is one JSONL line (schema beast.perf-sample/v2) under session/perf/.
Exit code: 0 when at least one lane produced data, 2 when both lanes were unavailable.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "studio"))
import perf_monitor  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--process", action="append", default=[], metavar="EXE",
                    help="capture this exe name (repeatable); default = foreground window")
    ap.add_argument("--pid", action="append", default=[], type=int, help="capture this pid (repeatable)")
    ap.add_argument("--interval", type=float, default=1.0, help="seconds between samples (default 1)")
    ap.add_argument("--duration", type=float, default=0.0, help="stop after N seconds (default: Ctrl+C)")
    ap.add_argument("--out", type=Path, help="JSONL path (default session/perf/<timestamp>.jsonl)")
    ap.add_argument("--fps-backend", choices=["auto", "service", "console"], default="auto")
    ap.add_argument("--no-fps", action="store_true", help="skip the PresentMon lane")
    ap.add_argument("--no-gpu", action="store_true", help="skip the nvidia-smi lane")
    ap.add_argument("--quiet", action="store_true", help="no per-sample console line")
    args = ap.parse_args(argv)

    out = args.out or REPO / "session" / "perf" / (time.strftime("%Y%m%d_%H%M%S") + ".jsonl")
    summary = perf_monitor.monitor(
        targets=perf_monitor.Targets(pids=args.pid, processes=args.process),
        interval=args.interval, duration=args.duration, out_path=out,
        fps=not args.no_fps, gpu=not args.no_gpu, fps_backend=args.fps_backend,
        printer=None if args.quiet else print,
    )
    print(json.dumps(summary, indent=2))
    fps_ok = summary["fps_lane"].get("available") and summary["frames_seen"] > 0
    gpu_ok = summary["gpu_lane"] and summary["records"] > 0
    return 0 if (fps_ok or gpu_ok) else 2


if __name__ == "__main__":
    raise SystemExit(main())
