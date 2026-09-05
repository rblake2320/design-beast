"""Shared media-tool discovery for doctor, Watch and reinspection.

Explicit BEAST_FFMPEG / BEAST_FFPROBE overrides fail closed if invalid.
Otherwise use PATH, then version-independent per-user WinGet installations.
No downloads, global PATH edits, or recursive whole-drive scans.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path


def _version(path: Path) -> tuple[int, ...]:
    match = re.search(r"ffmpeg-(\d+(?:\.\d+)*)", str(path), re.IGNORECASE)
    return tuple(map(int, match.group(1).split("."))) if match else ()


def find_tool(name: str) -> str | None:
    if name not in {"ffmpeg", "ffprobe"}:
        return shutil.which(name)
    configured = os.environ.get(f"BEAST_{name.upper()}")
    if configured is not None:
        return shutil.which(os.path.expanduser(configured)) if configured else None
    found = shutil.which(name)
    if found:
        return found
    if os.name != "nt":
        return None
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    packages = local / "Microsoft/WinGet/Packages"
    candidates = packages.glob(f"Gyan.FFmpeg*/*/bin/{name}.exe")
    for candidate in sorted(candidates, key=lambda p: (_version(p), str(p)), reverse=True):
        if candidate.is_file():
            return str(candidate.resolve())
    return None


def missing_tool_message(name: str) -> str:
    if name not in {"ffmpeg", "ffprobe"}:
        hint = "; install with pip install yt-dlp" if name == "yt-dlp" else ""
        return f"{name} not found on PATH{hint}"
    return (f"{name} not found: check BEAST_{name.upper()}, PATH, or the per-user "
            "WinGet Gyan.FFmpeg installation")
