"""Record real campaign readiness without spending credits or loading models.

Starts a disposable Studio process with an isolated database, exercises its real
HTTP health/OpenAPI surface, measures live resource admission and stops only that
owned process. This is a preflight, never a creative-output benchmark.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import requests

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "studio"))
import resource_guard


def stop_owned(process, record):
    try:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        record["owned_server_stopped"] = process.poll() is not None
    except (OSError, subprocess.SubprocessError) as exc:
        record.setdefault("cleanup_errors", []).append(f"{type(exc).__name__}: {exc}")
        record["owned_server_stopped"] = False
        record["outcome"] = "preflight_error"


@contextmanager
def owned_server(command, log, record):
    process = subprocess.Popen(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
    record["owned_server_pid"] = process.pid
    try:
        yield process
    finally:
        # Must happen before Windows attempts to delete the temporary database.
        stop_owned(process, record)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    folder = args.out.resolve() / f"preflight-{time.time_ns()}"
    folder.mkdir(parents=True)
    spec = REPO / "bench/campaign-challenge"
    record = {"schema": "beast.campaign-preflight/v1", "phase": "preflight",
              "creative_score": None, "competitive_winner": None,
              "generation_attempts": 0, "paid_calls": 0, "model_calls": 0,
              "test_inputs": {name: hashlib.sha256((spec / name).read_bytes()).hexdigest()
                              for name in ("protocol.json", "BRIEF.md", "reference.png")}}
    process = None
    try:
        record["git_head"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
        snapshot = resource_guard.measure_gpu(use_cache=False)
        policy = resource_guard.load_policy()
        record["admission"] = {name: resource_guard.evaluate(snapshot, policy, name)
                               for name in ("studio_light", "video_generation", "judge")}
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with tempfile.TemporaryDirectory(prefix="beast-campaign-") as tmp:
            bootstrap = (
                "import sys; from pathlib import Path; "
                "sys.path.insert(0,sys.argv[1]); import jobs; "
                "jobs.DB_PATH=Path(sys.argv[2])/'jobs.db'; "
                "import server,uvicorn; "
                "uvicorn.run(server.app,host='127.0.0.1',port=int(sys.argv[3]))")
            with (folder / "studio.log").open("w", encoding="utf-8") as log, owned_server(
                    [sys.executable, "-c", bootstrap, str(REPO / "studio"), tmp, str(port)],
                    log, record) as process:
                base = f"http://127.0.0.1:{port}"
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    try:
                        response = requests.get(base + "/api/health", timeout=1)
                        response.raise_for_status()
                        record["http_health"] = response.json()
                        break
                    except requests.RequestException:
                        if process.poll() is not None:
                            raise RuntimeError("isolated Studio exited; see studio.log")
                        time.sleep(0.1)
                else:
                    raise RuntimeError("isolated Studio did not become healthy in 20 seconds")
                response = requests.get(base + "/openapi.json", timeout=5)
                response.raise_for_status()
                record["api_paths"] = sorted(response.json()["paths"])
                record["outcome"] = ("resource_blocked" if not all(
                    record["admission"][name]["admitted"]
                    for name in ("studio_light", "video_generation")) else "preflight_only_ready")
    except Exception as exc:
        record["outcome"] = "preflight_error"
        record["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if process is not None and process.poll() is None:
            stop_owned(process, record)
        (folder / "receipt.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(folder / "receipt.json")
        print(record.get("outcome"))
    return 0 if record.get("outcome") == "preflight_only_ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
