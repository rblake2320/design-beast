import json
from pathlib import Path
import subprocess
import sys


BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))
import beast_loop_custody as custody


PROTOCOL = json.loads((BENCH / "beast-loop-protocol.json").read_text(encoding="utf-8"))


def init_repo(tmp_path: Path) -> tuple[Path, Path, list[Path]]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    envelope = repo / "envelope.json"
    envelope.write_text(json.dumps({"model": "frozen", "tools": ["cli"]}), encoding="utf-8")
    implementation = []
    for name in ("protocol.json", "scorer.py", "compiler.py"):
        path = repo / name
        path.write_text(name, encoding="utf-8")
        implementation.append(path)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "freeze base"], check=True)
    return repo, envelope, implementation


def make_registry(tmp_path: Path, freeze: dict) -> Path:
    tasks = []
    for index in range(9):
        source = tmp_path / f"source-{index}.bin"
        oracle = tmp_path / f"oracle-{index}.json"
        receipt = tmp_path / f"selection-{index}.json"
        source.write_bytes(f"source-{index}".encode())
        oracle.write_text(json.dumps({"answer": index}), encoding="utf-8")
        receipt.write_text(json.dumps({"selected": index}), encoding="utf-8")
        tasks.append({
            "task_id": f"task-{index}",
            "domain": f"domain-{index // 3}",
            "source_path": str(source),
            "oracle_path": str(oracle),
            "oracle_id": f"oracle-{index}",
            "selection_receipt_path": str(receipt),
            "selected_after_freeze": True,
            "visual_only_fact_count": 1,
            "ambiguous_segment_count": 1,
        })
    registry = tmp_path / "registry.json"
    authority_receipt = tmp_path / "user-selection.json"
    authority_receipt.write_text(json.dumps({"selected_after_freeze": True}), encoding="utf-8")
    registry.write_text(json.dumps({
        "schema": "beast.loop-task-registry/v2",
        "experiment_id": "test-experiment",
        "freeze_fingerprint": freeze["freeze_fingerprint"],
        "selection_role": "user_trust_root",
        "selected_by": "test-user",
        "selection_method": "user_supplied_undisclosed_after_freeze",
        "user_selection_receipt_path": str(authority_receipt),
        "selector_attestation": {
            "identity_kind": "user",
            "selected_after_freeze": True,
            "candidate_pool_not_discussed_with_current_fleet": True,
            "no_prior_access_to_frozen_beast_packs": True,
            "no_prior_access_to_watch_evidence": True,
            "no_prior_access_to_mesh_candidate_discussion": True,
        },
        "tasks": tasks,
    }), encoding="utf-8")
    return registry


def test_freeze_seal_and_result_chain(tmp_path):
    repo, envelope, implementation = init_repo(tmp_path)
    freeze = custody.create_freeze(repo, envelope, implementation)
    assert not custody.verify_freeze(repo, freeze)
    registry = make_registry(tmp_path, freeze)
    seal = custody.create_seal(repo, freeze, registry, PROTOCOL, seed="fixed-seed")
    assert seal["expected_runs"] == 81
    assert not custody.verify_seal(seal)

    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    artifact = artifact_root / "run-1.txt"
    artifact.write_text("real output", encoding="utf-8")
    expected = seal["schedule"][0]
    row_path = tmp_path / "row.json"
    row_path.write_text(json.dumps({
        **expected,
        "hard_gates": {gate["id"]: True for gate in PROTOCOL["hard_gates"]},
        "metrics": {
            "wall_clock_seconds": 1, "tool_calls": 1, "retries": 0,
            "human_interventions": 0, "unsupported_claims": 0,
            "visual_only_claims": 1, "visual_only_true_positive": 1,
            "reinspection_required": 1, "reinspection_triggered": 1,
            "acceptance_assertions_passed": 1, "acceptance_assertions_total": 1,
            "oom_count": 0,
        },
        "artifacts": [{"path": artifact.name, "sha256": custody.digest_file(artifact)}],
    }), encoding="utf-8")
    results = tmp_path / "results.jsonl"
    custody.append_result(seal, results, row_path, artifact_root)
    records = custody._read_records(results)
    assert not custody.verify_result_chain(seal, records, artifact_root)

    artifact.write_text("tampered", encoding="utf-8")
    errors = custody.verify_result_chain(seal, records, artifact_root)
    assert any("artifact hash mismatch" in error for error in errors)


