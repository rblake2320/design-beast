import json

import pytest
from exporters.skill_bundle import compile_skill_bundle
from review.evidence_gate import validate_claim

OK_SOURCE = {"source_id": "synthetic-src", "sha256": "0" * 64,
             "ingested_at": "2026-10-12T00:00:00+00:00", "authorization_status": "authorized_owned"}
GOOD = {"step_id": "1", "description": "step", "evidence_event_ids": ["ev-1"], "review_state": "verified_by_execution", "replay_result": {"success": True}}


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
    {"authorization_status": "unverified_do_not_use"}, {"authorization_status": "authorized"},
    {"authorization_status": ""}, {}, None,
])
def test_unauthorized_source_is_refused_fail_closed(tmp_path, source):
    out = tmp_path / "out.json"
    with pytest.raises(ValueError, match="not authorized for export"):
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
    assert bundle["review_gate_passed"] is True
    assert bundle["verification_scope"] == {
        "authorization": "declared",
        "references": "IDs_present_unresolved",
        "execution": "reported_receipts_not_independently_verified",
    }
    assert "evidence_backed" not in bundle and "hard_proof_boundary" not in bundle


@pytest.mark.parametrize("status", ["authorized_owned", "authorized_licensed",
                                    "authorized_public_domain", "authorized_fair_use_research"])
def test_each_canonical_authorized_state_exports(tmp_path, status):
    compile_skill_bundle([GOOD], dict(OK_SOURCE, authorization_status=status), str(tmp_path / "out.json"))


def test_non_serializable_claim_writes_nothing(tmp_path):
    claim = dict(GOOD, bad=object())
    out = tmp_path / "unserializable.json"
    with pytest.raises(ValueError, match="nothing written"):
        compile_skill_bundle([claim], OK_SOURCE, str(out))
    assert list(tmp_path.iterdir()) == []


def test_non_finite_number_writes_nothing(tmp_path):
    claim = dict(GOOD, provider_metadata={"measurement": float("nan")})
    out = tmp_path / "nan.json"
    with pytest.raises(ValueError, match="nothing written"):
        compile_skill_bundle([claim], OK_SOURCE, str(out))
    assert list(tmp_path.iterdir()) == []


def test_all_verified_claims_never_upgrade_proof_scope(tmp_path):
    out = tmp_path / "all-verified.json"
    bundle = compile_skill_bundle([GOOD], OK_SOURCE, str(out))
    assert bundle["verification_scope"]["execution"] == "reported_receipts_not_independently_verified"
    assert bundle["verification_scope"]["references"] == "IDs_present_unresolved"
    assert bundle["verification_scope"]["execution"].startswith("reported_receipts_not_")
