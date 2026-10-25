import pytest

pytest.importorskip("cv2")
from watch.visual_state import VisualState, MotionTrack
from watch.pixel_policy import PixelInspectionPolicy
from watch.inspection import Confidence, InspectionContext, Interval
from scripts.fuse_watch_state import validate_regions


def sample():
    return VisualState(clip_ms=500, frame_sha256="a"*64, before_sha256=None, dimensions=(100, 100),
        text_elements=(), appeared_text_track_ids=(), disappeared_text_track_ids=(), motion_tracks=(),
        region_motion=(), changed_regions=((10, 20, 30, 40),), changed_pixel_fraction=.12,
        motion_scale=None, affine_inlier_fraction=None, tracking_reset=True, uncertainty=("unknown cause",))


def test_policy_preserves_three_confidences_and_cannot_accept_evidence():
    confidence = Confidence(perception=.2, transition=.3, procedure=.1)
    context = InspectionContext(source_interval=Interval(start_ms=0, end_ms=1000),
        candidate_interval=Interval(start_ms=0, end_ms=500), confidence=confidence)
    decision = PixelInspectionPolicy(sample()).decide(context)
    assert decision.requested_action == "increase_density"
    assert decision.confidence == confidence
    assert decision.target_regions[0].x == .1
    stopped = PixelInspectionPolicy(sample()).decide(context.model_copy(update={"completed_inspections": 1}))
    assert stopped.requested_action == "stop_inspection"
    assert "verified" not in stopped.model_dump()


@pytest.mark.parametrize("region", [
    {"bbox_xyxy": [0, 0, 10, 10], "raw_score": float("nan")},
    {"bbox_xyxy": [0, 0, 101, 10], "raw_score": .5},
    {"bbox_xyxy": [10, 10, 0, 0], "raw_score": .5},
    {"bbox_xyxy": [0, 0, 10, 10], "raw_score": .5, "verified": True},
])
def test_invalid_detector_output_rejected(region):
    with pytest.raises(ValueError):
        validate_regions([region], 100, 100)


def test_ui_and_temporal_channels_only_change_inspection_request():
    state = sample().model_copy(update={"tracking_reset": False, "motion_tracks": (
        MotionTrack(track_id=1, before=(10.0, 10.0), after=(11.0, 10.0), forward_backward_error_px=.1, age_frames=2),)})
    context = InspectionContext(source_interval=Interval(start_ms=0, end_ms=1000),
        candidate_interval=Interval(start_ms=0, end_ms=500), confidence=Confidence(perception=.1, transition=.2, procedure=.0))
    assert PixelInspectionPolicy(state, ui_region_count=2).decide(context).requested_action == "run_ocr"
    assert PixelInspectionPolicy(state, temporal_change_score=.2).decide(context).requested_action == "request_slow_review"
    assert PixelInspectionPolicy(state, temporal_change_score=.2).decide(context).confidence == context.confidence
