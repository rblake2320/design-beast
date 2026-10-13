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



NOW = 1_000_000.0
REMOTE_POLICY = {
    "gpu": {"expected_total_mib": 32607, "protected_reserve_mib": 4096, "unknown_state_policy": "deny"},
    "remote_gpu": {"expected_total_mib": 0, "protected_reserve_mib": 4096,
                   "unknown_state_policy": "deny", "max_measurement_age_seconds": 10,
                   "host_id": "spark-3173", "device_id": "GPU-remote"},
    "workloads": {
        "light": {"requested_mib": 8192, "class": "light"},
        "tunnel_generation": {"requested_mib": 8192, "class": "light", "execution": "remote", "host": "spark-3173"},
        "broken": {"requested_mib": 8192, "class": "light", "execution": "elsewhere"},
        "nohost": {"requested_mib": 8192, "class": "light", "execution": "remote", "host": "spark-3cdf"},
    },
}


def remote_reading(free: int, host: str = "spark-3173", age: float = 0.0, device: str = "GPU-remote") -> dict:
    state = snapshot(free)
    state.update(total_mib=119000, used_mib=119000 - free, host_id=host, device_id=device,
                 measured_unix=NOW - age, units="MiB")
    return state


def test_remote_stage_ignores_local_gpu_state():
    result = resource_guard.evaluate_stage(snapshot(1000), remote_reading(20000), REMOTE_POLICY,
                                           "tunnel_generation", stage="generation", now=NOW)
    assert result["admitted"]
    assert result["execution"] == "remote" and result["host"] == "spark-3173"
    assert result["stage"] == "generation"
    assert result["automatic_process_termination"] is False


def test_remote_stage_refuses_without_remote_measurement():
    result = resource_guard.evaluate_stage(snapshot(30000), None, REMOTE_POLICY,
                                           "tunnel_generation", now=NOW)
    assert not result["admitted"]
    assert "unavailable" in " ".join(result["reasons"])


def test_remote_unknown_state_denied_even_if_local_policy_allows():
    policy = {**REMOTE_POLICY, "gpu": {**REMOTE_POLICY["gpu"], "unknown_state_policy": "allow"}}
    result = resource_guard.evaluate_stage(snapshot(30000), {"available": False, "error": "ssh timeout"},
                                           policy, "tunnel_generation", now=NOW)
    assert not result["admitted"]


def test_remote_stage_rejects_short_remote_free():
    result = resource_guard.evaluate_stage(snapshot(30000), remote_reading(10000), REMOTE_POLICY,
                                           "tunnel_generation", now=NOW)
    assert not result["admitted"]
    assert "need 12288 MiB free" in " ".join(result["reasons"])


def test_remote_stage_refuses_wrong_host_reading():
    result = resource_guard.evaluate_stage(snapshot(30000), remote_reading(30000, host="spark-3cdf"),
                                           REMOTE_POLICY, "tunnel_generation", now=NOW)
    assert not result["admitted"]
    assert "does not match declared host" in " ".join(result["reasons"])


def test_remote_stage_refuses_stale_reading():
    result = resource_guard.evaluate_stage(snapshot(30000), remote_reading(30000, age=60),
                                           REMOTE_POLICY, "tunnel_generation", now=NOW)
    assert not result["admitted"]
    assert "stale refused" in " ".join(result["reasons"])


def test_remote_stage_refuses_future_dated_reading():
    result = resource_guard.evaluate_stage(snapshot(30000), remote_reading(30000, age=-60),
                                           REMOTE_POLICY, "tunnel_generation", now=NOW)
    assert not result["admitted"]


def test_remote_workload_declaring_other_host_fails_closed():
    try:
        resource_guard.evaluate_stage(snapshot(30000), remote_reading(30000), REMOTE_POLICY, "nohost", now=NOW)
    except ValueError as exc:
        assert "declares host" in str(exc)
    else:
        raise AssertionError("remote workload without a host was accepted")


