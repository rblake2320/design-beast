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
