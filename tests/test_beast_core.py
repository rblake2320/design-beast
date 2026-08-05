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


def test_active_pack_has_fail_closed_lifecycle_policy():
    pack = beast_core.read_json(
        ROOT / "beast" / "packs" / "ue58-enhanced-input-movement" / "pack.json"
    )
    assert pack["lifecycle_policy"].endswith("lifecycle.json")
    assert beast_core.validate_all()["ok"] is True


def test_trusted_pack_selection_excludes_drift(monkeypatch):
    good = {
        "protocol_version": "2025-06-18",
        "toolset_count": 56,
        "blueprint_dsl_documented": True,
        "endpoint": "http://127.0.0.1:8000/mcp",
    }
    monkeypatch.setattr(beast_core.lifecycle_gate, "run_json_probe", lambda *args, **kwargs: good)
    assert "ue58-enhanced-input-movement" in beast_core.trusted_packs()["eligible"]
    drifted = {**good, "toolset_count": 55}
    monkeypatch.setattr(beast_core.lifecycle_gate, "run_json_probe", lambda *args, **kwargs: drifted)
    result = beast_core.trusted_packs()
    assert "ue58-enhanced-input-movement" not in result["eligible"]
    assert result["excluded"][0]["reason"] == "stale_unproven"


def test_trusted_pack_selection_fails_closed_on_probe_error(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("offline")
    monkeypatch.setattr(beast_core.lifecycle_gate, "run_json_probe", fail)
    result = beast_core.trusted_packs()
    assert result["eligible"] == []
    assert result["excluded"][0]["reason"] == "probe_error"