def test_remote_workload_without_remote_policy_fails_closed():
    policy = {k: v for k, v in REMOTE_POLICY.items() if k != "remote_gpu"}
    try:
        resource_guard.evaluate_stage(snapshot(30000), remote_reading(30000), policy, "tunnel_generation", now=NOW)
    except ValueError as exc:
        assert "remote_gpu" in str(exc)
    else:
        raise AssertionError("remote workload admitted without remote_gpu policy")


def test_local_judge_after_remote_generation_still_uses_local_gate():
    generation = resource_guard.evaluate_stage(snapshot(1000), remote_reading(30000), REMOTE_POLICY,
                                               "tunnel_generation", stage="generation", now=NOW)
    judge = resource_guard.evaluate_stage(snapshot(4000), remote_reading(30000), REMOTE_POLICY,
                                          "light", stage="judge", now=NOW)
    assert generation["admitted"]
    assert not judge["admitted"]
    assert judge["execution"] == "local" and judge["stage"] == "judge"


def test_local_workload_ignores_remote_snapshot():
    result = resource_guard.evaluate_stage(snapshot(4000), remote_reading(30000), REMOTE_POLICY, "light", now=NOW)
    assert not result["admitted"]
    assert result["execution"] == "local"


def test_unknown_execution_target_and_stage_are_rejected():
    for call in (
        lambda: resource_guard.evaluate_stage(snapshot(30000), None, REMOTE_POLICY, "broken", now=NOW),
        lambda: resource_guard.evaluate_stage(snapshot(30000), None, REMOTE_POLICY, "light", stage="upscale", now=NOW),
    ):
        try:
            call()
        except ValueError:
            continue
        raise AssertionError("invalid execution target or stage was accepted")


def test_probe_contract_cases_are_refused():
    """Each invalid snapshot class from the Codex DB probe is refused."""
    bad = {
        "stale_24h": remote_reading(30000, age=86400),
        "missing_timestamp": {k: v for k, v in remote_reading(30000).items() if k != "measured_unix"},
        "wrong_host": remote_reading(30000, host="different-host"),
        "wrong_device": remote_reading(30000, device="GPU-other"),
        "free_above_total": {**remote_reading(30000), "free_mib": 150000, "used_mib": 0},
        "wrong_units": {**remote_reading(30000), "units": "bytes"},
        "available_string_false": {**remote_reading(30000), "available": "false"},
        "available_string_true": {**remote_reading(30000), "available": "true"},
        "inconsistent_used_free": {**remote_reading(30000), "used_mib": 1},
        "future_dated": remote_reading(30000, age=-600),
        "float_free": {**remote_reading(30000), "free_mib": 30000.5},
    }
    for name, reading in bad.items():
        result = resource_guard.evaluate_stage(snapshot(30000), reading, REMOTE_POLICY,
                                               "tunnel_generation", now=NOW)
        assert not result["admitted"], name
        assert result["automatic_process_termination"] is False, name


def test_fresh_positive_and_low_vram_controls_still_behave():
    positive = resource_guard.evaluate_stage(snapshot(1000), remote_reading(30000), REMOTE_POLICY,
                                             "tunnel_generation", now=NOW)
    low = resource_guard.evaluate_stage(snapshot(30000), remote_reading(10000), REMOTE_POLICY,
                                        "tunnel_generation", now=NOW)
    assert positive["admitted"]
    assert not low["admitted"]


def test_local_string_available_is_not_treated_as_available():
    state = snapshot(30000)
    state["available"] = "false"
    assert not resource_guard.evaluate(state, POLICY, "light")["admitted"]


def test_remote_policy_without_identity_fails_closed():
    policy = {**REMOTE_POLICY, "remote_gpu": {k: v for k, v in REMOTE_POLICY["remote_gpu"].items() if k != "host_id"}}
    try:
        resource_guard.evaluate_stage(snapshot(30000), remote_reading(30000), policy, "tunnel_generation", now=NOW)
    except ValueError as exc:
        assert "host_id/device_id" in str(exc)
    else:
        raise AssertionError("remote admitted without a bound host identity")
