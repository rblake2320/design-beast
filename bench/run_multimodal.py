"""Run fixed edit, image-to-video, or image-to-3D benchmark tasks.

Sources are explicit and immutable for a run:
    {"prod-01": "runs/<image-bench-job>/final.png", ...}

This runner never enables cloud/hosted fallback. It records failures instead of
silently substituting a different source or backend.
"""
import argparse
import json
import time
from pathlib import Path

import requests

B = "http://127.0.0.1:8787"
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
TERMINAL = {"done", "failed", "cancelled"}


def poll(job_id: str, timeout_s: int, sleep_s: int = 5) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = requests.get(f"{B}/api/run/{job_id}", timeout=30).json()
        if status.get("phase") in TERMINAL:
            return status
        time.sleep(sleep_s)
    return {"id": job_id, "phase": "timeout", "error": "runner timeout"}


def submit(task: dict, group: str, source: str) -> dict:
    if group == "edit_tasks":
        endpoint = "/api/refine"
        body = {"file": source, "instruction": task["instruction"],
                "brief": task["criterion"], "allow_cloud_fallback": False}
        timeout_s = 1200
    elif group == "i2v_tasks":
        endpoint = "/api/animate"
        body = {"file": source, "motion": task["motion"], "duration": 3,
                "quality": "fast", "allow_cloud_fallback": False}
        timeout_s = 4200
    else:
        endpoint = "/api/to3d"
        body = {"file": source, "allow_hosted_fallback": False}
        timeout_s = 3000
    started = time.time()
    response = requests.post(f"{B}{endpoint}", json=body, timeout=30)
    if not response.ok:
        return {"id": task["id"], "source_brief": task["source_brief"],
                "phase": "submit_failed", "error": response.text[:500],
                "latency_s": round(time.time() - started, 1)}
    job_id = response.json()["id"]
    status = poll(job_id, timeout_s)
    result = {"id": task["id"], "source_brief": task["source_brief"],
              "source": source, "job": job_id, "phase": status.get("phase"),
              "error": status.get("error"),
              "latency_s": round(time.time() - started, 1),
              "final": status.get("final")}
    if group == "edit_tasks" and status.get("phase") == "done" and status.get("final"):
        judged_file = f"runs/{job_id}/{status['final']}"
        judge = requests.post(f"{B}/api/judge",
                              json={"file": judged_file, "brief": task["criterion"]},
                              timeout=120).json()
        result["judge"] = {k: judge.get(k) for k in ("score", "kill", "fix")}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", required=True, choices=("edit", "i2v", "i23d"))
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--ids", default="")
    args = parser.parse_args()
    group = {"edit": "edit_tasks", "i2v": "i2v_tasks", "i23d": "i23d_tasks"}[args.suite]
    tasks = json.loads((HERE / "multimodal_tasks.json").read_text())[group]
    sources = json.loads(args.sources.read_text())
    wanted = {value for value in args.ids.split(",") if value}
    if wanted:
        tasks = [task for task in tasks if task["id"] in wanted]
    missing = sorted({task["source_brief"] for task in tasks} - sources.keys())
    if missing:
        raise SystemExit(f"source map missing brief IDs: {', '.join(missing)}")
    results = []
    for index, task in enumerate(tasks, 1):
        print(f"[{index}/{len(tasks)}] {task['id']}", flush=True)
        results.append(submit(task, group, sources[task["source_brief"]]))
    summary = {
        "protocol": "multimodal-0.1",
        "suite": args.suite,
        "source_map": str(args.sources),
        "completed": sum(row["phase"] == "done" for row in results),
        "failed": sum(row["phase"] != "done" for row in results),
        "results": results,
    }
    RESULTS.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    output = RESULTS / f"{stamp}_{args.suite}_multimodal.json"
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
