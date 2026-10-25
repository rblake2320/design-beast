import math
import json
import pytest
from scripts.narrate_watch_training import segment_duration
from scripts.draft_watch_explanations import Explanation, caption_text
from pydantic import ValidationError
from scripts.narrate_watch_training import narrate
from watch.inspection_runtime import digest


@pytest.mark.parametrize("source,audio", [(2,1.5), (5,1), (.5,.1), (119,119)])
def test_narration_never_cuts_off_audio_or_source(source, audio):
    duration = segment_duration(source, audio)
    assert duration >= source and duration >= audio+.25
    assert math.isclose(duration*30, round(duration*30))


@pytest.mark.parametrize("source,audio", [(0,1),(-1,2),(2,float('nan')),(float('inf'),1),(2,120)])
def test_invalid_or_unbounded_duration_refused(source,audio):
    with pytest.raises(ValueError): segment_duration(source,audio)


@pytest.mark.parametrize("source,audio", [(2,12.608),(2,12.714666),(2,9.173333),(.5,.5),(20,23)])
def test_excessive_holds_request_recapture(source,audio):
    from scripts.narrate_watch_training import PacingReviewRequired
    with pytest.raises(PacingReviewRequired): segment_duration(source,audio)


def test_model_cannot_promote_procedure():
    with pytest.raises(ValidationError):
        Explanation.model_validate_json('{"caption":"Something visible changed.","uncertainty":"Cause unknown.","verified_procedure":true}')


def test_model_certainty_never_removes_causal_caution():
    observation = Explanation(caption="A different view is visible.", uncertainty="No uncertainty whatsoever.")
    text = caption_text(observation)
    assert text.endswith("The input or cause is not established by these frames.")
    assert "No uncertainty" not in text


@pytest.mark.parametrize("fault", ["media", "promotion", "negative", "approval", "segment", "blank"])
def test_narration_preflight_denies_before_model_loading(tmp_path, fault):
    video = tmp_path / "training-draft.mp4"
    video.write_bytes(b"synthetic fixture, not real media")
    segment = tmp_path / "segment-000.mp4"
    segment.write_bytes(b"fixture")
    row = {"caption": "Visible change.", "source_start_ms": 0, "source_end_ms": 1000,
        "review_state": "uncertain", "requires_human_approval": True, "segment_sha256": digest(segment)}
    report = {"publication_allowed": False, "verified_procedure": False, "output_sha256": digest(video), "segments": [row]}
    if fault == "media": report["output_sha256"] = "0"*64
    if fault == "promotion": report["verified_procedure"] = True
    if fault == "negative": row["source_end_ms"] = -1
    if fault == "approval": row["requires_human_approval"] = False
    if fault == "segment": row["segment_sha256"] = "0"*64
    if fault == "blank": row["caption"] = " "
    (tmp_path / "report.json").write_text(json.dumps(report))
    with pytest.raises(ValueError):
        narrate(tmp_path, tmp_path / "out", tmp_path / "nonexistent-model")
    assert not (tmp_path / "out").exists()
