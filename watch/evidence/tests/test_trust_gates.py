import json

import pytest
from exporters.skill_bundle import compile_skill_bundle
from review.evidence_gate import validate_claim

OK_SOURCE = {"authorization_status": "authorized"}
GOOD = {"step_id": "1", "review_state": "verified_by_execution", "replay_result": {"success": True}}


@pytest.mark.parametrize("replay", [{"success": False}, {}, None, {"success": "true"}, {"success": 1}])
def test_failed_or_malformed_replay_cannot_be_verified(replay):
    assert validate_claim({"review_state": "verified_by_execution", "replay_result": replay})["valid"] is False


def test_successful_replay_is_accepted_control():
    assert validate_claim(GOOD)["valid"] is True


@pytest.mark.parametrize("claims", [[], None])
def test_empty_claims_are_never_exported(tmp_path, claims):
    out = tmp_path / "out.json"
    with pytest.raises(ValueError, match="no procedure claims"):
        compile_skill_bundle(claims or [], OK_SOURCE, str(out))
    assert not out.exists()


@pytest.mark.parametrize("source", [
    {"authorization_status": "unverified_do_not_use"}, {"authorization_status": ""}, {}, None,
])
def test_unauthorized_source_is_refused_fail_closed(tmp_path, source):
    out = tmp_path / "out.json"
    with pytest.raises(ValueError, match="not explicitly authorized"):
        compile_skill_bundle([GOOD], source, str(out))
    assert not out.exists()


def test_failed_replay_claim_blocks_whole_bundle(tmp_path):
    bad = {"step_id": "2", "review_state": "verified_by_execution", "replay_result": {"success": False}}
    with pytest.raises(ValueError, match="review gate"):
        compile_skill_bundle([GOOD, bad], OK_SOURCE, str(tmp_path / "out.json"))


def test_valid_bundle_exports_with_its_claims(tmp_path):
    out = tmp_path / "out.json"
    bundle = compile_skill_bundle([GOOD], OK_SOURCE, str(out))
    assert json.loads(out.read_text())["procedure_claims"] == [GOOD]
    assert bundle["evidence_backed"] is True
