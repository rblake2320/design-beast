"""Shipped-CLI and SQLite checks with retained machine-readable evidence.

python scripts/verify_optimization.py --output .beast/optimization-proof
Defaults to synthetic CPU media and disposable databases, without service restarts
or model calls. --judge opts into one local vision-model call after GPU admission.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import types
import uuid

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "studio"))
from tool_paths import find_tool
import jobs


def command(args: list[str], records: list[dict]) -> subprocess.CompletedProcess:
    started = time.perf_counter()
    try:
        result = subprocess.run(args, cwd=REPO, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        records.append({"command": args, "returncode": None,
                        "elapsed_s": time.perf_counter() - started,
                        "error": f"{type(exc).__name__}: {exc}"})
        raise
    records.append({"command": args, "returncode": result.returncode,
                    "elapsed_s": time.perf_counter() - started,
                    "stdout": result.stdout, "stderr": result.stderr})
    if result.returncode:
        raise RuntimeError(f"command failed: {args[0]} (see receipt)")
    return result


def storage_probe(module, db: Path) -> dict:
    module.DB_PATH = db
    module._LOCAL = threading.local()
    module.init()
    con = module._db()
    con.executemany("INSERT INTO jobs(id,kind,model,brief,phase,created) VALUES (?,?,?,?,?,?)",
                    [(f"history-{i}", "create", "synthetic", "test asset", "done", i)
                     for i in range(20000)])
    con.commit()
    module.recent()  # warm filesystem/SQLite caches in both conditions
    durations = []
    expected = [f"history-{i}" for i in range(19999, 19969, -1)]
    for _ in range(100):
        start = time.perf_counter_ns()
        result = module.recent()
        durations.append((time.perf_counter_ns() - start) / 1e6)
        assert [row["id"] for row in result] == expected
    barrier = threading.Barrier(16)
    key = uuid.uuid4().hex

    def create(_):
        try:
            barrier.wait(timeout=10)
            jid, created = module.create("create", "synthetic", "contention", {}, key)
            return {"id": jid, "created": created}
        except Exception as exc:
            return {"error": type(exc).__name__, "message": str(exc)}
        finally:
            if hasattr(module._LOCAL, "conn"):
                module._LOCAL.conn.close()
                del module._LOCAL.conn

    with ThreadPoolExecutor(max_workers=16) as pool:
        attempts = list(pool.map(create, range(16)))
    jid, _ = module.create("create", "synthetic", "terminal", {})
    module.set_phase(jid, "done")
    module.set_phase(jid, "running")
    terminal_preserved = module.get(jid)["phase"] == "done"
    con.close()
    del module._LOCAL.conn
    return {"history_rows": 20000, "queries": 100, "timings_ms": durations,
            "p50_ms": statistics.median(durations), "p95_ms": sorted(durations)[94],
            "concurrent_requests": attempts, "terminal_preserved": terminal_preserved}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", default="1a7f7ab")
    parser.add_argument("--judge", action="store_true",
                        help="also run the local vision model after live GPU admission")
    args = parser.parse_args()
    # Unique child keeps repeated proofs and failed attempts rather than overwriting.
    output = args.output.resolve() / f"run-{time.time_ns()}"
    output.mkdir(parents=True)
    records = []
    report = {"schema": "beast.optimization-proof/v1", "ok": False,
              "python": sys.version, "platform": platform.platform(),
              "clock": vars(time.get_clock_info("perf_counter")),
              "commands": records, "baseline": args.baseline,
              "scope": "synthetic CPU media and local SQLite; no creative quality claim"}
    try:
        baseline = command(["git", "show", f"{args.baseline}:studio/jobs.py"], []).stdout
        old_jobs = types.ModuleType("baseline_jobs")
        old_jobs.__file__ = str(REPO / "studio/jobs.py")
        exec(compile(baseline, "baseline_jobs.py", "exec"), old_jobs.__dict__)
        with tempfile.TemporaryDirectory(prefix="beast-optimization-") as tmp:
            report["before"] = storage_probe(old_jobs, Path(tmp) / "before.db")
            report["after"] = storage_probe(jobs, Path(tmp) / "after.db")
        attempts = report["after"]["concurrent_requests"]
        assert not any("error" in attempt for attempt in attempts)
        assert len({attempt["id"] for attempt in attempts}) == 1
        assert sum(attempt["created"] for attempt in attempts) == 1
        assert report["after"]["terminal_preserved"]
        ffmpeg, ffprobe = find_tool("ffmpeg"), find_tool("ffprobe")
        if not ffmpeg or not ffprobe:
            raise RuntimeError("FFmpeg and FFprobe must be installed for real media proof")
        command([ffmpeg, "-version"], records)
        command([ffprobe, "-version"], records)
        source = output / "synthetic.mp4"
        command([ffmpeg, "-v", "error", "-f", "lavfi", "-i",
                 "testsrc2=size=320x180:rate=12:duration=3", "-c:v", "libx264",
                 "-threads", "1", str(source)], records)
        bundle = output / "watched"
        command([sys.executable, "scripts/watch_video.py", str(source), "--out", str(bundle),
                 "--periodic", "1", "--height", "240", "--no-transcribe"], records)
        timeline = json.loads((bundle / "timeline.json").read_text(encoding="utf-8"))
        frames = timeline["frames"]
        assert len(frames) >= 3, "watch must retain real extracted frames"
        for frame in frames:
            data = (bundle / frame["file"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == frame["sha256"]
        report["watch_frames"] = len(frames)
        command([sys.executable, "scripts/watch_seek.py", str(bundle), "--at", "1",
                 "--level", "2", "--before", "0.5", "--after", "0.5",
                 "--fps", "2", "--reason", "synthetic verification"], records)
        inspected = json.loads((bundle / "timeline.json").read_text(encoding="utf-8"))
        request = inspected["evidence_requests"][-1]
        assert request["center_seconds"] == 1 and request["new_frames"] >= 1
        assert len(inspected["frames"]) > len(frames)
        for frame in inspected["frames"]:
            assert hashlib.sha256((bundle / frame["file"]).read_bytes()).hexdigest() == frame["sha256"]
        report["reinspection"] = request
        if args.judge:
            import resource_guard
            import judge_image
            report["judge_admission"] = resource_guard.admission("judge", use_cache=False)
            if not report["judge_admission"]["admitted"]:
                raise RuntimeError("insufficient free VRAM for local judge verification")
            started = time.perf_counter()
            report["judge_verdict"] = judge_image.judge(
                str(bundle / frames[0]["file"]),
                "A synthetic video test pattern with clearly separated colored bars.",
                "qwen3-vl:8b")
            report["judge_elapsed_s"] = time.perf_counter() - started
        report["ok"] = True
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        (output / "receipt.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(output / "receipt.json")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
