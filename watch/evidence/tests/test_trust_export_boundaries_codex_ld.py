"""Additional source, serialization and promotion boundary acceptance tests."""
import copy
import json

import pytest

from exporters.skill_bundle import compile_skill_bundle
from review.evidence_gate import validate_claim
from review.provenance_gate import check_source_authorized

from test_trust_codex_ld import owned_case  # noqa: F401 -- shared real-process fixture


@pytest.mark.parametrize("value", [[], {}, ["authorized_owned"], {"state": "authorized_owned"}])
def test_malformed_authorization_is_typed_refusal(value):
    result = check_source_authorized({"authorization_status": value})
    assert result["authorized"] is False
    assert result["reason"]


@pytest.mark.parametrize("field", ["source_id", "sha256", "ingested_at"])
def test_missing_manifest_identity_cannot_export_evidence_backed(tmp_path, owned_case, field):
    source, claim = owned_case
    source.pop(field)
    destination = tmp_path / "missing-source.json"
    with pytest.raises(ValueError):
        compile_skill_bundle([claim], source, str(destination))
    assert not destination.exists()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_extra_metadata_is_refused_before_output(tmp_path, owned_case, value):
    source, claim = owned_case
    claim["provider_metadata"] = {"measurement": value}
    destination = tmp_path / "nonfinite.json"
    with pytest.raises(ValueError):
        compile_skill_bundle([claim], source, str(destination))
    assert not destination.exists()


def test_serialization_refusal_preserves_previous_valid_artifact(tmp_path, owned_case):
    source, claim = owned_case
    destination = tmp_path / "previous.json"
    compile_skill_bundle([claim], source, str(destination))
    before = destination.read_bytes()
    bad = copy.deepcopy(claim)
    bad["provider_metadata"] = {"unsupported": {"non-JSON-object"}}
    with pytest.raises(ValueError):
        compile_skill_bundle([bad], source, str(destination))
    assert destination.read_bytes() == before
    assert json.loads(destination.read_text())["procedure_claims"] == [claim]


def test_success_boolean_cannot_override_failed_exit_receipt(owned_case):
    _, claim = owned_case
    claim["replay_result"].update(success=True, exit_code=7)
    assert validate_claim(claim)["valid"] is False


@pytest.mark.parametrize("claim_state", ["verified", "trusted", "human_approved"])
def test_unrecognized_or_legacy_promotion_state_is_invalid(owned_case, claim_state):
    _, claim = owned_case
    claim["review_state"] = claim_state
    assert validate_claim(claim)["valid"] is False
