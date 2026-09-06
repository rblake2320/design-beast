import pytest
from watch.evidence.exporters.skill_bundle import compile_skill_bundle
from watch.evidence.review.evidence_gate import validate_claim


@pytest.mark.parametrize("claims", [[], [{"review_state": "rejected"}],
    [{"review_state": "verified_by_execution"}],
    [{"review_state": "verified_by_execution", "replay_result": {"passed": False}}]])
def test_legacy_false_proof_rejected(tmp_path, claims):
    target = tmp_path / "bundle.json"
    with pytest.raises(ValueError):
        compile_skill_bundle(claims, {"source_id": "test"}, str(target))
    assert not target.exists()


def test_approval_flag_is_not_proof(tmp_path):
    result = compile_skill_bundle([{"review_state": "inferred", "requires_human_approval": True}],
                                  {"source_id": "test"}, str(tmp_path / "bundle.json"))
    assert result["evidence_backed"] is False
    assert result["promotion_allowed"] is False


def test_failed_replay_is_not_valid():
    assert not validate_claim({"review_state": "verified_by_execution",
                              "replay_result": {"passed": False}})["valid"]
