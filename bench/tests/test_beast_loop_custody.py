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
    registry.write_text(json.dumps({
        "schema": "beast.loop-task-registry/v1",
        "experiment_id": "test-experiment",
        "freeze_fingerprint": freeze["freeze_fingerprint"],
        "selection_role": "independent_reviewer",
        "selected_by": "reviewer-a",
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


def test_seal_requires_independent_selector(tmp_path):
    repo, envelope, implementation = init_repo(tmp_path)
    freeze = custody.create_freeze(repo, envelope, implementation)
    registry = make_registry(tmp_path, freeze)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["selection_role"] = "builder"
    registry.write_text(json.dumps(payload), encoding="utf-8")
    try:
        custody.create_seal(repo, freeze, registry, PROTOCOL, seed="fixed")
    except custody.CustodyError as exc:
        assert "independent reviewer" in str(exc)
    else:
        raise AssertionError("self-selected task registry should fail")
