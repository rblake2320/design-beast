"""Load the explicitly selected disposable proof map before spawning evidence actors."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import require_context

MARKER = "BEAST_PROOF_MAP_LOADED="


def main() -> dict:
    context = require_context()
    map_path = os.environ.get("BEAST_PROOF_MAP", "/Game/MetaHumanLiveLinkProof").strip()
    if not map_path.startswith("/Game/") or ".." in map_path:
        raise RuntimeError(f"Proof map must be an explicit /Game path: {map_path}")
    if not unreal.EditorAssetLibrary.does_asset_exist(map_path):
        raise RuntimeError(f"Proof map does not exist: {map_path}")
    world = unreal.EditorLoadingAndSavingUtils.load_map(map_path)
    if world is None:
        raise RuntimeError(f"Failed to load proof map: {map_path}")
    result = {
        "state": "PROOF_MAP_LOADED",
        "project": context["project"],
        "run_id": context["run_id"],
        "map": map_path,
        "world": world.get_path_name(),
    }
    unreal.log(MARKER + json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
