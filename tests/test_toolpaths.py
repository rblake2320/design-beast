import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("toolpaths", ROOT / "scripts" / "toolpaths.py")
toolpaths = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(toolpaths)


def _build(packages: Path, version: str) -> Path:
    bin_dir = packages / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe" / f"ffmpeg-{version}-full_build" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "ffmpeg.exe").write_bytes(b"")
    return bin_dir


def test_newest_build_wins_numerically(tmp_path):
    _build(tmp_path, "8.1.2")
    _build(tmp_path, "9.0")
    newest = _build(tmp_path, "10.0")  # lexically "10.0" < "9.0"; must still win
    assert toolpaths.winget_ffmpeg_bin(tmp_path) == newest


def test_survives_upgrade_that_removes_old_build(tmp_path, monkeypatch):
    monkeypatch.setattr(toolpaths.shutil, "which", lambda name: None)
    current = _build(tmp_path, "9.0")  # 8.1.2 never existed / was deleted by winget
    assert toolpaths.find_tool("ffmpeg", tmp_path) == str(current / "ffmpeg.exe")


def test_path_beats_winget_and_missing_is_none(tmp_path, monkeypatch):
    _build(tmp_path, "9.0")
    monkeypatch.setattr(toolpaths.shutil, "which", lambda name: "C:/on/path/ffmpeg.exe")
    assert toolpaths.find_tool("ffmpeg", tmp_path) == "C:/on/path/ffmpeg.exe"
    monkeypatch.setattr(toolpaths.shutil, "which", lambda name: None)
    assert toolpaths.find_tool("ffmpeg", tmp_path / "empty") is None


def test_user_path_length_is_int_on_windows():
    length = toolpaths.user_path_length()
    assert (length is None) if os.name != "nt" else isinstance(length, int)
