"""Quit the active disposable proof editor after its dirty packages are saved."""

from __future__ import annotations

import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import require_context


def main() -> None:
    require_context()
    unreal.SystemLibrary.quit_editor()


if __name__ == "__main__":
    main()
