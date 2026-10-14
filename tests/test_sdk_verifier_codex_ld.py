"""Completeness attacks using actual pytest and Node runner output."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

spec = importlib.util.spec_from_file_location(
    "sdk_verifier_review", Path(__file__).resolve().parents[1] / "scripts/verify_sdk_distribution_codex_ld.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def test_python_deselection_is_rejected_and_environment_isolated(tmp_path, monkeypatch):
    source = '''from pathlib import Path
import pytest
def test_alpha():
    Path(__file__).with_suffix('.alpha-ran').write_text('executed')
@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_beta(host):
    Path(__file__).with_suffix('.' + host + '-ran').write_text('executed')
'''
    fixture = tmp_path / "test_controls.py"
    fixture.write_text(source)
    config = tmp_path / "pytest.ini"
    config.write_text("[pytest]\n")
    required = verifier.python_deadline_inventory(source)
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k alpha")
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    xml = tmp_path / "selected.xml"
    command = [sys.executable, "-m", "pytest", "-q", "-c", str(config),
               "--confcutdir", str(tmp_path), str(fixture)]
    selected = subprocess.run([*command, f"--junitxml={xml}"], cwd=tmp_path, env=env,
                              capture_output=True, text=True, timeout=20)
    (tmp_path / "selected.txt").write_text(selected.stdout + selected.stderr)
    assert selected.returncode == 0 and "2 deselected" in selected.stdout
    with pytest.raises(RuntimeError, match="inventory"):
        verifier.verify_python_deadlines(xml, required)
    complete = tmp_path / "complete.xml"
    result = subprocess.run([*command, f"--junitxml={complete}"], cwd=tmp_path,
                            env=verifier.isolated_test_env(), capture_output=True, text=True, timeout=20)
    (tmp_path / "complete.txt").write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    assert verifier.verify_python_deadlines(complete, required) == 3
    assert fixture.with_suffix(".alpha-ran").read_text() == "executed"
    assert fixture.with_suffix(".127.0.0.1-ran").read_text() == "executed"
    assert fixture.with_suffix(".localhost-ran").read_text() == "executed"


@pytest.mark.parametrize("status", ["skip", "todo", "renamed"])
def test_node_incomplete_required_inventory_is_rejected(tmp_path, status):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for the actual runner acceptance control")
    header = 'import {test} from "node:test"; import assert from "node:assert/strict";\n'
    first = 'test("deadline: alpha",()=>assert.equal(Buffer.from("owned").length,5));\n'
    second = 'test("deadline: beta",()=>assert.equal(Buffer.from("control").length,7));\n'
    source = header + first + second
    required = verifier.node_deadline_inventory(source)
    broken = (second.replace("test(", f"test.{status}(") if status != "renamed" else
              second.replace("deadline: beta", "deadline: beta-changed"))
    fixture = tmp_path / "controls.mjs"
    fixture.write_text(header + first + broken)
    # Direct node:test execution keeps one owned process and also works on the
    # hosted Python job's Node version, which lacks --test-isolation.
    result = subprocess.run([node, "--test-reporter=tap", str(fixture)], cwd=tmp_path,
                            env=verifier.isolated_test_env(), capture_output=True, text=True, timeout=20)
    (tmp_path / "incomplete.tap").write_text(result.stdout + result.stderr)
    marker = "# pass 2" if status == "renamed" else f"# {'skipped' if status == 'skip' else 'todo'} 1"
    assert marker in result.stdout
    with pytest.raises(RuntimeError, match="inventory"):
        verifier.verify_node_deadlines(result.stdout, required)
    fixture.write_text(source)
    result = subprocess.run([node, "--test-reporter=tap", str(fixture)], cwd=tmp_path,
                            env=verifier.isolated_test_env(), capture_output=True, text=True, timeout=20)
    (tmp_path / "complete.tap").write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    assert verifier.verify_node_deadlines(result.stdout, required) == 2
