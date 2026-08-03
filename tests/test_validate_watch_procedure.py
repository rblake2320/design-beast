import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_watch_procedure.py"
SPEC = importlib.util.spec_from_file_location("validate_watch_procedure", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_visual_only_fact_and_reinspection_are_linked():
    timeline = {
        "frames": [{"id": "frame-1"}],
        "transcript": {"segments": [{"text": "Open settings"}]},
        "evidence_requests": [{"reason": "resolve menu"}],
    }
    procedure = {"watching_evidence": {
        "visual_only_facts": [{
            "claim": "The toggle is blue", "frame_ids": ["frame-1"],
            "transcript_search_terms": ["toggle is blue"],
            "transcript_absence_checked": True,
        }],
        "ambiguous_segments": [{
            "description": "Which toggle changed", "requires_reinspection": True,
            "evidence_request_index": 0, "resolved": True,
        }],
    }}
    assert module.validate(procedure, timeline)["ok"]


def test_transcript_only_and_unresolved_artifacts_fail():
    timeline = {
        "frames": [{"id": "frame-1"}],
        "transcript": {"segments": [{"text": "The toggle is blue"}]},
        "evidence_requests": [],
    }
    procedure = {"watching_evidence": {
        "visual_only_facts": [{
            "claim": "The toggle is blue", "frame_ids": ["missing"],
            "transcript_search_terms": ["toggle is blue"],
            "transcript_absence_checked": True,
        }],
        "ambiguous_segments": [{
            "description": "Which toggle", "requires_reinspection": True,
            "evidence_request_index": None, "resolved": False,
        }],
    }}
    result = module.validate(procedure, timeline)
    assert not result["ok"]
    assert any("found in transcript" in error for error in result["errors"])
    assert any("unknown frame" in error for error in result["errors"])
    assert any("not resolved" in error for error in result["errors"])
