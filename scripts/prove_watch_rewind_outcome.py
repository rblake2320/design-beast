"""Exhaust native frames and measure counterbalanced known-case reinspection."""
from __future__ import annotations
import argparse
import json
import statistics
import subprocess
import time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.evaluate_watch_rewind import evaluate
from watch.inspection_runtime import digest, retain


def run(review: Path, units: Path, output: Path) -> None:
    source = review / "media/source.mp4"
    source_hash = digest(source)
    output.mkdir(parents=True,exist_ok=False)
    retain(output / "protocol.json", {"source_sha256":source_hash,"pairs":10,
        "order":"alternating baseline-first and rewind-first; five each",
        "speed_pass":"rewind faster in at least 8/10 pairs AND median paired time reduction >=10%",
        "speed_unit":"existing arm extraction+pixel-measurement wall time; excludes setup/copy",
        "action_pass":"reviewer identifies visible initiating input plus control and result from native frames",
        "native_review":"all decoded frames at timestamps 0 <= t < 2 seconds; no sparse sampling",
        "scope":"one known frozen recording; compare mechanisms, no semantic labels supplied to scheduler"})
    try:
        native = output / "native"
        native.mkdir()
        subprocess.run(["ffmpeg","-v","error","-nostdin","-n","-i",str(source.resolve()),
            "-t","2","-fps_mode","passthrough","-q:v","2",str(native / "frame-%03d.jpg")],
            capture_output=True,check=True,timeout=60)
        probe = json.loads(subprocess.run(["ffprobe","-v","error","-select_streams","v:0",
            "-show_frames","-show_entries","frame=best_effort_timestamp_time","-of","json",str(source)],
            capture_output=True,check=True,timeout=60).stdout)
        stamps = [float(f["best_effort_timestamp_time"]) for f in probe["frames"] if float(f["best_effort_timestamp_time"]) < 2]
        paths = sorted(native.glob("frame-*.jpg"))
        if len(paths) != len(stamps): raise ValueError("native frame accounting mismatch")
        retain(native / "manifest.json", {"source_sha256":source_hash,"count":len(paths),
            "frames":[{"file":p.name,"seconds":t,"sha256":digest(p)} for p,t in zip(paths,stamps,strict=True)]})
        # Contact sheets are navigational aids; native JPEGs remain independently inspectable.
        subprocess.run(["ffmpeg","-v","error","-nostdin","-n","-framerate","30","-i",str(native / "frame-%03d.jpg"),
            "-vf","scale=640:360,tile=3x2","-frames:v","10","-q:v","2",str(native / "sheet-%02d.jpg")],
            capture_output=True,check=True,timeout=60)
        pairs = []
        for index in range(10):
            start = time.perf_counter()
            report = evaluate(review,units,output / f"pair-{index:02d}",reverse_order=bool(index%2))
            times = {a["arm"]:a["elapsed_seconds"] for a in report["arms"]}
            baseline,rewind = times["watch-adaptive-bounded"],times["debt-rewind"]
            pairs.append({"index":index,"reverse_order":bool(index%2),"baseline_seconds":baseline,
                "rewind_seconds":rewind,"reduction_fraction":1-rewind/baseline,
                "total_pair_wall_seconds":time.perf_counter()-start})
        median = statistics.median(p["reduction_fraction"] for p in pairs)
        wins = sum(p["rewind_seconds"] < p["baseline_seconds"] for p in pairs)
        if digest(source) != source_hash: raise ValueError("source changed")
        retain(output / "report.json", {"pairs":pairs,"native_frames":len(paths),"faster_pairs":wins,
            "median_paired_reduction_fraction":median,"speed_result":"PASS" if wins>=8 and median>=.1 else "FAIL",
            "action_result":"awaiting_native_frame_review","publication_allowed":False})
    except Exception as exc:
        retain(output / "failure.json",{"status":"incomplete","error":str(exc),"type":type(exc).__name__})
        raise


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("review","units","output"): parser.add_argument("--"+key,type=Path,required=True)
    args=parser.parse_args()
    run(args.review,args.units,args.output)
