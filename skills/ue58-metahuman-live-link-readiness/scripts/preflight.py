"""Run UE 5.8 MetaHuman readiness checks without cloud work."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import receipt_path, require_context, require_under_run, write_receipt

MARKER = "BEAST_METAHUMAN_PREFLIGHT="
DEFAULT_PRESET = "/MetaHumanCharacter/Optional/Presets/Ada"


def main() -> dict:
    context = require_context()
    assets = unreal.EditorAssetLibrary
    preset = os.environ.get("BEAST_MH_PRESET", DEFAULT_PRESET)
    target = require_under_run(
        os.environ.get("BEAST_MH_TARGET", context["content_root"] + "/Characters/AdaProof"),
        context,
    )
    if os.path.exists(receipt_path(context, "preflight")) or assets.does_directory_exist(
        context["content_root"]
    ):
        raise RuntimeError("BEAST_RUN_ID is not fresh; choose a new run identifier")
    if not assets.does_asset_exist(preset):
        raise RuntimeError(f"MetaHuman preset is missing: {preset}")
    created = False
    if not assets.does_asset_exist(target):
        if assets.duplicate_asset(preset, target) is None:
            raise RuntimeError(f"Failed to duplicate {preset} to {target}")
        created = True
    character = unreal.load_asset(target)
    if character is None or character.get_class().get_name() != "MetaHumanCharacter":
        raise RuntimeError(f"Invalid project MetaHuman: {target}")
    assets.save_asset(target, only_if_is_dirty=False)
    subsystem = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
    result = {
        "schema": 1,
        "state": "PREFLIGHT_READY",
        "engine_version": context["version"],
        "project": context["project"],
        "run_id": context["run_id"],
        "asset": target,
        "created": created,
        "can_build": bool(subsystem.can_build_meta_human(character, log_error=True)),
        "high_resolution_textures": bool(character.has_high_resolution_textures),
        "external_work_performed": False,
    }
    unreal.log(MARKER + json.dumps(result, sort_keys=True))
    write_receipt(context, "preflight", result)
    return result


if __name__ == "__main__":
    main()
