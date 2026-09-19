"""Add local synthetic narration to hash-verified Watch draft segments."""
from __future__ import annotations
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import digest, retain


def segment_duration(source_seconds: float, audio_seconds: float) -> float:
    if not all(math.isfinite(t) and t > 0 for t in (source_seconds, audio_seconds)):
        raise ValueError("invalid source or audio duration")
    duration = math.ceil(max(source_seconds, audio_seconds+.25)*30)/30
    if duration > 120:
        raise ValueError("narrated segment exceeds120s budget")
    return duration


def narrate(rendered: Path, output: Path, model_dir: Path) -> None:
    report = json.loads((rendered / "report.json").read_bytes())
    if report.get("publication_allowed") is not False or report.get("verified_procedure") is not False:
        raise ValueError("only private unverified drafts may be narrated")
    if digest(rendered / "training-draft.mp4") != report["output_sha256"]:
        raise ValueError("draft media changed")
    segments = report["segments"]
    if not 1 <= len(segments) <= 50:
        raise ValueError("invalid segment count")
    for index, segment in enumerate(segments):
        if type(segment["source_start_ms"]) is not int or type(segment["source_end_ms"]) is not int or segment["source_start_ms"] < 0:
            raise ValueError("invalid source interval coordinates")
        if segment.get("review_state") != "uncertain" or segment.get("requires_human_approval") is not True:
            raise ValueError("segment lacks required uncertainty/review boundary")
        segment_duration((segment["source_end_ms"]-segment["source_start_ms"])/1000, .1)
        if not isinstance(segment["caption"], str) or not 1 <= len(segment["caption"].strip()) <= 500:
            raise ValueError("invalid narration text")
        if digest(rendered / f"segment-{index:03d}.mp4") != segment["segment_sha256"]:
            raise ValueError("segment media changed")
    model = model_dir / "kokoro-v1.0.onnx"
    voices = model_dir / "voices-v1.0.bin"
    model_hash, voices_hash = digest(model), digest(voices)
    for index, segment in enumerate(segments):
        measured = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json",
            str(rendered / f"segment-{index:03d}.mp4")], check=True, capture_output=True, timeout=30).stdout)
        expected = (segment["source_end_ms"]-segment["source_start_ms"])/1000
        if abs(float(measured["format"]["duration"])-expected) > .15:
            raise ValueError("actual source segment duration differs from its interval")
    output.mkdir(parents=True, exist_ok=False)
    retain(output / "intent.json", {"operation": "synthetic_narration", "render_report_sha256": digest(rendered / "report.json"),
        "model_sha256": model_hash, "voices_sha256": voices_hash, "provider": "CPUExecutionProvider",
        "voice": "af_heart", "cloned_voice": False, "publication_allowed": False})
    try:
        import numpy as np
        import soundfile as sf
        os.environ["ONNX_PROVIDER"] = "CPUExecutionProvider"
        from kokoro_onnx import Kokoro
        engine = Kokoro(str(model), str(voices))
        if engine.sess.get_providers() != ["CPUExecutionProvider"]:
            raise ValueError("unexpected execution provider")
        shutil.copyfile(rendered / "caption-font.ttf", output / "caption-font.ttf")
        timing = []
        cursor = 0
        for index, segment in enumerate(segments):
            text = segment["caption"]
            samples, sr = engine.create(text, voice="af_heart", speed=1.0)
            if sr != 24000 or samples.ndim != 1 or not np.isfinite(samples).all() or len(samples) < 2400 or float(np.max(np.abs(samples))) < .001:
                raise ValueError("narrator returned invalid or silent audio")
            audio_seconds = len(samples)/sr
            source_seconds = (segment["source_end_ms"]-segment["source_start_ms"])/1000
            duration = segment_duration(source_seconds, audio_seconds)
            wav = f"voice-{index:03d}.wav"
            sf.write(str(output / wav), samples, sr, subtype="PCM_16")
            clip = f"narrated-{index:03d}.mp4"
            # Hold the actual last source frame, explicitly labeled; never synthesize a replacement scene.
            filters = f"tpad=stop_mode=clone:stop_duration={duration},pad=iw:ih+90:0:0:color=black,drawtext=fontfile=caption-font.ttf:text='SYNTHETIC NARRATION / EDITORIAL DRAFT':fontsize=18:fontcolor=white:x=24:y=h-75,drawtext=fontfile=caption-font.ttf:text='HELD SOURCE FRAME':fontsize=18:fontcolor=white:x=24:y=h-45:enable='gte(t,{source_seconds})'"
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-n", "-i", str((rendered / f"segment-{index:03d}.mp4").resolve()),
                "-i", wav, "-map", "0:v:0", "-map", "1:a:0", "-vf", filters, "-af", "apad", "-t", str(duration), "-c:v", "libx264", "-threads", "2",
                "-preset", "fast", "-crf", "18", "-c:a", "aac", "-movflags", "+faststart", clip],
                cwd=output, check=True, capture_output=True, timeout=180)
            timing.append({"output_start_seconds": cursor, "output_end_seconds": cursor+duration,
                "audio_seconds": audio_seconds, "held_seconds": duration-source_seconds,
                "source": segment, "wav_sha256": digest(output / wav), "clip_sha256": digest(output / clip)})
            cursor += duration
        with (output / "concat.txt").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write("".join(f"file 'narrated-{i:03d}.mp4'\n" for i in range(len(segments))))
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-n", "-f", "concat", "-safe", "1", "-i", "concat.txt",
            "-c", "copy", "-movflags", "+faststart", "narrated-training.mp4"], cwd=output, check=True, capture_output=True, timeout=180)
        probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
            "-of", "json", "narrated-training.mp4"], cwd=output, check=True, capture_output=True, timeout=30).stdout)
        if {s["codec_type"] for s in probe["streams"]} != {"audio", "video"} or abs(float(probe["format"]["duration"])-cursor) > .2:
            raise ValueError("narrated output stream/timing mismatch")
        retain(output / "report.json", {"output_sha256": digest(output / "narrated-training.mp4"), "segments": timing,
            "probe": probe, "publication_allowed": False, "verified_procedure": False,
            "audio": "local Kokoro af_heart synthetic voice; not source speaker", "generated_scene_images": 0})
    except Exception as exc:
        retain(output / "failure.json", {"error": str(exc), "type": type(exc).__name__})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("rendered", "output", "model-dir"):
        parser.add_argument("--"+key, type=Path, required=True)
    args = parser.parse_args()
    narrate(args.rendered.resolve(), args.output.resolve(), args.model_dir.resolve())


if __name__ == "__main__":
    main()
