"""Decode actual narrated output and compare its spoken words, source pixels and held frames."""
from __future__ import annotations
import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import digest, retain


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--narrated", type=Path, required=True)
    parser.add_argument("--rendered", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = json.loads((args.narrated / "report.json").read_bytes())
    video = args.narrated / "narrated-training.mp4"
    assert digest(video) == report["output_sha256"]
    audio = args.output / "decoded.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-n", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(audio)], check=True, capture_output=True, timeout=30)
    samples, sr = sf.read(audio)
    assert np.isfinite(samples).all() and float(np.sqrt(np.mean(samples**2))) > .005
    from faster_whisper import WhisperModel
    recognizer = WhisperModel("base.en", device="cpu", compute_type="int8", cpu_threads=4)
    parts, _ = recognizer.transcribe(str(audio), beam_size=5)
    spoken = " ".join(p.text.strip() for p in parts)
    expected = " ".join(s["source"]["caption"] for s in report["segments"])
    normalize = lambda s: re.findall(r"[a-z0-9]+", s.lower())
    similarity = difflib.SequenceMatcher(None, normalize(expected), normalize(spoken)).ratio()
    assert similarity >= .85, (expected, spoken, similarity)
    def pixels(path: Path, seconds: float) -> np.ndarray:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(seconds), "-i", str(path), "-frames:v", "1",
            "-vf", "crop=1280:720:0:0", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"], capture_output=True, check=True, timeout=30).stdout
        return np.frombuffer(raw, dtype=np.uint8).astype(np.int16)
    errors = []
    held_errors = []
    for i, segment in enumerate(report["segments"]):
        errors.append(float(np.abs(pixels(video, segment["output_start_seconds"]+.5)-pixels(args.rendered / f"segment-{i:03d}.mp4", .5)).mean()))
        if segment["held_seconds"] > .5:
            original_seconds = (segment["source"]["source_end_ms"]-segment["source"]["source_start_ms"])/1000
            held_errors.append(float(np.abs(pixels(video, segment["output_start_seconds"]+original_seconds+.25)
                -pixels(args.rendered / f"segment-{i:03d}.mp4", original_seconds-1/30)).mean()))
    assert max(errors) < 8, errors
    assert all(error < 8 for error in held_errors), held_errors
    retain(args.output / "report.json", {"output_sha256": digest(video), "expected_words": expected, "recognized_words": spoken,
        "word_sequence_similarity": similarity, "audio_rms": float(np.sqrt(np.mean(samples**2))),
        "source_region_pixel_errors": errors, "held_source_pixel_errors": held_errors,
        "asr": "faster-whisper base.en CPU int8; transcription is fallible",
        "boundary": "1280x720 fixture; speech-content check, not semantic correctness of explanation"})


if __name__ == "__main__":
    main()
