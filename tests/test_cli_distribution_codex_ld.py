"""Exercise the customer CLI process; no patched subprocess or GPU readings."""
from pathlib import Path
import json
import shutil
import subprocess

import pytest


REPO = Path(__file__).resolve().parents[1]
SHELL = shutil.which("powershell.exe") or shutil.which("pwsh")
pytestmark = pytest.mark.skipif(SHELL is None, reason="PowerShell executable unavailable")


def invoke(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [SHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(REPO / "bin/beast.ps1"), *args],
        cwd=cwd, capture_output=True, text=True, timeout=30, check=False,
    )


def test_cli_propagates_refused_workload_exit(tmp_path: Path):
    result = invoke("resource-check", "distribution-unknown-workload", cwd=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert json.loads(result.stdout)["ok"] is False


def test_cli_validate_outside_checkout(tmp_path: Path):
    result = invoke("validate", cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ok"] is True


def test_cli_unknown_command_refused(tmp_path: Path):
    result = invoke("distribution-unknown-command", cwd=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "unknown" in (result.stdout + result.stderr).lower()


def test_cli_help_is_success(tmp_path: Path):
    result = invoke("help", cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "beast validate" in result.stdout
