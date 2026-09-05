from pathlib import Path

import pytest

from scripts import tool_paths


def test_path_wins_over_winget(monkeypatch):
    monkeypatch.delenv("BEAST_FFMPEG", raising=False)
    monkeypatch.setattr(tool_paths.shutil, "which", lambda name: "/tools/ffmpeg")
    assert tool_paths.find_tool("ffmpeg") == "/tools/ffmpeg"


def test_invalid_explicit_override_does_not_silently_fallback(monkeypatch):
    monkeypatch.setenv("BEAST_FFMPEG", "/missing/ffmpeg")
    monkeypatch.setattr(tool_paths.shutil, "which",
                        lambda name: "/on/path/ffmpeg" if name == "ffmpeg" else None)
    assert tool_paths.find_tool("ffmpeg") is None


@pytest.mark.skipif(tool_paths.os.name != "nt", reason="WinGet is Windows-only")
@pytest.mark.parametrize("name", ["ffmpeg", "ffprobe"])
def test_winget_upgrade_and_numeric_version_order(tmp_path, monkeypatch, name):
    monkeypatch.delenv(f"BEAST_{name.upper()}", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(tool_paths.shutil, "which", lambda _: None)
    package = tmp_path / "Microsoft/WinGet/Packages/Gyan.FFmpeg_test"
    for version in ("8.1.2", "9.0", "10.0"):
        exe = package / f"ffmpeg-{version}-full_build/bin/{name}.exe"
        exe.parent.mkdir(parents=True)
        exe.touch()
    assert tool_paths.find_tool(name) == str(
        (package / f"ffmpeg-10.0-full_build/bin/{name}.exe").resolve())


def test_missing_tools_are_reported(monkeypatch):
    monkeypatch.setenv("BEAST_FFMPEG", "")
    from scripts.watch_video import _tool
    from watch.core import WatchError
    with pytest.raises(WatchError, match="BEAST_FFMPEG"):
        _tool("ffmpeg")
    assert _tool("ffmpeg", required=False) is None


def test_missing_downloader_hint_is_actionable():
    hint = tool_paths.missing_tool_message("yt-dlp")
    assert "pip install yt-dlp" in hint
    assert "BEAST_" not in hint and "FFmpeg" not in hint
