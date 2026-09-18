"""Offline adapter attacks: no real executable, provider request, or paid job."""
import copy
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

from PIL import Image
import pytest

import higgsfield_cli as hf

JOB = {"id": "2b1029a0-de52-45a1-ad46-4b160c8cc1fd", "status": "completed",
       "job_type": "nano_banana_flash",
       "result_url": "https://d8j0ntlcm91z4.cloudfront.net/proof.png?signature=private"}


@pytest.fixture(autouse=True)
def no_real_cli(monkeypatch):
    monkeypatch.setattr(hf, "resolve_cli", lambda: "native-hf.exe")
    monkeypatch.setattr(hf.subprocess, "run", lambda *a, **k: pytest.fail("unexpected subprocess"))
    monkeypatch.setattr(hf, "_connection", lambda *a: pytest.fail("unexpected network"))


def fake_generate(monkeypatch, job=JOB, code=0):
    calls = []
    def run(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=code, stdout=json.dumps(job), stderr="private auth diagnostics")
    monkeypatch.setattr(hf.subprocess, "run", run)
    def image(url, path):
        Image.new("RGB", (16, 16), (50, 100, 150)).save(path, format="PNG")
        return path.stat().st_size
    monkeypatch.setattr(hf, "download", image)
    return calls


@pytest.mark.parametrize("array", [False, True])
def test_success_is_terminal_decoded_receipted_and_never_replayed(tmp_path, monkeypatch, array):
    calls = fake_generate(monkeypatch, [JOB] if array else JOB)
    out = tmp_path / "result.png"
    result = hf.generate("gpt_image_2", "private prompt", out)
    assert result["file"] == "result.png"
    assert "signature" not in json.dumps(result)
    receipt = json.loads((tmp_path / result["receipt"]).read_text())
    assert receipt["ok"] and receipt["status"] == "completed"
    assert receipt["job_id"] == JOB["id"]
    assert receipt["artifact_sha256"] == hf._sha(out)
    assert receipt["dimensions"] == [16, 16]
    assert "private" not in json.dumps(receipt)
    assert "error" in hf.generate("gpt_image_2", "private prompt", out)
    assert len(calls) == 1
    assert calls[0][0][0][0] == "native-hf.exe"
    assert not calls[0][1].get("shell")


@pytest.mark.parametrize("job", [None, [], [JOB, JOB], {"id": "invalid"},
                                {**JOB, "status": "pending"},
                                {**JOB, "status": "failed"},
                                {**JOB, "result_url": None},
                                {**JOB, "result_url": "https://evil.test/result.png"}])
def test_bad_or_nonterminal_job_never_downloaded(tmp_path, monkeypatch, job):
    calls = fake_generate(monkeypatch, job)
    monkeypatch.setattr(hf, "download", lambda *a: pytest.fail("downloaded unverified URL"))
    result = hf.generate("gpt_image_2", "test", tmp_path / "out.png")
    assert "error" in result and not (tmp_path / "out.png").exists()
    assert len(calls) == 1


@pytest.mark.parametrize("text", ['{"id":"a","id":"b"}', '[] garbage', '{"x":NaN}', 'null'])
def test_strict_json(text):
    with pytest.raises((ValueError, TypeError)):
        hf.parse_job(text)


@pytest.mark.parametrize("url", ["http://d8j0ntlcm91z4.cloudfront.net/a", "https://127.0.0.1/a",
    "https://d8j0ntlcm91z4.cloudfront.net.evil.test/a", "https://user@d8j0ntlcm91z4.cloudfront.net/a",
    "https://d8j0ntlcm91z4.cloudfront.net:444/a", "https://d8j0ntlcm91z4.cloudfront.net/a#frag",
    "https://d8j0ntlcm91z4.cloudfront.net/a\nInjected", "https://other.cloudfront.net/a"])
def test_unsafe_url(url):
    with pytest.raises(ValueError):
        hf.checked_url(url)


def test_write_ahead_intent_precedes_process_and_blocks_concurrent_attempt(tmp_path, monkeypatch):
    output = tmp_path / "out.png"
    calls = []
    def timeout(*args, **kwargs):
        calls.append(args)
        receipt = json.loads(output.with_name(output.name + ".higgsfield.json").read_text())
        assert receipt["status"] == "outcome_unknown"
        assert "error" in hf.generate("gpt_image_2", "same", output)
        raise subprocess.TimeoutExpired("hf", 1000)
    monkeypatch.setattr(hf.subprocess, "run", timeout)
    assert hf.generate("gpt_image_2", "test", output)["outcome"] == "outcome_unknown"
    assert len(calls) == 1


