import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from watch.training_draft import TrainingDraft
from scripts.render_watch_training import render
from scripts.watch_perception import clip_stamps


def test_source_offset_is_not_playback_time():
    timeline = {"source": {"range": {"start_seconds": 1800}}, "frames": [
        {"source_seconds": 1800, "clip_seconds": 0}, {"source_seconds": 1800.5, "clip_seconds": .5}]}
    assert clip_stamps(timeline) == [0, 500]
    timeline["frames"][1]["clip_seconds"] = 1800.5
    with pytest.raises(ValueError, match="clocks disagree"):
        clip_stamps(timeline)


def plan():
    return dict(schema_version="beast.watch.training-draft/v1", source_sha256="a"*64,
        source_duration_ms=2000, visual_policy="original_source_only", publication_allowed=False,
        steps=[dict(start_ms=0, end_ms=1000, caption="Visible change, cause unknown.",
            frame_refs=[dict(clip_ms=500, sha256="b"*64)], review_state="uncertain", requires_human_approval=True)])


def test_valid_draft_remains_uncertain():
    value = TrainingDraft.model_validate_json(json.dumps(plan()))
    assert not value.publication_allowed
    assert value.steps[0].review_state == "uncertain"


@pytest.mark.parametrize("mutation", ["promotion", "generated", "outside", "blank", "short", "causal", "approval", "extra"])
def test_invalid_draft_fails_closed(mutation):
    value = copy.deepcopy(plan())
    step = value["steps"][0]
    if mutation == "promotion": value["publication_allowed"] = True
    if mutation == "generated": value["visual_policy"] = "generated"
    if mutation == "outside": step["end_ms"] = 3000
    if mutation == "blank": step["caption"] = "   "
    if mutation == "short": step["end_ms"] = 100
    if mutation == "causal": step["review_state"] = "verified_procedure"
    if mutation == "approval": step["requires_human_approval"] = False
    if mutation == "extra": step["execute"] = "click"
    with pytest.raises(ValidationError):
        TrainingDraft.model_validate_json(json.dumps(value))


def test_changed_review_fails_before_output(tmp_path: Path):
    (tmp_path / "plan.json").write_text(json.dumps(plan()))
    (tmp_path / "review-data.json").write_text("{}")
    (tmp_path / "report.json").write_text(json.dumps({"review_data_sha256": "0"*64}))
    with pytest.raises(ValueError, match="review data changed"):
        render(tmp_path, tmp_path / "plan.json", tmp_path / "out", "no-ffmpeg", "no-ffprobe")
    assert not (tmp_path / "out").exists()
