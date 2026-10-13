"""Independent production-path trust controls; real process and file outputs."""
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone

import pytest

from exporters.skill_bundle import compile_skill_bundle
from review.evidence_gate import validate_claim
from review.provenance_gate import check_source_authorized


@pytest.fixture
def owned_case(tmp_path):
    source = tmp_path / "owned-source.txt"
    source.write_text("Owned evidence trust acceptance input\n", encoding="utf-8")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    output = tmp_path / "observed-output.txt"
    result = subprocess.run(
        [sys.executable, "-I", "-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).write_text('completed\\n')", str(output)],
        capture_output=True, text=True, check=True,
    )
    timestamp = datetime.now(timezone.utc).isoformat()
    source_manifest = {"source_id": source_hash, "sha256": source_hash,
                       "authorization_status": "authorized_owned", "ingested_at": timestamp}
    claim = {"step_id": "owned-1", "description": "Owned process wrote the expected output",
             "evidence_event_ids": ["owned-output-1"], "review_state": "verified_by_execution",
             "replay_result": {"success": result.returncode == 0 and output.read_text() == "completed\n",
                               "environment": "owned isolated acceptance process", "timestamp": timestamp,
                               "exit_code": result.returncode,
                               "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}}
    return source_manifest, claim


@pytest.mark.parametrize("status", ["authorized_owned", "authorized_licensed", "authorized_public_domain", "authorized_fair_use_research"])
def test_source_authorized_by_existing_policy_is_exportable(tmp_path, owned_case, status):
    source, claim = owned_case
    source["authorization_status"] = status
    assert check_source_authorized(source)["authorized"] is True
    destination = tmp_path / "accepted.json"
    result = compile_skill_bundle([claim], source, str(destination))
    assert result["source_manifest"]["authorization_status"] == status
    assert json.loads(destination.read_text())["procedure_claims"] == [claim]


@pytest.mark.parametrize("status", ["authorized", "unverified_do_not_use", "", None, "AUTHORIZED_OWNED"])
def test_unknown_or_unauthorized_vocabulary_has_no_export_side_effect(tmp_path, owned_case, status):
    source, claim = owned_case
    source["authorization_status"] = status
    destination = tmp_path / "refused.json"
    with pytest.raises(ValueError):
        compile_skill_bundle([claim], source, str(destination))
    assert not destination.exists()


@pytest.mark.parametrize("replay", [None, {}, False, True, [], "completed", {"success": False}, {"success": 1}, {"success": "true"}])
def test_malformed_or_failed_replay_never_verifies(owned_case, replay):
    _, claim = owned_case
    claim["replay_result"] = replay
    result = validate_claim(claim)
    assert result["valid"] is False
    assert result["errors"]


def test_actual_failed_process_cannot_be_verified_or_exported(tmp_path, owned_case):
    source, claim = owned_case
    result = subprocess.run([sys.executable, "-I", "-c", "raise SystemExit(7)"], capture_output=True)
    assert result.returncode == 7
    claim["replay_result"]["success"] = False
    claim["replay_result"]["exit_code"] = result.returncode
    assert validate_claim(claim)["valid"] is False
    destination = tmp_path / "failed-process.json"
    with pytest.raises(ValueError):
        compile_skill_bundle([claim], source, str(destination))
    assert not destination.exists()


@pytest.mark.parametrize("bad", [None, [], "claim", 1])
def test_non_object_claims_are_classified_invalid(bad):
    result = validate_claim(bad)
    assert result["valid"] is False
    assert result["errors"]


@pytest.mark.parametrize("malformation", ["no_step", "no_description", "empty_description", "no_evidence", "empty_evidence", "wrong_evidence_type"])
def test_unlinked_or_incomplete_claim_has_no_evidence_backed_export(tmp_path, owned_case, malformation):
    source, claim = owned_case
    if malformation == "no_step":
        claim.pop("step_id")
    elif malformation == "no_description":
        claim.pop("description")
    elif malformation == "empty_description":
        claim["description"] = " "
    elif malformation == "no_evidence":
        claim.pop("evidence_event_ids")
    elif malformation == "empty_evidence":
        claim["evidence_event_ids"] = []
    else:
        claim["evidence_event_ids"] = "owned-output-1"
    destination = tmp_path / "unlinked.json"
    with pytest.raises(ValueError):
        compile_skill_bundle([claim], source, str(destination))
    assert not destination.exists()


def test_false_approval_value_is_not_human_approval(owned_case):
    _, claim = owned_case
    claim.update(review_state="inferred", requires_human_approval="false")
    assert validate_claim(claim)["valid"] is False


@pytest.mark.parametrize("source", [None, [], "authorized_owned", 1])
def test_non_object_source_is_refused_without_writing(tmp_path, owned_case, source):
    _, claim = owned_case
    destination = tmp_path / "bad-source.json"
    with pytest.raises(ValueError):
        compile_skill_bundle([claim], source, str(destination))
    assert not destination.exists()


def test_later_invalid_claim_does_not_partially_export(tmp_path, owned_case):
    source, claim = owned_case
    later = copy.deepcopy(claim)
    later.update(step_id="owned-2", review_state="undefined-status")
    destination = tmp_path / "partial.json"
    with pytest.raises(ValueError):
        compile_skill_bundle([claim, later], source, str(destination))
    assert not destination.exists()


def test_duplicate_step_identity_is_refused(tmp_path, owned_case):
    source, claim = owned_case
    destination = tmp_path / "duplicate.json"
    with pytest.raises(ValueError):
        compile_skill_bundle([claim, copy.deepcopy(claim)], source, str(destination))
    assert not destination.exists()
