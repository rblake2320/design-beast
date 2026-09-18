import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from watch.frame_observer import FrameState, observe_frame, parse_state


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
