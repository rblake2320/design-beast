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

    malformed = _malformed_reasons(snapshot)
    if malformed:
        admitted = False
        reasons.extend(malformed)
    elif snapshot.get("available") is not True:
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
STAGES = ("generation", "judge", "refine", "fallback")
LOCAL_HOST = "local"
_REQUIRED_NUMERIC = ("total_mib", "used_mib", "free_mib")
_CLOCK_SKEW_S = 5.0


def _malformed_reasons(snapshot: dict[str, Any]) -> list[str]:
    """Schema and sanity checks on one measurement. Any reason refuses."""
    reasons: list[str] = []
    if not isinstance(snapshot.get("available"), bool):
        return ["measurement 'available' is not a boolean"]
    if not snapshot["available"]:
        return []
    if snapshot.get("units", "MiB") != "MiB":
        reasons.append(f"measurement units {snapshot.get('units')!r} are not MiB")
    for key in _REQUIRED_NUMERIC:
        value = snapshot.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            reasons.append(f"measurement {key} is missing or not a non-negative integer")
    if reasons:
        return reasons
    total, used, free = snapshot["total_mib"], snapshot["used_mib"], snapshot["free_mib"]
    if free > total or used > total:
        reasons.append(f"measurement impossible: free {free} or used {used} exceeds total {total}")
    elif abs(used + free - total) > 16:
        reasons.append(f"measurement inconsistent: used {used} + free {free} != total {total}")
    return reasons


def _remote_reasons(reading: dict[str, Any], remote_gpu: dict[str, Any], now: float) -> tuple[list[str], float | None]:
    reasons = _malformed_reasons(reading)
    if reasons:
        return reasons, None
    if reading["available"] is not True:
        return ["remote GPU state unavailable; refused, not guessed"], None
    if reading.get("host_id") != remote_gpu["host_id"]:
        reasons.append(f"measurement host {reading.get('host_id')!r} does not match declared host {remote_gpu['host_id']!r}")
    if reading.get("device_id") != remote_gpu["device_id"]:
        reasons.append(f"measurement device {reading.get('device_id')!r} does not match declared device {remote_gpu['device_id']!r}")
    measured = reading.get("measured_unix")
    if not isinstance(measured, (int, float)) or isinstance(measured, bool):
        reasons.append("measurement timestamp missing or not numeric; refused")
        return reasons, None
    age = now - float(measured)
    max_age = float(remote_gpu.get("max_measurement_age_seconds", remote_gpu.get("measurement_ttl_seconds", 0)))
    if max_age <= 0:
        reasons.append("remote policy declares no positive measurement age limit; refused")
    elif age < -_CLOCK_SKEW_S or age > max_age:
        reasons.append(f"remote measurement age {age:.1f}s outside 0..{max_age:g}s; stale refused")
    return reasons, round(age, 3)


def evaluate_stage(
    local_snapshot: dict[str, Any],
    remote_snapshot: dict[str, Any] | None,
    policy: dict[str, Any],
    workload: str,
    *,
    stage: str = "generation",
    now: float | None = None,
) -> dict[str, Any]:
    """Stage-aware admission for one stage of one job. Local workloads keep the
    unchanged local gate, with the same schema checks as every other reading.

    A workload with ``"execution": "remote"`` is judged only on a fresh,
    well-formed measurement whose host_id and device_id equal the identity the
    policy declares in ``policy["remote_gpu"]``. If the workload also names a
    ``host``, it must match that identity. Anything else is refused, and the
    local GPU is never consulted. Each stage is evaluated on its own, so a local
    judge or fallback after remote generation still faces the local gate.
    """
    if workload not in policy["workloads"]:
        raise ValueError(f"unknown workload: {workload}")
    if stage not in STAGES:
        raise ValueError(f"unknown stage: {stage}")
    profile = policy["workloads"][workload]
    execution = profile.get("execution", "local")
    if execution not in EXECUTION_TARGETS:
        raise ValueError(f"unknown execution target for {workload}: {execution}")
    now = time.time() if now is None else now

    if execution == "local":
        result = evaluate(local_snapshot, policy, workload)
        result["execution"] = "local"
        result["stage"] = stage
        result["host"] = LOCAL_HOST
        return result

    remote_gpu = policy.get("remote_gpu")
    if not remote_gpu or not remote_gpu.get("host_id") or not remote_gpu.get("device_id"):
        raise ValueError(f"{workload} is remote but policy remote_gpu lacks host_id/device_id")
    if profile.get("host") not in (None, remote_gpu["host_id"]):
        raise ValueError(f"{workload} declares host {profile.get('host')!r}, policy binds {remote_gpu['host_id']!r}")
    reading = remote_snapshot if isinstance(remote_snapshot, dict) else {"available": False, "error": "no remote measurement supplied"}
    reasons, age = _remote_reasons(reading, remote_gpu, now)
    if reasons:
        result = evaluate({"available": False, "error": "; ".join(reasons)},
                          {**policy, "gpu": {**remote_gpu, "unknown_state_policy": "deny"}}, workload)
    else:
        result = evaluate(reading, {**policy, "gpu": {**remote_gpu, "unknown_state_policy": "deny"}}, workload)
        result["measured_age_s"] = age
    result["reasons"] = ["judged on remote host measurement; local GPU not consulted", *reasons, *result["reasons"]]
    result["execution"] = "remote"
    result["stage"] = stage
    result["host"] = remote_gpu["host_id"]
    return result
