"""No paid calls: exercise the real helper with failed process boundaries."""
import subprocess
from types import SimpleNamespace

import pytest
import server
import higgsfield_cli


@pytest.fixture(autouse=True)
def native_cli_stub(monkeypatch):
    monkeypatch.setattr(higgsfield_cli, "resolve_cli", lambda: "native-hf.exe")


@pytest.mark.parametrize("code", [1, 2, 23])
def test_failed_cli_input_url_is_never_downloaded(tmp_path, monkeypatch, code):
    calls = []
    monkeypatch.setattr(server.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=code, stdout='{"status":"failed","input_url":"https://cdn.example/source.png"}',
        stderr="private diagnostics"))
    monkeypatch.setattr(server.urllib.request, "urlretrieve", lambda *a: calls.append(a))
    result = server.hf_generate("gpt_image_2", "test", tmp_path / "out.png")
    assert result["outcome"] == "outcome_unknown"
    assert result["exit_code"] == code
    assert "file" not in result and not calls
    assert "private diagnostics" not in str(result)
    assert not (tmp_path / "out.png").exists()


@pytest.mark.parametrize("error,outcome", [
    (subprocess.TimeoutExpired("higgsfield", 1000), "outcome_unknown"),
    (FileNotFoundError("missing"), "not_submitted"),
])
def test_process_failure_is_contained_without_replay(tmp_path, monkeypatch, error, outcome):
    calls = []
    def fail(*args, **kwargs):
        calls.append(args)
        raise error
    monkeypatch.setattr(server.subprocess, "run", fail)
    result = server.hf_generate("gpt_image_2", "test", tmp_path / "out.png")
    assert result["outcome"] == outcome
    assert "file" not in result
    assert len(calls) == 1
