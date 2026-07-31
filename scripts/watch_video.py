"""beast watch — build timestamped visual evidence from any tutorial video.

The watcher is deliberately hierarchical: scene changes + periodic safety
samples + optional dense windows.  It writes a machine-readable timeline that
an agent can query and revisit before compiling demonstrated work into a skill.

Examples:
  beast watch tutorial.mp4
  beast watch URL --start 12:00 --end 18:00
  beast watch tutorial.mp4 --dense-window 12:04-12:12@4
  beast watch tutorial.mp4 --periodic 6 --max-frames 300
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from watch.core import (SCHEMA_VERSION, WatchError, build_sampling_plan, clean_vtt,
                        detect_scene_times, extract_frame, format_time, frame_name,
                        hamming_hash, parse_dense_window, parse_timecode,
                        perceptual_hash, probe_video, sha256, transcribe_local)

FFMPEG_HINT = (Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
               / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
               / "ffmpeg-8.1.2-full_build/bin")


def _tool(name: str, required: bool = True) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    hinted = FFMPEG_HINT / f"{name}.exe"
    if hinted.exists():
        return str(hinted)
    if required:
        raise WatchError(f"{name} not found on PATH (checked {hinted})")
    return None


def _slug(source: str) -> str:
    raw = source.rsplit("/", 1)[-1].split("?", 1)[0] if re.match(r"^https?://", source) \
        else Path(source).stem
    return re.sub(r"[^A-Za-z0-9]+", "-", raw).strip("-")[:60] or "video"


def _download(source: str, bundle: Path, height: int,
              start: float | None, end: float | None) -> tuple[Path, float]:
    ytdlp = _tool("yt-dlp")
    output = bundle / "video.%(ext)s"
    cmd = [ytdlp, "--no-playlist",
           "-f", f"bv*[height<={height}]+ba/b[height<={height}]/b",
           "--merge-output-format", "mp4", "--write-auto-subs", "--write-subs",
           "--sub-lang", "en.*", "--sub-format", "vtt", "-o", str(output)]
    if start is not None or end is not None:
        if end is None:
            raise WatchError("--end is required when clipping a URL")
        cmd += ["--download-sections", f"*{start or 0}-{end}", "--force-keyframes-at-cuts"]
    proc = subprocess.run(cmd + [source], capture_output=True, text=True, timeout=7200)
    if proc.returncode != 0:
        raise WatchError(f"yt-dlp failed: {proc.stderr[-800:]}")
    video = next((path for path in bundle.glob("video.*")
                  if path.suffix.lower() not in (".vtt", ".part", ".ytdl")), None)
    if video is None:
        raise WatchError("download produced no video file")
    return video, start or 0.0


def _clip_local(ffmpeg: str, source: Path, bundle: Path,
                start: float | None, end: float | None) -> tuple[Path, float]:
    if start is None and end is None:
        destination = bundle / f"video{source.suffix.lower()}"
        shutil.copy2(source, destination)
        return destination, 0.0
    offset = start or 0.0
    destination = bundle / "video.mp4"
    cmd = [ffmpeg, "-v", "error", "-ss", f"{offset:.3f}", "-i", str(source)]
    if end is not None:
        if end <= offset:
            raise WatchError("--end must be after --start")
        cmd += ["-t", f"{end - offset:.3f}"]
    # Re-encode around exact requested boundaries; stream copying can begin at
    # an earlier keyframe and corrupt source timestamp alignment.
    cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-movflags", "+faststart", str(destination), "-y"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    if proc.returncode != 0:
        raise WatchError(f"local clipping failed: {proc.stderr[-800:]}")
    return destination, offset


def _caption_source(bundle: Path, video: Path, no_transcribe: bool) -> tuple[Path | None, str]:
    downloaded = next(bundle.glob("*.vtt"), None)
    if downloaded:
        return downloaded, "captions"
    if no_transcribe:
        return None, "disabled"
    vtt = transcribe_local(video, bundle)
    return (vtt, "local_whisper") if vtt else (None, "unavailable")


def _write_manifest(bundle: Path, timeline: dict) -> None:
    frames = timeline["frames"]
    transcript = timeline["transcript"]
    coverage = timeline["coverage"]
    text = f"""# Beast Watch evidence bundle

