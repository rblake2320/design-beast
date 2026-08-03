import json

import pytest

import watch.seek as seek


def test_seek_times_supports_rewind_forward_and_bounds():
    both = seek.seek_times(10, 0, 20, before=2, after=1, fps=2, direction="both")
    assert both[0] == 8
    assert both[-1] == 11
    assert seek.seek_times(1, 0, 20, before=5, after=2, fps=1,
                           direction="back") == [0, 1]
    assert seek.seek_times(19, 0, 20, before=2, after=5, fps=1,
                           direction="forward") == [19, 20]


@pytest.mark.parametrize(("confidence", "missing", "rapid", "level"), [
    (0.9, False, False, None),
    (0.7, False, False, 1),
    (0.6, False, False, 2),
    (0.9, True, False, 2),
    (0.9, False, True, 3),
    (0.2, False, False, 3),
])
def test_escalation_policy(confidence, missing, rapid, level):
    assert seek.escalation_for(confidence, missing, rapid) == level


def test_resolve_center():
    timeline = {"frames": [{"id": "frame-0002", "source_seconds": 12.5}]}
    assert seek.resolve_center(timeline, frame_id="frame-0002") == 12.5
    assert seek.resolve_center(timeline, at=8) == 8
    with pytest.raises(seek.SeekError):
        seek.resolve_center(timeline, frame_id="missing")


def test_reinspect_revises_timeline_and_records_reason(tmp_path, monkeypatch):
    bundle = tmp_path
    (bundle / "frames").mkdir()
    (bundle / "video.mp4").write_bytes(b"video")
    timeline = {
        "schema": "beast.watch.timeline/v3",
        "source": {"local_video": "video.mp4", "range": {
            "start_seconds": 100, "end_seconds": 110,
            "start": "00:01:40.000", "end": "00:01:50.000"}},
        "sampling": {"height": 720}, "coverage": {}, "frames": [],
        "bundle_fingerprint": "old",
    }
    (bundle / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")

    def fake_extract(_ffmpeg, _video, _clip_seconds, destination, _height):
        destination.write_bytes(b"frame")
        return True

    monkeypatch.setattr(seek, "extract_frame", fake_extract)
    monkeypatch.setattr(seek, "perceptual_hash", lambda _: "0000000000000000")
    result = seek.reinspect(bundle, "ffmpeg", center=105, level=2,
                            direction="both", reason="menu item was missed")
    updated = json.loads((bundle / "timeline.json").read_text(encoding="utf-8"))
    assert result["new_frames"] > 0
    assert updated["evidence_requests"][0]["reason"] == "menu item was missed"
    assert updated["frames"][0]["source_seconds"] >= 102
    assert updated["frames"][-1]["source_seconds"] <= 108
    assert updated["bundle_fingerprint"] != "old"
    assert all(row["sha256"] for row in updated["frames"])


def test_reinspect_reextracts_before_backfilling_missing_v3_hash(tmp_path, monkeypatch):
    bundle = tmp_path
    (bundle / "frames").mkdir()
    (bundle / "video.mp4").write_bytes(b"video")
    frame = bundle / "frames" / "f_000000005000.jpg"
    frame.write_bytes(b"same-source-frame")
    timeline = {
        "schema": "beast.watch.timeline/v3",
        "source": {"local_video": "video.mp4", "range": {
            "start_seconds": 0, "end_seconds": 10,
            "start": "00:00:00.000", "end": "00:00:10.000"}},
        "sampling": {"height": 720}, "coverage": {},
        "frames": [{"id": "frame-0001", "file": "frames/f_000000005000.jpg",
                    "source_seconds": 5.0, "source_time": "00:00:05.000",
                    "perceptual_hash": "0", "reasons": []}],
        "bundle_fingerprint": "old",
    }
    (bundle / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")

    def fake_extract(_ffmpeg, _video, _clip_seconds, destination, _height):
        destination.write_bytes(b"same-source-frame")
        return True

    monkeypatch.setattr(seek, "extract_frame", fake_extract)
    seek.reinspect(bundle, "ffmpeg", center=5, level=3, before=0, after=0, fps=1)
    updated = json.loads((bundle / "timeline.json").read_text(encoding="utf-8"))
    assert updated["frames"][0]["sha256"] == seek.sha256(frame)
    assert not list((bundle / "frames").glob("*.verify.jpg"))
