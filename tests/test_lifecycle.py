import copy
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

from beast import lifecycle


ROOT = Path(__file__).resolve().parents[1]
CLI_SPEC = importlib.util.spec_from_file_location("beast_lifecycle_cli", ROOT / "scripts" / "beast_lifecycle.py")
assert CLI_SPEC and CLI_SPEC.loader
cli = importlib.util.module_from_spec(CLI_SPEC)
CLI_SPEC.loader.exec_module(cli)


def test_cli_evidence_writer_uses_platform_independent_lf_bytes(tmp_path, capsys):
    output = tmp_path / "receipt.json"
    cli.write({"status": "active"}, output)
    assert b"\r\n" not in output.read_bytes()
    assert output.read_bytes().endswith(b"\n")
    assert capsys.readouterr().out.endswith("\n")


def manifest(output):
    fields = ["protocol_version", "toolset_count", "blueprint_dsl_documented"]
    return {
        "pack_id": "test-pack",
        "probe": {"assertions": [
            {"path": "protocol_version", "op": "eq", "value": "2025-06-18"},
            {"path": "toolset_count", "op": "gte", "value": 1},
        ]},
        "fingerprint_fields": fields,
        "baseline": {
            "fingerprint": lifecycle.canonical_hash(lifecycle.selected_facts(output, fields)),
            "verified_at": "2026-08-04T00:00:00+00:00",
            "max_age_days": 30,
        },
    }


def test_drift_demotes_and_blocks_trusted_retrieval():
    output = {"protocol_version": "2025-06-18", "toolset_count": 56, "blueprint_dsl_documented": True}
    enrolled = manifest(output)
    assert lifecycle.assess(enrolled, output, now=datetime(2026, 8, 5, tzinfo=timezone.utc))["status"] == "active"
    drifted = copy.deepcopy(output)
    drifted["toolset_count"] = 55
    result = lifecycle.assess(enrolled, drifted, now=datetime(2026, 8, 5, tzinfo=timezone.utc))
    assert result["status"] == "stale_unproven"
    assert result["trusted_retrieval"] is False
    assert "environment fingerprint drift" in result["failures"]


def test_expired_probe_demotes_even_when_output_matches():
    output = {"protocol_version": "2025-06-18", "toolset_count": 56, "blueprint_dsl_documented": True}
    result = lifecycle.assess(manifest(output), output, now=datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert result["status"] == "stale_unproven"
    assert "verification expired" in result["failures"]


def test_fitness_requires_matched_runs_no_regressions_and_real_gain():
    base = {"task_id": "t", "variant_id": "v", "repetition": 1, "envelope_fingerprint": "same", "hard_gates": {"correct": True}, "unsupported_claims": 0}
    rows = [{**base, "condition": "baseline", "score": 0.5}, {**base, "condition": "candidate", "score": 0.8}]
    assert lifecycle.evaluate_fitness(rows)["promotion_proposal_eligible"] is True
    harmed = copy.deepcopy(rows)
    harmed[1]["score"] = 0.4
    assert lifecycle.evaluate_fitness(harmed)["promotion_proposal_eligible"] is False
    assert lifecycle.evaluate_fitness(rows[1:])["promotion_proposal_eligible"] is False


def test_fitness_rejects_unsupported_claim_even_with_better_score():
    rows = [
        {"task_id": "t", "variant_id": "v", "repetition": 1, "condition": "baseline", "envelope_fingerprint": "x", "hard_gates": {"correct": False}, "unsupported_claims": 0, "score": 0},
        {"task_id": "t", "variant_id": "v", "repetition": 1, "condition": "candidate", "envelope_fingerprint": "x", "hard_gates": {"correct": True}, "unsupported_claims": 1, "score": 1},
    ]
    assert lifecycle.evaluate_fitness(rows)["promotion_proposal_eligible"] is False


def test_practice_envelope_names_coverage_and_retains_failure():
    rows = [{"variant_id": "a", "passed": True}, {"variant_id": "b", "passed": False}]
    result = lifecycle.practice_envelope(rows, ["a", "b", "c"])
    assert result["verified_variants"] == ["a"]
    assert result["failed_variants"] == ["b"]
    assert result["missing_variants"] == ["c"]
    assert result["complete"] is False


def test_curriculum_is_proposal_only():
    graph = json.loads((lifecycle.REPO / "beast" / "capabilities.json").read_text())
    result = lifecycle.curriculum_proposals(graph)
    assert result["proposals"]
    assert result["may_execute"] is False
    assert all(item["authority"] == "human_review_required" for item in result["proposals"])
