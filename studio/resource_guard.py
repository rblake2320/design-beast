"""Live external-aware GPU admission for the single-node Beast runtime.

The SQLite scheduler coordinates Beast jobs. This module closes the separate gap
created by unrelated GPU consumers such as Unreal, Ollama, games, and desktop
applications. It never terminates a process; it only admits or denies new work
from a point-in-time NVIDIA memory measurement.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO / "beast" / "resource-policy.json"
_CACHE: dict[str, Any] = {"at": 0.0, "snapshot": None}


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_gpu_row(row: str) -> dict[str, Any]:
    parts = [part.strip() for part in row.strip().split(",")]
    if len(parts) != 5:
        raise ValueError(f"unexpected nvidia-smi GPU row: {row!r}")
    name, total, used, free, utilization = parts
    return {
        "available": True,
        "name": name,
        "total_mib": int(total),
        "used_mib": int(used),
        "free_mib": int(free),
        "utilization_percent": int(utilization),
        "measured_unix": time.time(),
    }


def measure_gpu(*, timeout: float = 3.0, use_cache: bool = True) -> dict[str, Any]:
    policy = load_policy()
    ttl = float(policy["gpu"].get("measurement_ttl_seconds", 0))
    if use_cache and _CACHE["snapshot"] and time.time() - _CACHE["at"] <= ttl:
        return dict(_CACHE["snapshot"])
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        first = next(line for line in result.stdout.splitlines() if line.strip())
        snapshot = parse_gpu_row(first)
    except (FileNotFoundError, StopIteration, subprocess.SubprocessError, ValueError) as exc:
        snapshot = {
            "available": False,
            "error": str(exc),
            "measured_unix": time.time(),
        }
    _CACHE.update(at=time.time(), snapshot=dict(snapshot))
    return snapshot


def evaluate(
    snapshot: dict[str, Any], policy: dict[str, Any], workload: str
) -> dict[str, Any]:
    if workload not in policy["workloads"]:
        raise ValueError(f"unknown workload: {workload}")
    profile = policy["workloads"][workload]
    requested = int(profile["requested_mib"])
    reserve = int(policy["gpu"]["protected_reserve_mib"])
    required_free = requested + reserve
    reasons: list[str] = []

    if not snapshot.get("available"):
        admitted = policy["gpu"].get("unknown_state_policy") == "allow"
        reasons.append("GPU state unavailable; policy is " + ("allow" if admitted else "deny"))
    else:
        free = int(snapshot["free_mib"])
        admitted = free >= required_free
        if not admitted:
            reasons.append(
                f"need {required_free} MiB free ({requested} workload + {reserve} reserve); "
                f"measured {free} MiB"
            )
        expected_total = int(policy["gpu"].get("expected_total_mib", 0))
        if expected_total and abs(int(snapshot["total_mib"]) - expected_total) > 256:
            admitted = False
            reasons.append(
                f"GPU total {snapshot['total_mib']} MiB differs from expected {expected_total} MiB"
            )
    if admitted:
        reasons.append("live free VRAM satisfies workload budget and protected reserve")
    return {
        "schema": "beast.resource-admission/v1",
        "workload": workload,
        "class": profile["class"],
        "requested_mib": requested,
        "protected_reserve_mib": reserve,
        "required_free_mib": required_free,
        "admitted": admitted,
        "reasons": reasons,
        "snapshot": snapshot,
        "automatic_process_termination": False,
    }


def admission(workload: str, *, use_cache: bool = True) -> dict[str, Any]:
    policy = load_policy()
    return evaluate(measure_gpu(use_cache=use_cache), policy, workload)


EXECUTION_TARGETS = ("local", "remote")


def evaluate_stage(
    local_snapshot: dict[str, Any],
    remote_snapshot: dict[str, Any] | None,
    policy: dict[str, Any],
    workload: str,
) -> dict[str, Any]:
    """Stage-aware admission. Local workloads keep the exact local gate.

    A workload declares ``"execution": "remote"`` when its VRAM is consumed on
    another host (for example a spark-hosted backend reached through a tunnel).
    Such workloads are judged only on a fresh measurement from that remote host
    against ``policy["remote_gpu"]``. The local GPU is never consulted for them,
    and a missing or unreadable remote measurement is a refusal, never an allow.
    """
    if workload not in policy["workloads"]:
        raise ValueError(f"unknown workload: {workload}")
    execution = policy["workloads"][workload].get("execution", "local")
    if execution not in EXECUTION_TARGETS:
        raise ValueError(f"unknown execution target for {workload}: {execution}")

    if execution == "local":
        result = evaluate(local_snapshot, policy, workload)
        result["execution"] = "local"
        return result

    if "remote_gpu" not in policy:
        raise ValueError(f"{workload} is remote but policy has no remote_gpu section")
    if remote_snapshot is None or not remote_snapshot.get("available"):
        error = (remote_snapshot or {}).get("error", "no remote measurement supplied")
        remote_policy = {**policy, "gpu": {**policy["remote_gpu"], "unknown_state_policy": "deny"}}
        result = evaluate({"available": False, "error": error}, remote_policy, workload)
    else:
        result = evaluate(remote_snapshot, {**policy, "gpu": policy["remote_gpu"]}, workload)
    result["execution"] = "remote"
    result["reasons"].insert(0, "judged on remote host measurement; local GPU not consulted")
    return result
