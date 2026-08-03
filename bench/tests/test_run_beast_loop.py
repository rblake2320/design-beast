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
        "repetition": 1, "hard_gates": {"execution": True, "evidence": True},
        "metrics": {
            "wall_clock_seconds": seconds, "tool_calls": seconds, "retries": 1,
            "human_interventions": 0, "unsupported_claims": unsupported,
            "visual_only_claims": 1, "visual_only_true_positive": 1,
            "reinspection_required": 1, "reinspection_triggered": 1,
        },
    }


def test_pilot_reports_improvement_without_claiming_breadth():
    report = run_beast_loop.analyze([row("baseline", 20), row("beast", 10)], PROTOCOL, pilot=True)
    assert report["ok"]
    assert report["promotion_eligible"]
    assert report["conditions"]["beast"]["visual_only_fact_precision"] == 1.0
    assert report["pilot"] is True


def test_full_protocol_rejects_one_run_and_one_domain():
    report = run_beast_loop.analyze([row("baseline", 20), row("beast", 10)], PROTOCOL)
    assert not report["ok"]
    assert not report["promotion_eligible"]
    assert any("insufficient materially different domains" in error for error in report["errors"])


def test_unsupported_claim_regression_blocks_promotion():
    report = run_beast_loop.analyze(
        [row("baseline", 20, unsupported=0), row("beast", 10, unsupported=1)],
        PROTOCOL, pilot=True,
    )
    assert not report["promotion_eligible"]
