import hashlib

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")
from watch.visual_state import VisualStateTracker, decode_verified, text_lines

EMPTY = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"


def textured():
    image = np.zeros((200, 300, 3), dtype=np.uint8)
    rng = np.random.default_rng(7)
    for x, y in rng.integers((20, 20), (280, 180), (70, 2)):
        cv2.rectangle(image, (int(x), int(y)), (int(x)+4, int(y)+4), (255, 255, 255), -1)
    return image


def test_tracks_retain_identity_and_measure_translation():
    tracker = VisualStateTracker()
    a = textured()
    tracker.update(a, 0, "a"*64, EMPTY)
    b = cv2.warpAffine(a, np.float32([[1, 0, 3], [0, 1, 2]]), (300, 200))
    second = tracker.update(b, 100, "b"*64, EMPTY)
    third = tracker.update(b, 200, "c"*64, EMPTY)
    assert len(second.motion_tracks) > 20
    delta = np.median([np.array(t.after)-np.array(t.before) for t in second.motion_tracks], axis=0)
    assert delta == pytest.approx([3, 2], abs=.2)
    assert set(t.track_id for t in second.motion_tracks) & set(t.track_id for t in third.motion_tracks)
    assert third.changed_pixel_fraction == 0
    assert second.procedure_confidence is None


def test_scale_measurement_is_not_object_action():
    a = textured()
    tracker = VisualStateTracker()
    tracker.update(a, 0, "a"*64, EMPTY)
    b = cv2.warpAffine(a, cv2.getRotationMatrix2D((150, 100), 0, .94), (300, 200))
    result = tracker.update(b, 100, "b"*64, EMPTY)
    assert result.motion_scale == pytest.approx(.94, abs=.02)
    assert result.evidence_class == "pixel_measurement_not_semantic_verdict"


def test_cut_and_time_gap_reset_correspondence():
    tracker = VisualStateTracker()
    a = textured()
    tracker.update(a, 0, "a"*64, EMPTY)
    state = tracker.update(np.full_like(a, 255), 100, "b"*64, EMPTY)
    assert state.tracking_reset and not state.motion_tracks
    gap = tracker.update(a, 2000, "c"*64, EMPTY)
    assert gap.tracking_reset and not gap.motion_tracks


def test_text_requires_same_string_and_spatial_overlap():
    tracker = VisualStateTracker()
    row = "5\t1\t1\t1\t1\t1\t10\t10\t50\t15\t95\tObject\n"
    a = textured()
    first = tracker.update(a, 0, "a"*64, EMPTY+row)
    second = tracker.update(a, 100, "b"*64, EMPTY+row)
    assert first.text_elements[0].track_id == second.text_elements[0].track_id
    assert second.text_elements[0].consecutive_frames == 2
    assert not second.appeared_text_track_ids
    third = tracker.update(a, 200, "c"*64, EMPTY+row.replace("Object", "Sculpt"))
    assert third.appeared_text_track_ids and third.disappeared_text_track_ids


def test_out_of_bounds_ocr_and_duplicate_time_rejected():
    with pytest.raises(ValueError, match="outside"):
        text_lines(EMPTY+"5\t1\t1\t1\t1\t1\t299\t10\t50\t15\t95\tBad\n", 300, 200)
    tracker = VisualStateTracker()
    tracker.update(textured(), 0, "a"*64, EMPTY)
    with pytest.raises(ValueError, match="increase"):
        tracker.update(textured(), 0, "a"*64, EMPTY)


def test_decode_rejects_tampered_source(tmp_path):
    path = tmp_path / "frame.png"
    cv2.imwrite(str(path), textured())
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert decode_verified(path, expected).shape == (200, 300, 3)
    with pytest.raises(ValueError, match="custody"):
        decode_verified(path, "0"*64)
