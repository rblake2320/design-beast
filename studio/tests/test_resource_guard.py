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
