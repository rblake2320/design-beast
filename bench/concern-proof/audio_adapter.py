"""Render and measure the audio benchmark from an agent answer."""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path


def ffmpeg_exe() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    hinted = (Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
              / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
              / "ffmpeg-8.1.2-full_build/bin/ffmpeg.exe")
    if hinted.exists():
        return str(hinted)
    raise FileNotFoundError("ffmpeg")


def number(value):
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value))
    if not match:
        raise ValueError(value)
    return float(match.group())


def load(path: Path) -> dict[str, float]:
    answer = json.loads(path.read_text(encoding="utf-8"))
    if answer["status"] != "answered":
        raise ValueError("answer is incomplete; no audio artifact may be built")
    values = {item["name"]: number(item["value"]) for item in answer["values"]}
    required = {
        "compressor_threshold_db", "compressor_makeup_db", "compressor_knee_db",
        "compressor_ratio", "compressor_lookahead_ms", "compressor_attack_ms",
        "compressor_release_ms", "limiter_threshold_db", "limiter_makeup_target_db",
        "limiter_knee_db", "limiter_lookahead_ms", "limiter_release_ms",
    }
    missing = sorted(required - values.keys())
    if missing:
        raise ValueError(f"missing values: {missing}")
    return values


def main(answer_path: Path, output: Path, receipt: Path) -> None:
    values = load(answer_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    limit = 10 ** (values["limiter_threshold_db"] / 20)
    compressor = (
        f"acompressor=threshold={values['compressor_threshold_db']}dB:"
        f"ratio={values['compressor_ratio']}:attack={values['compressor_attack_ms']}:"
        f"release={values['compressor_release_ms']}:makeup={values['compressor_makeup_db']}dB:"
        f"knee={values['compressor_knee_db']}dB"
    )
    limiter = (
        f"alimiter=limit={limit}:attack={values['limiter_lookahead_ms']}:"
        f"release={values['limiter_release_ms']}:level=false"
    )
    subprocess.run([
        ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=2",
        "-filter:a", f"volume=12dB,{compressor},{limiter}",
        "-c:a", "pcm_s24le", str(output),
    ], check=True)
    measured = subprocess.run([
        ffmpeg_exe(), "-hide_banner", "-i", str(output), "-af", "volumedetect",
        "-f", "null", "-",
    ], text=True, capture_output=True, check=True)
    peak_match = re.search(r"max_volume:\s*([-\d.]+) dB", measured.stderr)
    report = {
        "artifact": str(output),
        "opens": output.stat().st_size > 44,
        "bytes": output.stat().st_size,
        "measured_peak_db": float(peak_match.group(1)) if peak_match else None,
        "parameters": values,
        "limiter_linear_limit": limit,
    }
    receipt.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
