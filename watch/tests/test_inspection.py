from pathlib import Path

import pytest
from pydantic import ValidationError

from watch.inspection import (BoundingBox, Confidence, DeterministicWatchPolicy,
                              EvidenceGates, InspectionContext, InspectionDecision,
                              Interval, plan_seek)


def context() -> InspectionContext:
    return InspectionContext(source_interval=Interval(start_ms=0, end_ms=6000),
                             candidate_interval=Interval(start_ms=2500, end_ms=3500),
                             confidence=Confidence(perception=0.9, transition=0.5, procedure=0.0))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1, 1.1, True, "0.8"])
def test_probability_boundary(value: object) -> None:
    with pytest.raises(ValidationError):
        Confidence(perception=value, transition=0.5, procedure=0.0)


def test_contract_rejects_promotion_and_leaks() -> None:
    decision = DeterministicWatchPolicy().decide(context())
    for field in ("ground_truth", "accepted", "source_path", "original_sampling"):
        with pytest.raises(ValidationError):
            InspectionDecision.model_validate({**decision.model_dump(), field: True})
    with pytest.raises(ValidationError):
        decision.requested_action = "stop_inspection"
    with pytest.raises(ValidationError):
        Interval(start_ms=2, end_ms=1)
    with pytest.raises(ValidationError):
        BoundingBox(x=0.9, y=0.0, width=0.2, height=1.0)


def test_existing_escalation_and_equal_budget() -> None:
    ctx = context()
    decision = DeterministicWatchPolicy().decide(ctx)
    plan = plan_seek(decision, ctx, 25)
    assert plan and plan.level == 2 and plan.fps == 4 and len(plan.timestamps) == 25
    with pytest.raises(ValueError, match="budget"):
        plan_seek(decision, ctx, 24)
    assert decision.confidence.procedure == 0.0


@pytest.mark.parametrize("action", ["run_ocr", "track_element", "expand_region", "compare_states", "request_slow_review"])
def test_unsupported_actions_fail_closed(action: str) -> None:
    ctx = context()
    decision = DeterministicWatchPolicy().decide(ctx).model_dump()
    decision["requested_action"] = action
    with pytest.raises(ValueError, match="unavailable"):
        plan_seek(InspectionDecision.model_validate(decision), ctx, 100)


def test_confidence_never_promotes_evidence() -> None:
    Confidence(perception=1.0, transition=1.0, procedure=1.0)
    assert EvidenceGates(transition_passed=False).evidence_class == "uncertain_observation"
    gates = EvidenceGates(transition_passed=True, transition_evidence=("before:hash", "after:hash"))
    assert gates.evidence_class == "evidence_supported_transition"
    with pytest.raises(ValidationError):
        EvidenceGates(transition_passed=True)
    assert EvidenceGates(transition_passed=True, transition_evidence=("a", "b"),
                         action_supports_cause=True, causal_evidence=("input-event",),
                         reproducibility_passed=True, reproducibility_evidence=("replay",)
                         ).evidence_class == "verified_procedure_step"


def test_stop_does_not_mean_acceptance() -> None:
    ctx = context().model_copy(update={"completed_inspections": 1})
    decision = DeterministicWatchPolicy().decide(ctx)
    assert decision.requested_action == "stop_inspection"
    assert plan_seek(decision, ctx, 0) is None


def test_exclusive_intent_prevents_replay(tmp_path: Path) -> None:
    from watch.inspection_runtime import retain
    path = tmp_path / "intent.json"
    retain(path, {"status": "intent"})
    with pytest.raises(FileExistsError):
        retain(path, {"status": "intent"})


