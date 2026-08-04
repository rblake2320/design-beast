from review.evidence_gate import validate_claim
from exporters.skill_bundle import compile_skill_bundle
import pytest


def test_inferred_claim_without_approval_is_invalid():
    claim = {"review_state": "inferred", "requires_human_approval": False}
    result = validate_claim(claim)
    assert result["valid"] is False


def test_bundle_compile_rejects_unapproved_claims(tmp_path):
    claims = [{"step_id": "1", "review_state": "inferred", "requires_human_approval": False}]
    with pytest.raises(ValueError):
        compile_skill_bundle(claims, {"source_id": "x"}, str(tmp_path / "out.json"))
