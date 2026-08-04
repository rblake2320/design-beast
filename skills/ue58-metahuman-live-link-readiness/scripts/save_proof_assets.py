"""Save dirty content in the active disposable proof project before an editor restart."""

from __future__ import annotations

import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import require_context


def main() -> None:
    require_context()
    if not unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True):
        raise RuntimeError("UE 5.8 did not confirm saving all dirty proof packages")


if __name__ == "__main__":
    main()