def test_huge_interval_rejected_before_allocation(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = InspectionContext(source_interval=Interval(start_ms=0, end_ms=10**18),
                            candidate_interval=Interval(start_ms=0, end_ms=10**18),
                            confidence=context().confidence)
    data = DeterministicWatchPolicy().decide(ctx).model_dump()
    data["target_interval"] = ctx.source_interval.model_dump()
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("allocated timestamps before budget check")
    monkeypatch.setattr("watch.inspection.seek_times", forbidden)
    with pytest.raises(ValueError, match="budget"):
        plan_seek(InspectionDecision.model_validate(data), ctx, 1)


def test_runtime_rejects_foreign_frame_before_extraction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from watch.inspection_runtime import execute_inspection, retain
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    retain(bundle / "timeline.json", {"frames": [{"file": "../foreign.jpg"}]})
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("called Watch with foreign frame")
    monkeypatch.setattr("watch.inspection_runtime.reinspect", forbidden)
    with pytest.raises(ValueError, match="escapes"):
        execute_inspection(bundle, "unused", DeterministicWatchPolicy().decide(context()),
                           context(), 25, bundle / "intent.json")
    assert not (tmp_path / "foreign.verify.jpg").exists()
    assert not (bundle / "intent.json").exists()


def test_bundle_lock_rejects_second_writer(tmp_path: Path) -> None:
    from watch.inspection_runtime import execute_inspection
    (tmp_path / ".inspection-lock").mkdir()
    with pytest.raises(FileExistsError):
        execute_inspection(tmp_path, "unused", DeterministicWatchPolicy().decide(context()),
                           context(), 25, tmp_path / "other-intent.json")


def test_semif_style_scores_are_not_confidence() -> None:
    from watch.inspection import OptionReadout, OptionScore
    readout = OptionReadout(backend="semif-protocol-test", model_revision="test-only",
                            prompt_sha256="a" * 64, input_tokens=1, elapsed_seconds=0.0,
                            scores=(OptionScore(action="stop_inspection", score=0.99),
                                    OptionScore(action="increase_density", score=0.01)))
    decision = DeterministicWatchPolicy().decide(context())
    copied = InspectionDecision.model_validate({**decision.model_dump(), "option_readout": readout.model_dump()})
    assert copied.confidence == context().confidence
    assert copied.confidence.procedure == 0.0
    with pytest.raises(ValidationError):
        OptionReadout.model_validate({**readout.model_dump(), "probability_status": "verified"})


@pytest.mark.parametrize("mutation", ["empty", "duplicate", "foreign_id", "zero_budget"])
def test_frozen_manifest_validation(mutation: str) -> None:
    import json
    from scripts.evaluate_watch_inspection import Corpus
    path = Path(__file__).resolve().parents[2] / "proofs/watch-inspection/corpus/manifest.json"
    data = json.loads(path.read_text())
    if mutation == "empty":
        data["cases"] = []
    elif mutation == "duplicate":
        data["cases"].append(data["cases"][0])
    elif mutation == "foreign_id":
        data["cases"][0]["id"] = "../../foreign"
    else:
        data["inspection_budget"] = 0
    with pytest.raises(ValidationError):
        Corpus.model_validate_json(json.dumps(data))


def test_changed_source_during_copy_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.evaluate_watch_inspection import evaluate
    from watch.inspection_runtime import digest
    corpus = Path(__file__).resolve().parents[2] / "proofs/watch-inspection/corpus"
    def corrupt(source: Path, destination: Path) -> None:
        destination.write_bytes(b"changed source")
    monkeypatch.setattr("scripts.evaluate_watch_inspection.shutil.copyfile", corrupt)
    with pytest.raises(ValueError, match="copied source"):
        evaluate(corpus, digest(corpus / "manifest.json"), tmp_path / "output", "unused")


def test_frozen_hash_mismatch_has_no_output(tmp_path: Path) -> None:
    from scripts.evaluate_watch_inspection import evaluate
    corpus = Path(__file__).resolve().parents[2] / "proofs/watch-inspection/corpus"
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="manifest hash"):
        evaluate(corpus, "0" * 64, output, "unused")
    assert not output.exists()


def test_expired_seek_deadline_extracts_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from watch.inspection_runtime import retain
    from watch.seek import SeekError, reinspect
    (tmp_path / "video.mkv").write_bytes(b"not decoded")
    retain(tmp_path / "timeline.json", {"source": {"local_video": "video.mkv", "range": {
        "start_seconds": 0, "end_seconds": 6, "start": "0", "end": "6"}}, "frames": []})
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("decoder called past compute deadline")
    monkeypatch.setattr("watch.seek.extract_frame", forbidden)
    with pytest.raises(SeekError, match="deadline"):
        reinspect(tmp_path, "unused", center=3, deadline=0)


def test_planned_symlink_rejected_before_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from watch.inspection_runtime import execute_inspection, retain
    bundle = tmp_path / "bundle"
    (bundle / "frames").mkdir(parents=True)
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"must survive")
    try:
        (bundle / "frames/f_000000000000.jpg").symlink_to(outside)
    except OSError:
        pytest.skip("Windows symlink privilege unavailable")
    retain(bundle / "timeline.json", {"frames": []})
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("decoder called with foreign planned destination")
    monkeypatch.setattr("watch.inspection_runtime.reinspect", forbidden)
    with pytest.raises(ValueError, match="planned frame"):
        execute_inspection(bundle, "unused", DeterministicWatchPolicy().decide(context()),
                           context(), 25, bundle / "intent.json")
    assert outside.read_bytes() == b"must survive"