def test_freeze_rejects_dirty_worktree_and_placeholders(tmp_path):
    repo, envelope, implementation = init_repo(tmp_path)
    (repo / "dirty.txt").write_text("dirty", encoding="utf-8")
    try:
        custody.create_freeze(repo, envelope, implementation)
    except custody.CustodyError as exc:
        assert "clean worktree" in str(exc)
    else:
        raise AssertionError("dirty freeze should fail")

    (repo / "dirty.txt").unlink()
    envelope.write_text(json.dumps({"model": "TBD"}), encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "envelope.json"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "placeholder envelope"], check=True)
    try:
        custody.create_freeze(repo, envelope, implementation)
    except custody.CustodyError as exc:
        assert "unresolved" in str(exc)
    else:
        raise AssertionError("placeholder freeze should fail")


def test_seal_rejects_current_fleet_or_generic_reviewer_selector(tmp_path):
    repo, envelope, implementation = init_repo(tmp_path)
    freeze = custody.create_freeze(repo, envelope, implementation)
    registry = make_registry(tmp_path, freeze)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["selection_role"] = "independent_reviewer"
    registry.write_text(json.dumps(payload), encoding="utf-8")
    try:
        custody.create_seal(repo, freeze, registry, PROTOCOL, seed="fixed")
    except custody.CustodyError as exc:
        assert "user trust root or external sequestered selector" in str(exc)
    else:
        raise AssertionError("self-selected task registry should fail")


def test_seal_rejects_selector_with_prior_beast_or_mesh_access(tmp_path):
    repo, envelope, implementation = init_repo(tmp_path)
    freeze = custody.create_freeze(repo, envelope, implementation)
    registry = make_registry(tmp_path, freeze)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["selector_attestation"]["no_prior_access_to_mesh_candidate_discussion"] = False
    registry.write_text(json.dumps(payload), encoding="utf-8")
    try:
        custody.create_seal(repo, freeze, registry, PROTOCOL, seed="fixed")
    except custody.CustodyError as exc:
        assert "does not establish task sequestration" in str(exc)
    else:
        raise AssertionError("contaminated selector should fail")


def test_fresh_agent_selector_requires_birth_id_and_entropy_receipt(tmp_path):
    repo, envelope, implementation = init_repo(tmp_path)
    freeze = custody.create_freeze(repo, envelope, implementation)
    registry = make_registry(tmp_path, freeze)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["selection_role"] = "external_sequestered_selector"
    payload["selection_method"] = "deterministic_external_pool_postfreeze_entropy"
    payload["external_pool_receipt_path"] = payload.pop("user_selection_receipt_path")
    payload["selector_attestation"]["identity_kind"] = "fresh_agent"
    registry.write_text(json.dumps(payload), encoding="utf-8")
    try:
        custody.create_seal(repo, freeze, registry, PROTOCOL, seed="fixed")
    except custody.CustodyError as exc:
        assert "birth_id" in str(exc)
    else:
        raise AssertionError("fresh agent without birth ID should fail")

    payload["selector_attestation"]["birth_id"] = "fresh-selector-test-001"
    registry.write_text(json.dumps(payload), encoding="utf-8")
    try:
        custody.create_seal(repo, freeze, registry, PROTOCOL, seed="fixed")
    except custody.CustodyError as exc:
        assert "required file does not exist" in str(exc)
    else:
        raise AssertionError("deterministic selection without entropy receipt should fail")