- schema: `{timeline['schema']}`
- source: {timeline['source']['input']}
- selected source range: {timeline['source']['range']['start']} – {timeline['source']['range']['end']}
- frames: {len(frames)} ({coverage['scene_samples']} scene, {coverage['dense_samples']} targeted-dense)
- transcript: {len(transcript['segments'])} segments ({transcript['method']})
- evidence fingerprint: `{timeline['bundle_fingerprint']}`

## How an agent must read this

1. Search `transcript.txt` and `timeline.json`; do not consume every image blindly.
2. Inspect scene-change frames and frames around statements such as “click”, “set”,
   “change”, “as you can see”, “before”, and “after”.
3. For any uncertain action, rerun `beast watch` with
   `--dense-window START-END@FPS` and keep the new evidence.
4. A demonstrated action is not a learned skill until it has a precondition,
   action, observed postcondition, source timestamps, executable implementation,
   and a passing validation.
5. Cite source timestamps in every extracted procedure step.

## Files

- `timeline.json`: authoritative evidence index and transcript alignment
- `transcript.txt`: human-readable timestamped narration
- `frames/`: source-timestamped evidence frames (`f_<milliseconds>.jpg`)
- `procedure.template.json`: contract for compiling evidence into a verified skill
"""
    (bundle / "MANIFEST.md").write_text(text, encoding="utf-8")


def _procedure_template(timeline: dict) -> dict:
    return {
        "schema": "beast.watch.procedure/v1",
        "source_timeline": "timeline.json",
        "goal": "",
        "application": "",
        "version_context": [],
        "prerequisites": [],
        "steps": [{
            "id": "step-001", "intent": "", "preconditions": [],
            "action": {"type": "unknown", "target": "", "operation": "", "value": None},
            "observed_postconditions": [],
            "evidence": [{"start_seconds": None, "end_seconds": None,
                          "frame_ids": [], "transcript_segment_ids": []}],
            "implementation": {"preferred": "api_or_mcp", "code": None,
                               "fallback": "gui", "confidence": 0.0},
            "validation": {"structural": [], "behavioral": [], "visual": []},
            "uncertainties": []
        }],
        "publication_gate": {
            "executed_in_sandbox": False, "structural_validation_passed": False,
            "behavioral_validation_passed": False, "visual_validation_passed": False,
            "human_approved": False
        }
    }


def run(args: argparse.Namespace) -> Path:
    ffmpeg, ffprobe = _tool("ffmpeg"), _tool("ffprobe")
    start, end = parse_timecode(args.start), parse_timecode(args.end)
    bundle = Path(args.out).resolve() if args.out else (REPO / "watched" / _slug(args.source))
    frames_dir = bundle / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    is_url = bool(re.match(r"^https?://", args.source))
    if is_url:
        video, source_offset = _download(args.source, bundle, args.height, start, end)
    else:
        source = Path(args.source).expanduser().resolve()
        if not source.is_file():
            raise WatchError(f"video not found: {source}")
        video, source_offset = _clip_local(ffmpeg, source, bundle, start, end)

    media = probe_video(ffprobe, video)
    duration = media["duration_seconds"]
    scene_relative = [] if args.no_scenes else detect_scene_times(
        ffmpeg, video, args.scene_threshold)
    scene_source = [source_offset + value for value in scene_relative]
    dense = [parse_dense_window(value) for value in args.dense_window]
    plan = build_sampling_plan(
        duration, source_offset=source_offset, scene_times=scene_source,
        periodic_seconds=args.periodic, dense_windows=dense, max_frames=args.max_frames)

    frame_rows, previous_hash = [], None
    for index, sample in enumerate(plan, 1):
        destination = frames_dir / frame_name(sample.time)
        if not extract_frame(ffmpeg, video, sample.time - source_offset,
                             destination, args.height):
            continue
        phash = perceptual_hash(destination)
        distance = hamming_hash(previous_hash, phash)
        duplicate = distance is not None and distance <= args.dedupe_distance \
            and "targeted_dense" not in sample.reasons
        row = {
            "id": f"frame-{index:04d}", "file": destination.relative_to(bundle).as_posix(),
            "source_seconds": round(sample.time, 3), "source_time": format_time(sample.time),
            "clip_seconds": round(sample.time - source_offset, 3),
            "reasons": list(sample.reasons), "perceptual_hash": phash,
            "change_from_previous": distance, "near_duplicate": duplicate,
        }
        frame_rows.append(row)
        previous_hash = phash

    vtt, transcript_method = _caption_source(bundle, video, args.no_transcribe)
    transcript_path = bundle / "transcript.txt"
    segments = clean_vtt(vtt, transcript_path, source_offset) if vtt else []
    if not segments:
        transcript_path.write_text(
            "No captions or local Whisper-compatible CLI were available. Visual evidence "
            "is still indexed; install whisper-ctranslate2 or openai-whisper and rerun.",
            encoding="utf-8")

    source_end = source_offset + duration
    fingerprint_input = "\n".join(
        f"{row['source_seconds']}:{row['perceptual_hash']}" for row in frame_rows)
    timeline = {
        "schema": SCHEMA_VERSION,
        "source": {
            "input": args.source, "is_url": is_url, "local_video": video.name,
            "sha256": sha256(video),
            "range": {"start_seconds": source_offset, "end_seconds": source_end,
                      "start": format_time(source_offset), "end": format_time(source_end)},
            "media": media,
        },
        "sampling": {
            "strategy": "scene+periodic+targeted-dense", "periodic_seconds": args.periodic,
            "scene_threshold": None if args.no_scenes else args.scene_threshold,
            "dense_windows": args.dense_window, "max_frames": args.max_frames,
            "height": args.height,
        },
        "coverage": {
            "planned_frames": len(plan), "extracted_frames": len(frame_rows),
            "scene_samples": sum("scene_change" in row["reasons"] for row in frame_rows),
            "dense_samples": sum("targeted_dense" in row["reasons"] for row in frame_rows),
            "near_duplicates": sum(row["near_duplicate"] for row in frame_rows),
        },
        "frames": frame_rows,
        "transcript": {"method": transcript_method, "file": "transcript.txt",
                       "segments": [{"id": f"speech-{i:04d}", **row}
                                    for i, row in enumerate(segments, 1)]},
        "bundle_fingerprint": __import__("hashlib").sha256(
            fingerprint_input.encode()).hexdigest(),
        "learning_contract": {
            "unit": "precondition -> action -> observed_postcondition",
            "requires_source_evidence": True,
            "requires_sandbox_execution": True,
            "requires_validation": ["structural", "behavioral", "visual"],
        },
    }
    (bundle / "timeline.json").write_text(json.dumps(timeline, indent=2), encoding="utf-8")
    (bundle / "procedure.template.json").write_text(
        json.dumps(_procedure_template(timeline), indent=2), encoding="utf-8")
    _write_manifest(bundle, timeline)
    return bundle


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", help="yt-dlp-supported URL or local video")
    ap.add_argument("--start", help="source HH:MM:SS, MM:SS, or seconds")
    ap.add_argument("--end", help="source HH:MM:SS, MM:SS, or seconds")
    ap.add_argument("--periodic", type=float, default=10.0,
                    help="fallback sample interval in seconds (default: 10)")
    ap.add_argument("--dense-window", action="append", default=[], metavar="START-END@FPS",
                    help="targeted reinspection window; repeatable")
    ap.add_argument("--max-frames", type=int, default=240)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--scene-threshold", type=float, default=0.28)
    ap.add_argument("--no-scenes", action="store_true")
    ap.add_argument("--no-transcribe", action="store_true")
    ap.add_argument("--dedupe-distance", type=int, default=3,
                    help="aHash Hamming distance marked near-duplicate")
    ap.add_argument("--out")
    return ap


def main() -> int:
    try:
        args = parser().parse_args()
        if args.periodic <= 0 or args.max_frames < 1 or not 240 <= args.height <= 2160:
            raise WatchError("periodic/max-frames must be positive; height must be 240..2160")
        bundle = run(args)
        timeline = json.loads((bundle / "timeline.json").read_text(encoding="utf-8"))
        print(f"evidence ready: {bundle}")
        print(f"  {timeline['coverage']['extracted_frames']} frames | "
              f"{len(timeline['transcript']['segments'])} transcript segments | "
              f"schema {timeline['schema']}")
        print("  next: inspect timeline.json, then densify uncertain moments with "
              "--dense-window START-END@FPS")
        return 0
    except (WatchError, ValueError) as exc:
        print(f"beast watch: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
