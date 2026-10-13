import resource_guard


POLICY = {
    "gpu": {
        "expected_total_mib": 32607,
        "protected_reserve_mib": 4096,
        "unknown_state_policy": "deny",
    },
    "workloads": {
        "light": {"requested_mib": 8192, "class": "light"},
        "heavy": {"requested_mib": 24576, "class": "heavy"},
    },
}


def snapshot(free: int) -> dict:
    return {
        "available": True,
        "name": "NVIDIA GeForce RTX 5090",
        "total_mib": 32607,
        "used_mib": 32607 - free,
        "free_mib": free,
        "utilization_percent": 0,
    }


def test_admits_only_when_workload_and_reserve_fit():
    assert resource_guard.evaluate(snapshot(12288), POLICY, "light")["admitted"]
    rejected = resource_guard.evaluate(snapshot(12287), POLICY, "light")
    assert not rejected["admitted"]
    assert rejected["required_free_mib"] == 12288


def test_heavy_is_rejected_under_external_pressure():
    result = resource_guard.evaluate(snapshot(20000), POLICY, "heavy")
    assert not result["admitted"]
    assert "need 28672 MiB free" in result["reasons"][0]


def test_unknown_gpu_state_fails_closed():
    result = resource_guard.evaluate({"available": False, "error": "missing"}, POLICY, "light")
    assert not result["admitted"]


def test_unexpected_gpu_capacity_is_rejected():
    state = snapshot(16000)
    state["total_mib"] = 24000
    assert not resource_guard.evaluate(state, POLICY, "light")["admitted"]


REMOTE_POLICY = {
    "gpu": {"expected_total_mib": 32607, "protected_reserve_mib": 4096, "unknown_state_policy": "deny"},
    "remote_gpu": {"expected_total_mib": 0, "protected_reserve_mib": 4096, "unknown_state_policy": "deny"},
    "workloads": {
        "light": {"requested_mib": 8192, "class": "light"},
        "tunnel_generation": {"requested_mib": 8192, "class": "light", "execution": "remote"},
        "broken": {"requested_mib": 8192, "class": "light", "execution": "elsewhere"},
    },
}


def test_remote_workload_ignores_local_gpu_state():
    local_tight = snapshot(1000)
    remote_free = snapshot(20000)
    remote_free["total_mib"] = 119000
    result = resource_guard.evaluate_stage(local_tight, remote_free, REMOTE_POLICY, "tunnel_generation")
    assert result["admitted"]
    assert result["execution"] == "remote"
    assert result["automatic_process_termination"] is False


def test_remote_workload_refuses_without_remote_measurement():
    result = resource_guard.evaluate_stage(snapshot(30000), None, REMOTE_POLICY, "tunnel_generation")
    assert not result["admitted"]
    assert "remote" in result["reasons"][-1].lower() or "unavailable" in result["reasons"][-1].lower()


def test_remote_unknown_state_is_denied_even_if_local_policy_allows():
    policy = {**REMOTE_POLICY, "gpu": {**REMOTE_POLICY["gpu"], "unknown_state_policy": "allow"}}
    result = resource_guard.evaluate_stage(snapshot(30000), {"available": False, "error": "ssh timeout"}, policy, "tunnel_generation")
    assert not result["admitted"]


def test_remote_workload_is_rejected_when_remote_free_is_short():
    remote = snapshot(10000)
    remote["total_mib"] = 119000
    result = resource_guard.evaluate_stage(snapshot(30000), remote, REMOTE_POLICY, "tunnel_generation")
    assert not result["admitted"]
    assert "need 12288 MiB free" in " ".join(result["reasons"])


def test_remote_workload_fails_closed_without_remote_policy():
    policy = {k: v for k, v in REMOTE_POLICY.items() if k != "remote_gpu"}
    try:
        resource_guard.evaluate_stage(snapshot(30000), snapshot(30000), policy, "tunnel_generation")
    except ValueError as exc:
        assert "remote_gpu" in str(exc)
    else:
        raise AssertionError("remote workload admitted without remote_gpu policy")


def test_local_workload_keeps_local_gate_and_ignores_remote_snapshot():
    remote_free = snapshot(30000)
    remote_free["total_mib"] = 119000
    result = resource_guard.evaluate_stage(snapshot(4000), remote_free, REMOTE_POLICY, "light")
    assert not result["admitted"]
    assert result["execution"] == "local"


def test_unknown_execution_target_is_rejected():
    try:
        resource_guard.evaluate_stage(snapshot(30000), snapshot(30000), REMOTE_POLICY, "broken")
    except ValueError as exc:
        assert "unknown execution target" in str(exc)
    else:
        raise AssertionError("unknown execution target was accepted")
