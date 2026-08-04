"""Core utilities for evidence-first tutorial video ingestion.

This module deliberately does not call a vision-language model.  It constructs a
small, timestamp-accurate evidence set that a model can inspect, re-inspect, and
turn into a procedure without pretending sparse uniform frames are continuous
video understanding.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SCHEMA_VERSION = "beast.watch.timeline/v3"


class WatchError(RuntimeError):
    """Actionable video ingestion failure."""


@dataclass(frozen=True)
class Sample:
    time: float
    reasons: tuple[str, ...]


def parse_timecode(value: str | float | int | None) -> float | None:
    """Parse seconds, MM:SS, or HH:MM:SS into seconds."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        if value < 0:
            raise ValueError("time cannot be negative")
        return float(value)
    parts = value.strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"invalid timecode: {value}")
    try:
        nums = [float(part) for part in parts]
    except ValueError as exc:
        raise ValueError(f"invalid timecode: {value}") from exc
    if any(part < 0 for part in nums) or any(part >= 60 for part in nums[1:]):
        raise ValueError(f"invalid timecode: {value}")
    while len(nums) < 3:
        nums.insert(0, 0.0)
    return nums[0] * 3600 + nums[1] * 60 + nums[2]


def format_time(seconds: float) -> str:
    milliseconds = round(max(0.0, seconds) * 1000)
    hours, rem = divmod(milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def frame_name(source_seconds: float) -> str:
    return f"f_{round(source_seconds * 1000):012d}.jpg"


def parse_dense_window(value: str) -> tuple[float, float, float]:
    """Parse START-END[@FPS], for example ``12:04-12:12@4``."""
    body, _, fps_text = value.partition("@")
    match = re.match(r"^(.+)-([^-]+)$", body)
    if not match:
        raise ValueError("dense window must be START-END[@FPS]")
    start = parse_timecode(match.group(1))
    end = parse_timecode(match.group(2))
    fps = float(fps_text) if fps_text else 3.0
    if start is None or end is None or end <= start or not 0.1 <= fps <= 10:
        raise ValueError("dense window needs end > start and fps between 0.1 and 10")
    return start, end, fps


def build_sampling_plan(
    duration: float,
    *,
    source_offset: float = 0.0,
    scene_times: Iterable[float] = (),
    periodic_seconds: float = 10.0,
    dense_windows: Iterable[tuple[float, float, float]] = (),
    max_frames: int = 240,
    merge_within: float = 0.18,
) -> list[Sample]:
    """Merge scene, periodic, and targeted samples into a bounded plan.

    All input/output times are source-video times. ``duration`` describes the
    selected clip and ``source_offset`` maps it back to the original source.
    Scene evidence is kept ahead of periodic safety samples when a hard cap is
    necessary; targeted dense windows receive the highest priority.
    """
    if duration <= 0 or periodic_seconds <= 0 or max_frames < 1:
        raise ValueError("duration, periodic interval, and max frames must be positive")
    clip_end = source_offset + duration
    candidates: list[tuple[float, str, int]] = []
    cursor = source_offset + min(periodic_seconds / 2, duration / 2)
    while cursor < clip_end:
        candidates.append((cursor, "periodic", 1))
        cursor += periodic_seconds
    for time_ in scene_times:
        if source_offset <= time_ <= clip_end:
            candidates.append((time_, "scene_change", 2))
    for start, end, fps in dense_windows:
        start, end = max(start, source_offset), min(end, clip_end)
        if end <= start:
            continue
        step = 1.0 / fps
        count = int(math.floor((end - start) / step)) + 1
        for i in range(count):
            candidates.append((min(start + i * step, end), "targeted_dense", 3))

    merged: list[tuple[float, set[str], int]] = []
    for time_, reason, priority in sorted(candidates):
        if merged and abs(time_ - merged[-1][0]) <= merge_within:
            old_time, reasons, old_priority = merged[-1]
            reasons.add(reason)
            # Preserve the more important sample's precise timestamp.
            merged[-1] = ((time_ if priority > old_priority else old_time),
                          reasons, max(priority, old_priority))
        else:
            merged.append((time_, {reason}, priority))

    if len(merged) > max_frames:
        # Keep all high-value samples where possible, then distribute remaining
        # slots uniformly instead of biasing toward the beginning of the video.
        mandatory = [row for row in merged if row[2] >= 2]
        optional = [row for row in merged if row[2] < 2]
        if len(mandatory) >= max_frames:
            ranked = sorted(mandatory, key=lambda row: (-row[2], row[0]))
            selected = _even_pick(ranked, max_frames)
        else:
            selected = mandatory + _even_pick(optional, max_frames - len(mandatory))
        merged = sorted(selected)
    return [Sample(time=row[0], reasons=tuple(sorted(row[1]))) for row in merged]


def _even_pick(rows: list[tuple], count: int) -> list[tuple]:
    if count <= 0 or not rows:
        return []
    if count >= len(rows):
        return rows
    if count == 1:
        return [rows[len(rows) // 2]]
    indexes = {round(i * (len(rows) - 1) / (count - 1)) for i in range(count)}
    return [rows[index] for index in sorted(indexes)]


def probe_video(ffprobe: str, video: Path) -> dict:
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-print_format", "json", "-show_format",
         "-show_streams", str(video)], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise WatchError(f"ffprobe failed: {proc.stderr[-500:]}")
    try:
        raw = json.loads(proc.stdout)
        duration = float(raw["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise WatchError("video duration could not be determined") from exc
    video_stream = next((s for s in raw.get("streams", [])
                         if s.get("codec_type") == "video"), {})
    return {
        "duration_seconds": duration,
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": video_stream.get("avg_frame_rate"),
        "video_codec": video_stream.get("codec_name"),
        "audio_present": any(s.get("codec_type") == "audio"
                             for s in raw.get("streams", [])),
    }


def detect_scene_times(ffmpeg: str, video: Path, threshold: float = 0.28) -> list[float]:
    """Return clip-relative scene changes using ffmpeg's scene score."""
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(video), "-an", "-vf",
         f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True, timeout=3600)
    combined = proc.stdout + "\n" + proc.stderr
    return sorted({float(match) for match in
                   re.findall(r"pts_time:([0-9]+(?:\.[0-9]+)?)", combined)})


def extract_frame(ffmpeg: str, video: Path, clip_seconds: float,
                  destination: Path, height: int) -> bool:
    proc = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", f"{clip_seconds:.3f}", "-i", str(video),
         "-frames:v", "1", "-vf", f"scale=-2:{height}", "-q:v", "3",
         str(destination), "-y"], capture_output=True, text=True, timeout=120)
    return proc.returncode == 0 and destination.exists() and destination.stat().st_size > 0


def perceptual_hash(path: Path) -> str | None:
    """Dependency-light 64-bit average hash used for duplicate grouping."""
    try:
        from PIL import Image
        with Image.open(path) as image:
            pixels = list(image.convert("L").resize((8, 8)).getdata())
        mean = sum(pixels) / len(pixels)
        bits = sum((1 << i) for i, value in enumerate(pixels) if value >= mean)
        return f"{bits:016x}"
    except Exception:
        return None


def hamming_hash(left: str | None, right: str | None) -> int | None:
    if not left or not right:
        return None
    return (int(left, 16) ^ int(right, 16)).bit_count()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def available_transcriber() -> tuple[str, list[str]] | None:
    """Find a supported local Whisper-compatible CLI."""
    ctranslate = shutil.which("whisper-ctranslate2")
    if ctranslate:
        return "whisper-ctranslate2", [ctranslate]
    whisper = shutil.which("whisper")
    if whisper:
        return "openai-whisper", [whisper]
    return None


def transcribe_local(video: Path, bundle: Path, language: str = "en") -> Path | None:
    """Run an installed local Whisper CLI and return its VTT output."""
    found = available_transcriber()
    if not found:
        return None
    _, command = found
    proc = subprocess.run(
        command + [str(video), "--language", language, "--output_format", "vtt",
                   "--output_dir", str(bundle)],
        capture_output=True, text=True, timeout=7200)
    if proc.returncode != 0:
        raise WatchError(f"local transcription failed: {proc.stderr[-500:]}")
    return next(bundle.glob(f"{video.stem}*.vtt"), None)


def clean_vtt(vtt: Path, output: Path, source_offset: float = 0.0) -> list[dict]:
    """Create timestamped text plus machine-readable transcript segments."""
    stamp: float | None = None
    segments: list[dict] = []
    seen: set[tuple[int, str]] = set()
    for raw in vtt.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(
            r"(?:(\d+):)?(\d+):(\d+)[.,](\d+)\s+-->\s+", raw.strip())
        if match:
            hours = int(match.group(1) or 0)
            stamp = source_offset + hours * 3600 + int(match.group(2)) * 60 \
                + int(match.group(3)) + float(f"0.{match.group(4)}")
            continue
        text = re.sub(r"<[^>]+>", "", raw).strip()
        if not text or text.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        key = (round(stamp or source_offset), text)
        if key in seen:
            continue
        seen.add(key)
        segments.append({"time_seconds": stamp, "time": format_time(stamp or source_offset),
                         "text": text})
    output.write_text("\n".join(f"[{row['time']}] {row['text']}" for row in segments),
                      encoding="utf-8")
    return segments
