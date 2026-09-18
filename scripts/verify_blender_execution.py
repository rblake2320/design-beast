"""One-command, real CPU Blender acceptance matrix. Never overwrites an old run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from beast.blender_runner import atomic_json, digest, read_json
from studio import config

EXPECTED_CASES = ["no-authority", "blockout", "bent-grid", "version-drift", "noop-bend"]


def acceptance_state(cases, *, complete=False):
    closed = complete and [c["case"] for c in cases] == EXPECTED_CASES
    return {"schema": "beast.blender.acceptance/v1", "status": "complete" if closed else "running",
            "ok": bool(closed and all(c["passed"] for c in cases)),
            "expected_cases": EXPECTED_CASES, "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--blender", default=config.get("blender"))
    parser.add_argument("--allow-execute", action="store_true")
    args = parser.parse_args()
    if not args.allow_execute:
        parser.error("--allow-execute is required for this real engine test")
    output = args.output.absolute()
    output.mkdir(exist_ok=False)
    cases = []
    atomic_json(output / "acceptance.json", acceptance_state(cases))
    for name, example, permitted, expected in (
        ("no-authority", "blockout", False, 2),
        ("blockout", "blockout", True, 0),
        ("bent-grid", "bent-grid", True, 0),
        ("version-drift", "blockout", True, 1),
        ("noop-bend", "bent-grid", True, 1),
    ):
        plan = read_json(REPO / "examples" / "blender" / f"{example}.json")
        if name == "version-drift":
            plan["blender_version"] = "0.0.0"
        if name == "noop-bend":
            plan["steps"][-1]["axis"] = "Y"
        source = output / f"{name}.json"
        atomic_json(source, plan)
        command = [sys.executable, str(REPO / "scripts" / "blender_execute.py"), str(source),
                   "--output", str(output / name), "--blender", args.blender]
        if permitted:
            command.append("--allow-execute")
        run = subprocess.run(command, capture_output=True, text=True, timeout=270,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        result = json.loads(run.stdout)
        passed = run.returncode == expected
        if name == "no-authority":
            passed = passed and not (output / name).exists() and result["status"] == "rejected"
        else:
            receipt = read_json(output / name / "receipt.json")
            passed = passed and receipt["ok"] == (expected == 0)
            for filename, info in receipt["artifacts"].items():
                passed = passed and digest(output / name / filename) == info["sha256"]
            if name == "version-drift":
                passed = passed and not (output / name / "scene.blend").exists()
            if name == "noop-bend":
                passed = passed and receipt.get("gates", {}).get("Ribbon.bend_effect") is False
        cases.append({"case": name, "passed": bool(passed), "command": command,
                      "returncode": run.returncode, "stdout": run.stdout, "stderr": run.stderr})
        atomic_json(output / "acceptance.json", acceptance_state(cases))
    atomic_json(output / "acceptance.json", acceptance_state(cases, complete=True))
    print(json.dumps({"ok": all(c["passed"] for c in cases), "cases": len(cases), "output": str(output)}))
    return 0 if all(c["passed"] for c in cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
