"""beast watch — turn any video into a Claude-readable bundle (frames + transcript).

The pipeline: yt-dlp downloads the video (or takes a local file) and grabs
captions when they exist (free — no transcription cost); ffmpeg samples
frames evenly across the duration (capped, so an hour costs about the same
as 20 minutes); everything lands in one bundle folder with a MANIFEST that
tells the reading agent how to correlate frame timestamps with transcript
lines. No video model involved — an agent that reads images + text IS the
video model.

Usage:
  python scripts/watch_video.py <url-or-file> [--start 45:00] [--end 55:00]
      [--max-frames 40] [--height 720] [--out DIR]

Output bundle:
  <out>/video.mp4  frames/f_MMSS.jpg ...  transcript.txt  MANIFEST.md
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

FFMPEG_HINT = (Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
               / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
               / "ffmpeg-8.1.2-full_build/bin")


def _tool(name: str) -> str:
    if shutil.which(name):
        return name
    hinted = FFMPEG_HINT / f"{name}.exe"
    if hinted.exists():
        return str(hinted)
    sys.exit(f"{name} not found on PATH (checked {hinted})")


def _seconds(ts: str | None) -> float | None:
    if not ts:
        return None
    parts = [float(p) for p in ts.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def _clean_vtt(vtt: Path, out_txt: Path) -> int:
    """VTT -> timestamped transcript lines (MM:SS  text), deduplicated."""
    stamp = None
    lines: list[str] = []
    seen: set[str] = set()
    for raw in vtt.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"(\d+):(\d+):(\d+)\.\d+\s+-->", raw)
        if m:
            h, mnt, s = int(m[1]), int(m[2]), int(m[3])
            stamp = f"{h * 60 + mnt:02d}:{s:02d}"
            continue
        text = re.sub(r"<[^>]+>", "", raw).strip()
        if not text or text.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if text in seen:
            continue
        seen.add(text)
        lines.append(f"[{stamp}] {text}" if stamp else text)
    out_txt.write_text("\n".join(lines), encoding="utf-8")
    return len(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", help="URL (yt-dlp-supported site) or local video file")
    ap.add_argument("--start", help="HH:MM:SS or MM:SS — process from here")
    ap.add_argument("--end", help="HH:MM:SS or MM:SS — stop here")
    ap.add_argument("--max-frames", type=int, default=40)
    ap.add_argument("--height", type=int, default=720, help="download/scale height")
    ap.add_argument("--out", help="bundle dir (default: watched/<slug>)")
    args = ap.parse_args()

    ffmpeg, ffprobe = _tool("ffmpeg"), _tool("ffprobe")
    is_url = re.match(r"^https?://", args.source)

    if args.out:
        bundle = Path(args.out)
    else:
        slug = (re.sub(r"[^A-Za-z0-9]+", "-", args.source.split("=")[-1])[:40]
                if is_url else Path(args.source).stem)
        bundle = Path(__file__).resolve().parent.parent / "watched" / slug
    frames_dir = bundle / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    video = bundle / "video.mp4"

    if is_url:
        ytdlp = _tool("yt-dlp")
        cmd = [ytdlp, "--no-playlist",
               "-f", f"bv*[height<={args.height}]+ba/b[height<={args.height}]/b",
               "--merge-output-format", "mp4",
               "--write-auto-subs", "--write-subs", "--sub-lang", "en.*",
               "--sub-format", "vtt", "-o", str(bundle / "video.%(ext)s")]
        if args.start or args.end:
            cmd += ["--download-sections",
                    f"*{args.start or '0:00'}-{args.end or 'inf'}"]
        subprocess.run(cmd + [args.source], check=True)
    else:
        src = Path(args.source)
        if not src.exists():
            sys.exit(f"not found: {src}")
        shutil.copy2(src, video)

    if not video.exists():
        found = next(bundle.glob("video.*"), None)
        if found is None:
            sys.exit("download produced no video file")
        video = found

    probe = json.loads(subprocess.run(
        [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format",
         str(video)], capture_output=True, text=True).stdout)
    duration = float(probe["format"]["duration"])

    n = min(args.max_frames, max(6, int(duration // 10)))
    interval = duration / n
    for i in range(n):
        t = i * interval + interval / 2
        stamp = f"{int(t // 60):02d}{int(t % 60):02d}"
        subprocess.run(
            [ffmpeg, "-v", "quiet", "-ss", f"{t:.2f}", "-i", str(video),
             "-frames:v", "1", "-vf", f"scale=-2:{args.height}", "-q:v", "4",
             str(frames_dir / f"f_{stamp}.jpg"), "-y"], check=False)

    vtt = next(bundle.glob("*.vtt"), None)
    transcript = bundle / "transcript.txt"
    if vtt:
        count = _clean_vtt(vtt, transcript)
        transcript_note = f"{count} caption lines (free — no transcription cost)"
    else:
        transcript_note = ("NO captions found — run Whisper on video.mp4 "
                           "(faster-whisper) and save as transcript.txt")
        transcript.write_text(transcript_note, encoding="utf-8")

    frames = sorted(frames_dir.glob("f_*.jpg"))
    (bundle / "MANIFEST.md").write_text(
        f"# Watch bundle\n\n"
        f"- source: {args.source}\n- duration: {duration:.0f}s\n"
        f"- frames: {len(frames)} at ~{interval:.0f}s intervals — filename "
        f"f_MMSS.jpg is the timestamp\n- transcript: {transcript_note}\n\n"
        f"## How to read this bundle (agent instructions)\n"
        f"1. Read transcript.txt — lines carry [MM:SS] stamps.\n"
        f"2. Read frames/ selectively: match f_MMSS.jpg to the transcript "
        f"moments that reference visuals ('this graph', 'as you can see').\n"
        f"3. Correlate both before answering; cite timestamps in answers.\n",
        encoding="utf-8")
    print(f"bundle ready: {bundle}\n  frames: {len(frames)}  "
          f"duration: {duration:.0f}s  transcript: {transcript_note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
