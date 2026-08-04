"""Adversarial injection tests for the watching gate.

Pattern transferred from the ECZIS false-microglyph demotion test: the gate
must be proven to CATCH planted deceptions, not merely to accept honest
bundles. Each test plants exactly ONE deception into a known-good bundle and
asserts (a) the gate rejects it and (b) the rejection is attributed to the
planted deception alone — so every check is individually load-bearing, and a
gate that silently lost one check fails this suite.

Pattern-level transfer only; no ECZIS code is used here.
"""

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "validate_watch_procedure.py"
SPEC = importlib.util.spec_from_file_location("validate_watch_procedure", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def honest_timeline() -> dict:
    return {
        "frames": [{"id": "frame-1"}, {"id": "frame-2"}],
        "transcript": {
            "segments": [
                {"text": "Now add the Swizzle modifier"},
                {"text": "and then Negate the value"},
            ]
        },
        "evidence_requests": [{"reason": "modifier panel too small"}],
    }


def honest_procedure() -> dict:
    return {
        "watching_evidence": {
            "visual_only_facts": [
                {
                    "claim": "The swizzle order dropdown shows YXZ.",
                    "frame_ids": ["frame-1"],
                    "transcript_search_terms": ["YXZ"],
                    "transcript_absence_checked": True,
                }
            ],
            "ambiguous_segments": [
                {
                    "description": "Dropdown value unreadable in overview pass",
                    "requires_reinspection": True,
                    "evidence_request_index": 0,
                    "resolved": True,
                }
            ],
        }
    }


def inject(procedure: dict, **overrides: object) -> dict:
    """Plant one deception by overriding fields of the first visual fact."""
    fact = procedure["watching_evidence"]["visual_only_facts"][0]
    fact.update(overrides)
    return procedure


def test_control_honest_bundle_passes():
    # Without this control, the injection tests below would prove nothing.
    result = module.validate(honest_procedure(), honest_timeline())
    assert result["ok"], result["errors"]
    assert result["visual_only_fact_count"] == 1


def test_injected_nonexistent_frame_citation_is_caught():
    procedure = inject(honest_procedure(), frame_ids=["frame-9999"])
    result = module.validate(procedure, honest_timeline())
    assert not result["ok"]
    assert len(result["errors"]) == 1
    assert "unknown frame frame-9999" in result["errors"][0]


def test_injected_narration_fact_disguised_as_visual_is_caught():
    # The core deception: claiming to have SEEN what was actually NARRATED.
    procedure = inject(
        honest_procedure(), transcript_search_terms=["swizzle modifier"]
    )
    result = module.validate(procedure, honest_timeline())
    assert not result["ok"]
    assert len(result["errors"]) == 1
    assert "found in transcript" in result["errors"][0]


def test_case_variant_narration_fact_cannot_evade_the_gate():
    # Evasion attempt: transcript says "Swizzle", claim terms use "SWIZZLE".
    procedure = inject(
        honest_procedure(), transcript_search_terms=["SWIZZLE MODIFIER"]
    )
    result = module.validate(procedure, honest_timeline())
    assert not result["ok"]
    assert "found in transcript" in result["errors"][0]


def test_injected_unchecked_absence_flag_is_caught():
    procedure = inject(honest_procedure(), transcript_absence_checked=False)
    result = module.validate(procedure, honest_timeline())
    assert not result["ok"]
    assert len(result["errors"]) == 1
    assert "transcript_absence_checked must be true" in result["errors"][0]


def test_injected_missing_absence_flag_is_caught():
    procedure = honest_procedure()
    del procedure["watching_evidence"]["visual_only_facts"][0][
        "transcript_absence_checked"
    ]
    result = module.validate(procedure, honest_timeline())
    assert not result["ok"]
    assert "transcript_absence_checked must be true" in result["errors"][0]


def test_injected_empty_search_terms_are_caught():
    # A fact with no search terms can never be checked against the transcript.
    procedure = inject(honest_procedure(), transcript_search_terms=["  ", ""])
    result = module.validate(procedure, honest_timeline())
    assert not result["ok"]
    assert len(result["errors"]) == 1
    assert "transcript_search_terms are required" in result["errors"][0]


def test_injected_uncited_fact_is_caught():
    procedure = inject(honest_procedure(), frame_ids=[])
    result = module.validate(procedure, honest_timeline())
    assert not result["ok"]
    assert len(result["errors"]) == 1
    assert "frame_ids are required" in result["errors"][0]


def test_blank_claim_padding_does_not_inflate_fact_count():
    # Smuggling whitespace-claim facts must not raise the reported evidence count.
    procedure = honest_procedure()
    procedure["watching_evidence"]["visual_only_facts"].append(
        {"claim": "   ", "frame_ids": [], "transcript_search_terms": []}
    )
    result = module.validate(procedure, honest_timeline())
    assert result["ok"]
    assert result["visual_only_fact_count"] == 1


def test_empty_bundle_cannot_claim_watching():
    procedure = {"watching_evidence": {"visual_only_facts": []}}
    result = module.validate(procedure, honest_timeline())
    assert not result["ok"]
    assert "at least one visual-only fact is required" in result["errors"][0]


@pytest.mark.parametrize("bad_index", [None, -1, 5])
def test_injected_dangling_reinspection_reference_is_caught(bad_index):
    procedure = honest_procedure()
    procedure["watching_evidence"]["ambiguous_segments"][0][
        "evidence_request_index"
    ] = bad_index
    result = module.validate(procedure, honest_timeline())
    assert not result["ok"]
    assert any("valid evidence_request_index required" in e for e in result["errors"])


def test_injected_unresolved_reinspection_is_caught():
    procedure = honest_procedure()
    procedure["watching_evidence"]["ambiguous_segments"][0]["resolved"] = False
    result = module.validate(procedure, honest_timeline())
    assert not result["ok"]
    assert len(result["errors"]) == 1
    assert "reinspection is not resolved" in result["errors"][0]


# --- Injection against the real, committed watch-004 artifact ----------------

WATCH_004 = REPO / "proofs" / "watch-004-ue58-first-game" / "watching-gate.json"


def watch_004_compatible_timeline() -> dict:
    """Minimal timeline consistent with the committed watch-004 artifact.

    The full timeline lives under the gitignored watched/ tree, so the test
    synthesizes the smallest timeline the artifact's own citations require:
    its cited frame exists, its reinspection index resolves, and the transcript
    names the modifiers WITHOUT stating the visual-only YXZ order (matching the
    artifact's recorded transcript_only_limitations).
    """
    return {
        "frames": [{"id": "frame-0161"}],
        "transcript": {
            "segments": [
                {"text": "add the Swizzle Input Axis Values modifier"},
                {"text": "then add Negate"},
            ]
        },
        "evidence_requests": [
            {"reason": "r0"},
            {"reason": "r1"},
            {"reason": "forensic resample of the modifier panel"},
        ],
    }


def test_committed_watch_004_artifact_passes_gate():
    procedure = json.loads(WATCH_004.read_text(encoding="utf-8"))
    result = module.validate(procedure, watch_004_compatible_timeline())
    assert result["ok"], result["errors"]


def test_planted_fact_in_watch_004_artifact_is_caught():
    # Inject a fabricated "visual-only" fact into the real shipped artifact:
    # it cites the artifact's own legitimate frame, but its content is
    # narration (Swizzle/Negate are spoken), so watching it was never required.
    procedure = json.loads(WATCH_004.read_text(encoding="utf-8"))
    procedure["watching_evidence"]["visual_only_facts"].append(
        {
            "claim": "The A-key mapping uses Swizzle and Negate modifiers.",
            "frame_ids": ["frame-0161"],
            "transcript_search_terms": ["swizzle", "negate"],
            "transcript_absence_checked": True,
        }
    )
    result = module.validate(procedure, watch_004_compatible_timeline())
    assert not result["ok"]
    assert any(
        "visual_only_facts[1]" in e and "found in transcript" in e
        for e in result["errors"]
    )
