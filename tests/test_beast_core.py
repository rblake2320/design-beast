import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "beast_core.py"
SPEC = importlib.util.spec_from_file_location("beast_core", SCRIPT)
assert SPEC and SPEC.loader
beast_core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(beast_core)


def test_repository_beast_contract_validates():
    result = beast_core.validate_all()
    assert result["ok"], result["errors"]
    assert result["capabilities"] >= 8
    assert result["packs"] >= 1


def test_graph_rejects_missing_evidence_and_cycles():
    graph = {
        "schema": "beast.capability-graph/v1",
        "capabilities": [
            {
                "id": "bad", "name": "Bad", "domain": "test", "level": "verified",
                "claim": "claim", "boundary": "boundary", "depends_on": ["bad"],
                "evidence": [], "next_test": "test",
            }
        ],
    }
    errors = beast_core.validate_graph(graph)
    assert any("evidence is required" in error for error in errors)
    assert any("cycle" in error for error in errors)


def test_generalized_requires_breadth():
    graph = {
        "schema": "beast.capability-graph/v1",
        "capabilities": [
            {
                "id": "narrow", "name": "Narrow", "domain": "test",
                "level": "generalized", "claim": "claim", "boundary": "boundary",
                "depends_on": [], "evidence": ["BEAST.md"], "breadth_count": 1,
                "next_test": "test",
            }
        ],
    }
    assert any("breadth_count >= 3" in error for error in beast_core.validate_graph(graph))


def test_recover_subcommand_uses_existing_verifier(monkeypatch, capsys, tmp_path):
    checkpoint = tmp_path / "latest.json"
    checkpoint.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        beast_core.recovery_verifier,
        "verify",
        lambda path, allow_head_drift=False: {
            "ok": True,
            "checkpoint": str(path),
            "head_drift_allowed": allow_head_drift,
        },
    )
    assert beast_core.main(["recover", str(checkpoint)]) == 0
    result = __import__("json").loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert result["head_drift_allowed"] is False
