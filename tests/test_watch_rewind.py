import pytest
from pydantic import ValidationError
from watch.inspection import Interval, InspectionContext, Confidence, plan_seek
from watch.rewind import EvidenceDebt, ChangeSample, budget_fps, refinement, request, rewind_window


@pytest.mark.parametrize("anchor,back,duration", [(0,1000,3000),(3000,1000,3000),(1000,10001,3000),(True,1000,3000)])
def test_invalid_anchor(anchor, back, duration):
    with pytest.raises(ValueError): rewind_window(anchor,back,duration)


def test_rewind_clamped_to_source():
    assert rewind_window(1000,2000,3000) == Interval(start_ms=0,end_ms=1000)


def test_surprise_is_recommendation_not_cause():
    window = Interval(start_ms=0,end_ms=2000)
    result = refinement(window, (ChangeSample(start_ms=0,end_ms=500,mean_absolute_difference=1.0),
        ChangeSample(start_ms=500,end_ms=1000,mean_absolute_difference=20.0)))
    assert result.target_interval == Interval(start_ms=500,end_ms=1000)
    assert result.confidence.procedure == 0.0
    assert EvidenceDebt().action == "unresolved"


def test_static_does_not_invent_refinement():
    assert refinement(Interval(start_ms=0,end_ms=2000), (ChangeSample(start_ms=0,end_ms=500,mean_absolute_difference=0.0),)) is None


def test_foreign_measurement_rejected():
    with pytest.raises(ValueError): refinement(Interval(start_ms=0,end_ms=1000),
        (ChangeSample(start_ms=500,end_ms=1500,mean_absolute_difference=20.0),))


def test_debt_cannot_self_promote():
    with pytest.raises(ValidationError): EvidenceDebt(action="verified")


@pytest.mark.parametrize("budget", [5,11,16,96])
def test_requests_fit_watch_budget(budget):
    interval = Interval(start_ms=0,end_ms=2000)
    context = InspectionContext(source_interval=interval,candidate_interval=interval,
        confidence=Confidence(perception=0.0,transition=0.0,procedure=0.0))
    plan = plan_seek(request(interval,"test"),context,budget,fixed_fps=budget_fps(interval,budget))
    assert len(plan.timestamps) <= budget


def test_zero_budget_rejected():
    with pytest.raises(ValueError): budget_fps(Interval(start_ms=0,end_ms=2000),0)


def test_reverse_order_is_available_without_changing_default():
    import inspect
    from scripts.evaluate_watch_rewind import evaluate
    assert inspect.signature(evaluate).parameters["reverse_order"].default is False


@pytest.mark.parametrize("field", ["perception_confidence", "transition_confidence", "procedure_confidence"])
def test_nonfinite_confidence_rejected(field):
    with pytest.raises(ValueError): EvidenceDebt(**{field: float("nan")})


@pytest.mark.parametrize("attack", ["source", "frame", "pending", "foreign", "outside", "budget"])
def test_runner_rejects_before_execution(tmp_path, attack):
    import json
    from scripts.evaluate_watch_rewind import evaluate
    from watch.inspection_runtime import digest
    (tmp_path / "media").mkdir()
    (tmp_path / "media/source.mp4").write_bytes(b"synthetic custody fixture")
    (tmp_path / "frame.jpg").write_bytes(b"synthetic frame")
    frame_hash = digest(tmp_path / "frame.jpg")
    source_hash = digest(tmp_path / "media/source.mp4")
    data = {"source_sha256": source_hash,"end_ms":3000,"source_offset_ms":0,
        "frames":[{"clip_ms":1000,"sha256":frame_hash,"image":"frame.jpg"}]}
    unit = {"unit_id":"test","kind":"observable_result","start_ms":0,"end_ms":2000,
        "sentence":"Test result.","frame_refs":[{"clip_ms":1000,"sha256":frame_hash}],
        "verdict":"accepted","reviewer":"synthetic fixture","result_evidence":"declared"}
    if attack == "pending": unit["verdict"] = "pending"
    if attack == "foreign": unit["frame_refs"][0]["sha256"] = "0"*64
    if attack == "outside": unit["end_ms"] = 4000
    (tmp_path / "units.json").write_text(json.dumps({"source_sha256":source_hash,"units":[unit]}))
    (tmp_path / "review-data.json").write_text(json.dumps(data))
    (tmp_path / "report.json").write_text(json.dumps({"review_data_sha256":digest(tmp_path / "review-data.json")}))
    if attack == "source": (tmp_path / "media/source.mp4").write_bytes(b"changed")
    if attack == "frame": (tmp_path / "frame.jpg").write_bytes(b"changed")
    with pytest.raises(ValueError): evaluate(tmp_path,tmp_path / "units.json",tmp_path / "out",
        frames=0 if attack == "budget" else 16,ffmpeg="must-not-execute")
    assert not (tmp_path / "out").exists()
