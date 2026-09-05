import io
import json
import sys

import pytest

from scripts import judge_image


@pytest.mark.parametrize("value", [
    None, [], {}, {"score": 10},
    {"score": "10", "kill": False, "fix": ""},
    {"score": True, "kill": False, "fix": ""},
    {"score": float("nan"), "kill": False, "fix": ""},
    {"score": float("inf"), "kill": False, "fix": ""},
    {"score": 11, "kill": False, "fix": ""},
    {"score": 0, "kill": False, "fix": ""},
    {"score": 9, "kill": "false", "fix": ""},
    {"score": 9, "kill": False, "fix": []},
    {"score": 9, "kill": False, "fix": "x" * 2001},
    {"score": 9, "kill": False, "fix": "", "refusal": "no"},
])
def test_hostile_verdicts_are_not_scores(value):
    with pytest.raises(judge_image.JudgeOutputError):
        judge_image.validate_verdict(value)


def test_valid_fractional_verdict():
    value = {"score": 8.5, "kill": False, "fix": "Reduce highlights"}
    assert judge_image.validate_verdict(value) == value


def test_schema_sent_and_final_response_validated(tmp_path, monkeypatch):
    img = tmp_path / "sample.png"
    img.write_bytes(b"fixture")
    verdict = {"score": 8, "kill": False, "fix": ""}

    def respond(request, **kwargs):
        body = json.loads(request.data)
        assert body["format"] == judge_image.JUDGE_SCHEMA
        assert body["options"]["temperature"] == 0
        return io.BytesIO(json.dumps({"response": json.dumps(verdict)}).encode())

    monkeypatch.setattr(judge_image.urllib.request, "urlopen", respond)
    assert judge_image.judge(str(img), "brief", "model") == verdict


def test_local_adapter_empty_response_accepts_only_whole_structured_answer(tmp_path, monkeypatch):
    img = tmp_path / "sample.png"
    img.touch()
    payload = {"response": "", "thinking": json.dumps(
        {"score": 10, "kill": False, "fix": ""})}
    monkeypatch.setattr(judge_image.urllib.request, "urlopen",
                        lambda *a, **kw: io.BytesIO(json.dumps(payload).encode()))
    assert judge_image.judge(str(img), "brief", "model") == {
        "score": 10, "kill": False, "fix": ""}


@pytest.mark.parametrize("payload", [
    {"response": "", "thinking": 'I think the score is {"score":10,"kill":false,"fix":""}'},
    {"response": "invalid", "thinking": '{"score":10,"kill":false,"fix":""}'},
    {"response": None}, [], {"error": "model unavailable"},
])
def test_no_reasoning_extraction_or_malformed_response_fallback(tmp_path, monkeypatch, payload):
    img = tmp_path / "sample.png"
    img.touch()
    monkeypatch.setattr(judge_image.urllib.request, "urlopen",
                        lambda *a, **kw: io.BytesIO(json.dumps(payload).encode()))
    with pytest.raises(judge_image.JudgeOutputError):
        judge_image.judge(str(img), "brief", "model")


@pytest.mark.parametrize("response", [
    '{"score":8,"kill":true,"kill":false,"fix":""}',
    '{"score":2,"score":10,"kill":false,"fix":""}',
])
def test_contradictory_duplicate_fields_are_rejected(tmp_path, monkeypatch, response):
    img = tmp_path / "sample.png"
    img.touch()
    monkeypatch.setattr(judge_image.urllib.request, "urlopen", lambda *a, **kw:
                        io.BytesIO(json.dumps({"response": response}).encode()))
    with pytest.raises(judge_image.JudgeOutputError, match="duplicate"):
        judge_image.judge(str(img), "brief", "model")


def test_cli_killed_high_score_cannot_win(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["judge_image.py", "bad.png", "good.png", "--brief", "brief"])
    monkeypatch.setattr(judge_image, "judge", lambda path, *_: {
        "score": 10 if path == "bad.png" else 8,
        "kill": path == "bad.png", "fix": ""})
    assert judge_image.main() == 0
    assert "WINNER: good.png" in capsys.readouterr().out


def test_cli_all_killed_is_failure(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["judge_image.py", "bad.png", "--brief", "brief"])
    monkeypatch.setattr(judge_image, "judge", lambda *_: {
        "score": 10, "kill": True, "fix": ""})
    assert judge_image.main() == 1
    assert "NO WINNER" in capsys.readouterr().out
