import json

import pytest
from pydantic import ValidationError

from scripts.challenge_watch_real_video import parse_answer


@pytest.mark.parametrize("field", ["response", "thinking"])
def test_exact_json_response_fields(field: str) -> None:
    result = parse_answer({"done": True, "done_reason": "stop", field: '{"changes":[],"unresolved":[]} '})
    assert result.changes == ()


def test_output_budget_never_accepts_even_parseable_partial() -> None:
    with pytest.raises(ValueError, match="budget"):
        parse_answer({"done": True, "done_reason": "length", "response": '{"changes":[],"unresolved":[]}'})


def test_unordered_or_authority_claim_rejected() -> None:
    data = {"changes": [{"before_index": 1, "after_index": 0, "description": "changed",
                          "confidence": {"perception": 1.0, "transition": 1.0, "procedure": 0.0},
                          "uncertainty": ""}], "unresolved": []}
    with pytest.raises(ValidationError):
        parse_answer({"done": True, "done_reason": "stop", "response": json.dumps(data)})
    with pytest.raises(ValidationError):
        parse_answer({"done": True, "done_reason": "stop", "response": '{"changes":[],"unresolved":[],"verified_procedure":true}'})
