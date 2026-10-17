"""Version-agnostic tool locations, so a tool upgrade never breaks a lookup.

winget installs FFmpeg into a versioned folder (ffmpeg-8.1.2-full_build,
ffmpeg-9.0-full_build, ...) and deletes the old one on upgrade. Hardcoding the
version broke doctor and the audio bench the day FFmpeg moved to 9.0.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

WINGET_PACKAGES = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
# Windows refuses to apply a per-variable environment block past 32,767 chars;
# an oversized User PATH is silently dropped, hiding every user-installed tool.
PATH_LIMIT = 32767
PATH_WARN_AT = 24000


def _version_key(folder: Path) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", folder.name))


def winget_ffmpeg_bin(packages: Path = WINGET_PACKAGES) -> Path | None:
    """Newest winget FFmpeg bin dir, whatever its version, or None."""
    builds = [p for p in packages.glob("Gyan.FFmpeg*/ffmpeg-*") if (p / "bin").is_dir()]
    if not builds:
        return None
    return max(builds, key=_version_key) / "bin"


def find_tool(name: str, packages: Path = WINGET_PACKAGES) -> str | None:
    """PATH first, then the newest winget FFmpeg build (ffmpeg/ffprobe/ffplay)."""
    found = shutil.which(name)
    if found:
        return found
    bin_dir = winget_ffmpeg_bin(packages)
    if bin_dir and (bin_dir / f"{name}.exe").exists():
        return str(bin_dir / f"{name}.exe")
    return None


def user_path_length() -> int | None:
    """Length of the registry User PATH (Windows only), or None elsewhere."""
    if os.name != "nt":
        return None
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
        try:
            value, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            return 0
    return len(value)
