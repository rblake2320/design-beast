import json
import base64
import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from watch.frame_observer import FrameState, observe_frame, parse_state
from watch import frame_observer


def state() -> dict[str, str]:
    return {key: "A visible screen" for key in FrameState.model_fields}


@pytest.mark.parametrize("field", ["response", "thinking", "content"])
def test_complete_structured_envelope(field: str) -> None:
    payload = {"done": True, "done_reason": "stop", "message": {field: json.dumps(state())}}
    assert parse_state(payload).view == "A visible screen"


def test_source_identity_is_not_model_controlled() -> None:
    value = {**state(), "source_ms": 999, "verified_procedure": True}
    with pytest.raises(ValidationError):
        parse_state({"done": True, "done_reason": "stop", "response": json.dumps(value)})


@pytest.mark.parametrize("reason", ["length", "load", None])
def test_nonterminal_output_cannot_be_observation(reason: str | None) -> None:
    with pytest.raises(ValueError, match="incomplete"):
        parse_state({"done": True, "done_reason": reason, "response": json.dumps(state())})


def test_duplicate_keys_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        parse_state({"done": True, "done_reason": "stop", "response": '{"view":"a","view":"b"}'})


@pytest.mark.parametrize("blank", ["", "  ", "unknown"])
def test_empty_or_unknown_state_not_complete(blank: str) -> None:
    with pytest.raises(ValueError):
        parse_state({"done": True, "done_reason": "stop", "response": json.dumps({key: blank for key in FrameState.model_fields})})


def test_changed_frame_refused_before_any_gpu_or_output(tmp_path: Path) -> None:
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"changed")
    output = tmp_path / "result"
    with pytest.raises(ValueError, match="custody"):
        observe_frame(image, 10, "0" * 64, output)
    assert not output.exists()


def test_submitted_bytes_are_the_verified_bytes_even_if_file_changes(tmp_path: Path, monkeypatch) -> None:
    original = b"frozen image bytes"
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(original)
    expected = hashlib.sha256(original).hexdigest()
    requests = []

    class Response:
        def __init__(self, value):
            self.value = value
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return json.dumps(self.value).encode()

    def admit(*args, **kwargs):
        frame.write_bytes(b"replacement after verified read")
        return {"admitted": True}

    def urlopen(request, **kwargs):
        if isinstance(request, str):
            return Response({"models": [{"name": "qwen3-vl:8b-instruct", "digest": "frozen-model"}]})
        requests.append(json.loads(request.data))
        return Response({"done": True, "done_reason": "stop", "message": {"content": json.dumps(state())}})

    monkeypatch.setattr(frame_observer, "admission", admit)
    monkeypatch.setattr(frame_observer.urllib.request, "urlopen", urlopen)
    result = observe_frame(frame, 500, expected, tmp_path / "output", "qwen3-vl:8b-instruct",
                           source_offset_ms=300000, source_sha256="a" * 64,
                           expected_model_digest="frozen-model")
    assert base64.b64decode(requests[0]["messages"][0]["images"][0]) == original
    assert result["clip_ms"] == 500
    assert result["source_ms"] == 300500
    assert result["sha256"] == expected
    intent = json.loads((tmp_path / "output/intent.json").read_text())
    assert intent["options"] == requests[0]["options"]
    assert intent["model_digest"] == "frozen-model"


def test_changed_model_digest_refused_before_inference(tmp_path: Path, monkeypatch) -> None:
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"pixels")
    monkeypatch.setattr(frame_observer, "admission", lambda *args, **kwargs: {"admitted": True})

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return json.dumps({"models": [{"name": "qwen3-vl:8b", "digest": "changed"}]}).encode()

    calls = []
    def urlopen(request, **kwargs):
        calls.append(request)
        assert isinstance(request, str), "inference must not execute"
        return Response()
    monkeypatch.setattr(frame_observer.urllib.request, "urlopen", urlopen)
    with pytest.raises(ValueError, match="model changed"):
        observe_frame(frame, 0, hashlib.sha256(b"pixels").hexdigest(), tmp_path / "output",
                      expected_model_digest="original")
    assert len(calls) == 1
