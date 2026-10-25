"""Render a private captioned draft using only exact reviewed source intervals."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import digest, retain
from watch.training_draft import TrainingDraft


def render(review: Path, plan_path: Path, output: Path, ffmpeg: str, ffprobe: str) -> None:
    plan = TrainingDraft.model_validate_json(plan_path.read_bytes())
    data = json.loads((review / "review-data.json").read_text(encoding="utf-8"))
    receipt = json.loads((review / "report.json").read_text(encoding="utf-8"))
    if receipt["review_data_sha256"] != digest(review / "review-data.json"):
        raise ValueError("review data changed after packaging")
    if plan.source_sha256 != data["source_sha256"] or plan.source_duration_ms != data["end_ms"]:
        raise ValueError("plan belongs to a different source")
    allowed = {(f["clip_ms"], f["sha256"]) for f in data["frames"]}
    for step in plan.steps:
        if any((ref.clip_ms, ref.sha256) not in allowed for ref in step.frame_refs):
            raise ValueError("draft cites unknown source frames")
    for frame in data["frames"]:
        path = (review / frame["image"]).resolve()
        if not path.is_relative_to(review.resolve()) or digest(path) != frame["sha256"]:
            raise ValueError("review frame custody mismatch")
    source = review / "media/source.mp4"
    if digest(source) != plan.source_sha256:
        raise ValueError("source media changed")
    output.mkdir(parents=True, exist_ok=False)
    retain(output / "intent.json", {"plan_sha256": digest(plan_path), "source_sha256": plan.source_sha256,
        "mode": "private_captioned_draft", "publication_allowed": False, "audio": "not generated",
        "visuals": "source footage only; draft caption band below, no replacement images"})
    try:
        shutil.copyfile(source, output / "source.mp4")
        if digest(output / "source.mp4") != plan.source_sha256:
            raise ValueError("render source copy differs")
        metadata = json.loads(subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "json", "source.mp4"], cwd=output,
            check=True, capture_output=True, timeout=30).stdout)["streams"][0]
        width, height = metadata["width"], metadata["height"]
        if width < 320 or height < 180 or width*height > 16_000_000:
            raise ValueError("unsupported source dimensions")
        clips = []
        timing = []
        cursor = 0
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf"
        if not font.is_file():
            font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        if not font.is_file():
            raise ValueError("caption font unavailable: install Segoe UI or DejaVu Sans")
        shutil.copyfile(font, output / "caption-font.ttf")
        font_size = max(12, min(24, width//55))
        wrap_width = max(1, (width-48)//font_size)
        captions = []
        for step in plan.steps:
            lines = textwrap.wrap("DRAFT / SOURCE FOOTAGE / EDITORIAL REVIEW REQUIRED", width=wrap_width)
            lines += [""] + textwrap.wrap(" ".join(step.caption.split()), width=wrap_width)
            captions.append(lines)
        band_height = (max(map(len, captions))*(font_size+6)+40+1)//2*2
        for index, step in enumerate(plan.steps):
            caption_name = f"caption-{index:03d}.txt"
            caption = "\n".join(captions[index])
            with (output / caption_name).open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(caption)
            clip = f"segment-{index:03d}.mp4"
            duration = (step.end_ms-step.start_ms)/1000
            # Fixed filenames; caption content is read literally, never interpolated
            # into a filter expression or shell command.
            filters = f"pad=ceil(iw/2)*2:ceil(ih/2)*2+{band_height}:0:0:color=0x101713"
            for line_index, line in enumerate(captions[index]):
                if not line:
                    continue
                line_file = f"caption-{index:03d}-line-{line_index:03d}.txt"
                with (output / line_file).open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(line)
                filters += f",drawtext=fontfile=caption-font.ttf:textfile={line_file}:expansion=none:fontcolor=white:fontsize={font_size}:x=24:y={height+20+line_index*(font_size+6)}"
            subprocess.run([ffmpeg, "-v", "error", "-nostdin", "-n", "-ss", str(step.start_ms/1000),
                "-i", "source.mp4", "-t", str(duration), "-an", "-vf", filters, "-r", "30",
                "-c:v", "libx264", "-threads", "2", "-preset", "fast", "-crf", "18",
                "-pix_fmt", "yuv420p", clip], cwd=output, check=True, capture_output=True, timeout=120)
            clips.append(clip)
            timing.append({"output_start_ms": cursor, "output_end_ms": cursor+step.end_ms-step.start_ms,
                "source_start_ms": step.start_ms, "source_end_ms": step.end_ms, "caption": step.caption,
                "original_source_start_ms": data["source_offset_ms"]+step.start_ms,
                "original_source_end_ms": data["source_offset_ms"]+step.end_ms,
                "source_sha256": plan.source_sha256, "segment_sha256": digest(output / clip),
                "review_state": "uncertain", "requires_human_approval": True})
            cursor += step.end_ms-step.start_ms
        with (output / "concat.txt").open("x", encoding="utf-8") as stream:
            stream.write("".join(f"file '{name}'\n" for name in clips))
        subprocess.run([ffmpeg, "-v", "error", "-nostdin", "-n", "-f", "concat", "-safe", "1", "-i",
            "concat.txt", "-c", "copy", "-movflags", "+faststart", "training-draft.mp4"], cwd=output,
            check=True, capture_output=True, timeout=120)
        probe = json.loads(subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration:stream=width,height,codec_type",
            "-of", "json", "training-draft.mp4"], cwd=output, check=True, capture_output=True, timeout=30).stdout)
        if abs(float(probe["format"]["duration"])*1000-cursor) > 150:
            raise ValueError("rendered duration does not match source segment plan")
        retain(output / "report.json", {"source_sha256": plan.source_sha256, "output_sha256": digest(output / "training-draft.mp4"),
            "duration_ms": cursor, "probe": probe, "segments": timing, "generated_visuals": 0,
            "publication_allowed": False, "verified_procedure": False, "audio": "none; captions only"})
    except Exception as exc:
        retain(output / "failure.json", {"type": type(exc).__name__, "error": str(exc),
            "stderr": exc.stderr.decode("utf-8", errors="replace") if isinstance(exc, subprocess.CalledProcessError) and isinstance(exc.stderr, bytes) else None})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("review", "plan", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    render(args.review, args.plan, args.output, args.ffmpeg, args.ffprobe)


if __name__ == "__main__":
    main()