def test_invalid_image_never_published_and_provider_job_retained(tmp_path, monkeypatch):
    fake_generate(monkeypatch)
    def html(url, path):
        path.write_bytes(b"<html>not a PNG</html>")
        return path.stat().st_size
    monkeypatch.setattr(hf, "download", html)
    result = hf.generate("gpt_image_2", "test", tmp_path / "out.png")
    assert result["outcome"] == "provider_completed_artifact_pending"
    assert not (tmp_path / "out.png").exists()
    receipt = json.loads((tmp_path / result["receipt"]).read_text())
    assert receipt["job_id"] == JOB["id"] and not receipt["ok"]
    assert (tmp_path / "out.png.higgsfield.part").exists()


def test_existing_output_preserved(tmp_path):
    output = tmp_path / "out.png"
    output.write_bytes(b"owner bytes")
    assert "error" in hf.generate("gpt_image_2", "test", output)
    assert output.read_bytes() == b"owner bytes"


@pytest.mark.parametrize("extra", [["--num_images", "4"], ["--json", "false"], ["--image"], ["--resolution", None]])
def test_extra_cli_control_flags_rejected(tmp_path, extra):
    assert hf.generate("gpt_image_2", "test", tmp_path / "out.png", extra)["outcome"] == "not_submitted"
    assert not list(tmp_path.iterdir())


class FakeConnection:
    def __init__(self, *, status=200, length="3", chunks=(b"abc", b"")):
        self.status, self.length, self.chunks = status, length, iter(chunks)
        self.closed = False
    def request(self, *args, **kwargs):
        pass
    def getresponse(self):
        return self
    def getheader(self, name, default=None):
        return self.length if name == "Content-Length" else default
    def read1(self, _):
        return next(self.chunks)
    def close(self):
        self.closed = True


@pytest.mark.parametrize("settings", [{"status":302}, {"length":"1000"}, {"length":"0"},
                                        {"length":str(hf.MAX_BYTES+1)}])
def test_download_rejects_redirect_or_bad_length(tmp_path, monkeypatch, settings):
    connection = FakeConnection(**settings)
    monkeypatch.setattr(hf, "_connection", lambda *a: connection)
    with pytest.raises(ValueError):
        hf.download(JOB["result_url"], tmp_path / "part")
    assert connection.closed


def test_download_enforces_streaming_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(hf, "MAX_BYTES", 2)
    connection = FakeConnection(length=None)
    monkeypatch.setattr(hf, "_connection", lambda *a: connection)
    with pytest.raises(ValueError, match="byte limit"):
        hf.download(JOB["result_url"], tmp_path / "part")


def test_nonzero_exit_preserves_known_job_but_never_downloads(tmp_path, monkeypatch):
    fake_generate(monkeypatch, JOB, code=1)
    monkeypatch.setattr(hf, "download", lambda *a: pytest.fail("download after failed exit"))
    result = hf.generate("gpt_image_2", "test", tmp_path / "out.png")
    receipt = json.loads((tmp_path / result["receipt"]).read_text())
    assert receipt["job_id"] == JOB["id"] and not receipt["ok"]


def test_download_deadline_is_checked_between_reads(tmp_path, monkeypatch):
    connection = FakeConnection(length=None, chunks=(b"a", b"b", b""))
    monkeypatch.setattr(hf, "_connection", lambda *a: connection)
    times = iter((0, 1, 91))
    monkeypatch.setattr(hf.time, "monotonic", lambda: next(times))
    with pytest.raises(ValueError, match="deadline"):
        hf.download(JOB["result_url"], tmp_path / "part")


def test_resolve_windows_npm_vendor_without_shell(tmp_path, monkeypatch):
    shim = tmp_path / "higgsfield.cmd"
    native = tmp_path / "node_modules/@higgsfield/cli/vendor/hf.exe"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"test executable marker, never run")
    monkeypatch.setattr(hf.shutil, "which", lambda _: str(shim))
    # Call original implementation rather than fixture's network-safe stub.
    import importlib.util
    spec = importlib.util.spec_from_file_location("hf_resolver_test", Path(hf.__file__))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.resolve_cli() == str(native.resolve())
