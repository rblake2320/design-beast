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
        },
    }


def test_pilot_reports_improvement_without_claiming_breadth():
    report = run_beast_loop.analyze(
        [row("baseline", 20), row("adaptive_frames", 15), row("beast", 10)],
        PROTOCOL, pilot=True,
    )
    assert report["ok"]
    assert report["promotion_eligible"]
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
