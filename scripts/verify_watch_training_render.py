"""Verify multi-segment real rendering, clip clocks, and actual decoded source pixels."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import retain, digest
from scripts.render_watch_training import render


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    data = json.loads((args.review / "review-data.json").read_text())
    captions = ["W"*500, "Actual source footage. The input causing this visual change is not established."]
    steps = [{"start_ms": i*1000, "end_ms": (i+1)*1000, "caption": caption,
        "frame_refs": [{"clip_ms": f["clip_ms"], "sha256": f["sha256"]} for f in data["frames"] if i*1000 <= f["clip_ms"] <= (i+1)*1000],
        "review_state": "uncertain", "requires_human_approval": True} for i, caption in enumerate(captions)]
    plan = {"schema_version": "beast.watch.training-draft/v1", "source_sha256": data["source_sha256"],
        "source_duration_ms": data["end_ms"], "visual_policy": "original_source_only", "publication_allowed": False, "steps": steps}
    retain(args.output / "plan.json", plan)
    render(args.review, args.output / "plan.json", args.output / "render", "ffmpeg", "ffprobe")
    video = args.output / "render/training-draft.mp4"
    result = json.loads((args.output / "render/report.json").read_text())
    errors = []
    for time in (.5, 1.5):
        frames = []
        for source, crop in [(args.review / "media/source.mp4", "null"), (video, "crop=iw:720:0:0")]:
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(time), "-i", str(source), "-frames:v", "1",
                "-vf", crop, "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"], capture_output=True, check=True, timeout=30).stdout
            frames.append(np.frombuffer(raw, dtype=np.uint8).astype(np.int16))
        assert frames[0].shape == frames[1].shape
        errors.append(float(np.abs(frames[0]-frames[1]).mean()))
    assert max(errors) < 8, errors
    assert result["segments"][0]["original_source_start_ms"] == data["source_offset_ms"]
    assert len(result["segments"]) == 2 and result["duration_ms"] == 2000
    rendered_width = result["probe"]["streams"][0]["width"]
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(video), "-frames:v", "1",
        "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"], capture_output=True, check=True, timeout=30).stdout
    decoded = np.frombuffer(raw, dtype=np.uint8).reshape((-1, rendered_width, 3))
    lines = (args.output / "render/caption-000.txt").read_text().splitlines()
    font_size = max(12, min(24, rendered_width//55))
    visible_lines = 0
    for index, line in enumerate(lines):
        if not line:
            continue
        top = 720+20+index*(font_size+6)
        region = decoded[top:top+font_size+6]
        assert ((region > 180).all(axis=2)).sum() > 50, f"caption line {index} absent"
        assert not (region[:, -24:] > 180).all(axis=2).any(), "caption exceeds right margin"
        visible_lines += 1
    subprocess.run(["ffmpeg", "-v", "error", "-n", "-ss", "0.5", "-i", str(video), "-frames:v", "1",
        str(args.output / "preview.png")], check=True, capture_output=True, timeout=30)
    retain(args.output / "verification.json", {"output_sha256": digest(video), "segments": 2,
        "source_offset_ms": data["source_offset_ms"], "decoded_source_mean_absolute_pixel_error": errors,
        "long_caption_characters": 500, "generated_visuals": 0, "publication_allowed": False,
        "visible_nonempty_caption_lines": visible_lines,
        "fixture_boundary": "two-second 1280x720 real Blender source; captions operator-authored"})


if __name__ == "__main__":
    main()
