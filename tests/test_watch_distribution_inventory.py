import importlib.util
from pathlib import Path

import pytest
from packaging.requirements import InvalidRequirement

SPEC = importlib.util.spec_from_file_location(
    "distribution_audit", Path(__file__).parents[1] / "scripts/audit_watch_distribution.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_requirement_cycles_deduplicated(tmp_path):
    (tmp_path / "a.txt").write_text("-r b.txt\npytest==9.1.1\n")
    (tmp_path / "b.txt").write_text("-r a.txt\n")
    rows = module.requirements(tmp_path, tmp_path / "a.txt")
    assert len(rows) == 1
    assert rows[0]["license_decision"] == "not_granted"


def test_requirement_include_cannot_escape(tmp_path):
    (tmp_path / "a.txt").write_text("-r ../outside.txt\n")
    with pytest.raises(ValueError, match="escapes"):
        module.requirements(tmp_path, tmp_path / "a.txt")


def test_invalid_requirement_fails_loudly(tmp_path):
    (tmp_path / "a.txt").write_text("--index-url https://example.invalid\n")
    with pytest.raises(InvalidRequirement):
        module.requirements(tmp_path, tmp_path / "a.txt")
