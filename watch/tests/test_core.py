import json
import subprocess
from pathlib import Path

import pytest

from watch.core import (SCHEMA_VERSION, build_sampling_plan, clean_vtt, format_time,
                        frame_name, hamming_hash, parse_dense_window, parse_timecode)
from scripts.watch_video import _procedure_template, _select_downloaded_video, _slug


@pytest.mark.parametrize(("raw", "expected"), [
    ("90", 90), ("01:30", 90), ("1:02:03.5", 3723.5), (12.25, 12.25),
])
def test_parse_timecode(raw, expected):
    assert parse_timecode(raw) == expected


@pytest.mark.parametrize("raw", ["1:99", "-1", "a:b", "1:2:3:4"])
def test_parse_timecode_rejects_invalid(raw):
    with pytest.raises(ValueError):
        parse_timecode(raw)


def test_dense_window():
    assert parse_dense_window("12:04-12:12@4") == (724, 732, 4)


def test_sampling_merges_reasons_and_preserves_source_offset():
    samples = build_sampling_plan(
        20, source_offset=100, scene_times=[105.05, 117], periodic_seconds=10,
        dense_windows=[(104.9, 105.2, 2)], max_frames=100)
    assert all(100 <= sample.time <= 120 for sample in samples)
    combined = next(sample for sample in samples if abs(sample.time - 105.0) < 0.2)
    assert set(combined.reasons) >= {"periodic", "scene_change", "targeted_dense"}


def test_sampling_cap_is_distributed():
    samples = build_sampling_plan(1000, periodic_seconds=1, max_frames=10)
    assert len(samples) == 10
    assert samples[0].time < 100
    assert samples[-1].time > 900


def test_helpers():
    assert format_time(3723.456) == "01:02:03.456"
    assert frame_name(1.5) == "f_000000001500.jpg"
    assert hamming_hash("0000000000000000", "000000000000000f") == 4
    assert SCHEMA_VERSION.endswith("/v2")


def test_slug_uses_youtube_video_id_without_collisions():
    assert _slug("https://www.youtube.com/watch?v=alpha123") == "alpha123"
    assert _slug("https://www.youtube.com/watch?v=beta456&t=30") == "beta456"
    assert _slug("https://youtu.be/gamma789?si=x") == "gamma789"


def test_clean_vtt_preserves_source_offset(tmp_path):
    source = tmp_path / "x.vtt"
    source.write_text(
        "WEBVTT\n\n00:00:01.500 --> 00:00:03.000\nClick Compile\n",
        encoding="utf-8")
    output = tmp_path / "transcript.txt"
    rows = clean_vtt(source, output, source_offset=600)
    assert rows[0]["time_seconds"] == 601.5
    assert "00:10:01.500" in output.read_text(encoding="utf-8")


def test_download_selector_rejects_audio_only_adaptive_stream(tmp_path, monkeypatch):
    audio = tmp_path / "video.f251.webm"
    visual = tmp_path / "video.f399.mp4"
    audio.write_bytes(b"audio")
    visual.write_bytes(b"visual")

    def fake_probe(_ffprobe, path):
        if path == audio:
            return {"video_codec": None, "width": None, "height": None}
        return {"video_codec": "av1", "width": 1920, "height": 1080}

    monkeypatch.setattr("scripts.watch_video.probe_video", fake_probe)
    assert _select_downloaded_video(tmp_path, "ffprobe") == visual


def test_procedure_template_cannot_conflate_transcript_with_watching():
    template = _procedure_template({})
    watching = template["watching_evidence"]
    assert "visual_only_facts" in watching
    assert "ambiguous_segments" in watching
    assert template["publication_gate"]["visual_only_evidence_validated"] is False
