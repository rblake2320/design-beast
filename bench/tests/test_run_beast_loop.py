import json
from pathlib import Path
import sys


BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))
import run_beast_loop


PROTOCOL = json.loads((BENCH / "beast-loop-protocol.json").read_text(encoding="utf-8"))


def row(condition: str, seconds: int, *, unsupported: int = 0) -> dict:
    return {
        "task_id": "watch-ui-01", "domain": "unreal", "condition": condition,
        "repetition": 1, "envelope_fingerprint": "frozen-v1",
        "hard_gates": {gate["id"]: True for gate in PROTOCOL["hard_gates"]},
        "metrics": {
            "wall_clock_seconds": seconds, "tool_calls": seconds, "retries": 1,
            "human_interventions": 0, "unsupported_claims": unsupported,
            "visual_only_claims": 1, "visual_only_true_positive": 1,
            "reinspection_required": 1, "reinspection_triggered": 1,
            "acceptance_assertions_passed": 4, "acceptance_assertions_total": 4,
            "oom_count": 0,
        },
    }


def test_pilot_reports_improvement_without_claiming_breadth():
    report = run_beast_loop.analyze(
        [row("baseline", 20), row("adaptive_frames", 15), row("beast", 10)],
        PROTOCOL, pilot=True,
    )
    assert report["ok"]
    assert report["pilot_criteria_met"]
    assert not report["promotion_eligible"]
    assert report["conditions"]["beast"]["visual_only_fact_precision"] == 1.0
    assert report["pilot"] is True


def test_full_protocol_rejects_one_run_and_one_domain():
    report = run_beast_loop.analyze(
        [row("baseline", 20), row("adaptive_frames", 15), row("beast", 10)],
        PROTOCOL,
    )
    assert not report["ok"]
    assert not report["promotion_eligible"]
    assert any("insufficient materially different domains" in error for error in report["errors"])
    assert any("fewer than 3 distinct tasks" in error for error in report["errors"])


def test_unsupported_claim_regression_blocks_promotion():
    report = run_beast_loop.analyze(
        [row("baseline", 20), row("adaptive_frames", 15),
         row("beast", 10, unsupported=1)],
        PROTOCOL, pilot=True,
    )
    assert not report["promotion_eligible"]


def test_mismatched_repetitions_and_envelopes_are_rejected():
    baseline = row("baseline", 20)
    frames = row("adaptive_frames", 15)
    beast = row("beast", 10)
    beast["repetition"] = 2
    beast["envelope_fingerprint"] = "different"
    report = run_beast_loop.analyze([baseline, frames, beast], PROTOCOL, pilot=True)
    assert not report["ok"]
    assert any("condition repetition IDs do not match" in error for error in report["errors"])
    assert any("frozen envelope" in error for error in report["errors"])


def test_missing_gate_or_metric_is_not_silently_scored_as_zero():
    baseline = row("baseline", 20)
    frames = row("adaptive_frames", 15)
    beast = row("beast", 10)
    del beast["hard_gates"]["visual_only_fact"]
    del beast["metrics"]["tool_calls"]
    report = run_beast_loop.analyze([baseline, frames, beast], PROTOCOL, pilot=True)
    assert not report["ok"]
    assert any("missing hard gates" in error for error in report["errors"])
    assert any("missing metrics" in error for error in report["errors"])


def test_beast_must_pass_every_gate_even_if_it_is_faster():
    baseline = row("baseline", 20)
    frames = row("adaptive_frames", 15)
    beast = row("beast", 10)
    beast["hard_gates"]["behavior_executes"] = False
    report = run_beast_loop.analyze([baseline, frames, beast], PROTOCOL, pilot=True)
    assert report["ok"]
    assert not report["promotion_eligible"]


def test_impossible_or_negative_metrics_fail_closed():
    baseline = row("baseline", 20)
    frames = row("adaptive_frames", 15)
    beast = row("beast", 10)
    beast["metrics"]["wall_clock_seconds"] = -1
    beast["metrics"]["visual_only_true_positive"] = 2
    report = run_beast_loop.analyze([baseline, frames, beast], PROTOCOL, pilot=True)
    assert not report["ok"]
    assert any("cannot be negative" in error for error in report["errors"])
    assert any("exceed visual claims" in error for error in report["errors"])


def test_non_boolean_gate_fails_closed():
    baseline = row("baseline", 20)
    frames = row("adaptive_frames", 15)
    beast = row("beast", 10)
    beast["hard_gates"]["artifact_opens"] = "yes"
    report = run_beast_loop.analyze([baseline, frames, beast], PROTOCOL, pilot=True)
    assert not report["ok"]
    assert any("must be booleans" in error for error in report["errors"])


def test_reliability_bound_does_not_overclaim_nine_tasks():
    rows = []
    for task_index in range(9):
        for condition, seconds in (("baseline", 20), ("adaptive_frames", 15), ("beast", 10)):
            for repetition in range(1, 4):
                item = row(condition, seconds)
                item["task_id"] = f"task-{task_index}"
                item["domain"] = f"domain-{task_index // 3}"
                item["repetition"] = repetition
                rows.append(item)
    report = run_beast_loop.analyze(rows, PROTOCOL, custody_verified=True)
    assert report["promotion_eligible"]
    assert report["successful_beast_tasks"] == 9
    assert report["one_sided_95pct_zero_failure_lower_bound"] < 0.90
    assert not report["target_population_reliability_eligible"]


def test_full_report_cannot_promote_without_verified_custody():
    rows = []
    for task_index in range(9):
        for condition, seconds in (("baseline", 20), ("adaptive_frames", 15), ("beast", 10)):
            for repetition in range(1, 4):
                item = row(condition, seconds)
                item["task_id"] = f"task-{task_index}"
                item["domain"] = f"domain-{task_index // 3}"
                item["repetition"] = repetition
                rows.append(item)
    report = run_beast_loop.analyze(rows, PROTOCOL)
    assert report["ok"]
    assert report["custody_verified"] is None
    assert not report["promotion_eligible"]
