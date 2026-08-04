"""Assemble a UE 5.8 MetaHuman and prove generated assets by discovery."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import read_receipt, require_context, require_under_run, write_receipt

MARKER = "BEAST_METAHUMAN_ASSEMBLY_CANDIDATE="


def main() -> dict:
    context = require_context()
    preflight = read_receipt(context, "preflight", "PREFLIGHT_READY")
    if not preflight.get("can_build"):
        read_receipt(context, "cloud", "ASSEMBLY_ELIGIBLE")
    target = require_under_run(
        os.environ.get("BEAST_MH_TARGET", context["content_root"] + "/Characters/AdaProof"),
        context,
    )
    build_root = require_under_run(
        os.environ.get("BEAST_MH_BUILD_ROOT", context["content_root"] + "/MetaHumans"),
        context,
    )
    character = unreal.load_asset(target)
    if character is None:
        raise RuntimeError(f"Missing MetaHuman Character: {target}")
    subsystem = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
    if not subsystem.can_build_meta_human(character, log_error=True):
        raise RuntimeError("MetaHuman is not build-ready; stop before assembly")

    assets = unreal.EditorAssetLibrary
    before = set(assets.list_assets(build_root, recursive=True, include_folder=False))
    added_here = False
    if not subsystem.is_object_added_for_editing(character):
        if not subsystem.try_add_object_to_edit(character):
            raise RuntimeError(f"Unable to register MetaHuman for editing: {target}")
        added_here = True
    try:
        params = unreal.MetaHumanCharacterEditorBuildParameters()
        params.pipeline_type = unreal.MetaHumanDefaultPipelineType.OPTIMIZED
        params.pipeline_quality = unreal.MetaHumanQualityLevel.MEDIUM
        params.absolute_build_path = build_root
        params.common_folder_path = build_root + "/Common"
        params.enable_wardrobe_item_validation = False
        subsystem.build_meta_human(character=character, params=params)
    finally:
        if added_here and subsystem.is_object_added_for_editing(character):
            subsystem.remove_object_to_edit(character)

    after = set(assets.list_assets(build_root, recursive=True, include_folder=False))
    new_assets = sorted(after - before)
    blueprint_candidates = []
    for path in new_assets:
        asset = unreal.load_asset(path)
        if asset is not None and asset.get_class().get_name() == "Blueprint":
            blueprint_candidates.append(path)
    if not new_assets or len(blueprint_candidates) != 1:
        raise RuntimeError(
            "Assembly evidence failed: "
            + json.dumps({"new_assets": len(new_assets), "blueprints": blueprint_candidates})
        )
    saved = bool(assets.save_directory(build_root, only_if_is_dirty=False, recursive=True))
    if not saved:
        raise RuntimeError(f"Generated assets were not saved: {build_root}")
    result = {
        "state": "ASSEMBLY_CANDIDATE",
        "project": context["project"],
        "run_id": context["run_id"],
        "asset": target,
        "build_root": build_root,
        "new_asset_count": len(new_assets),
        "blueprint": blueprint_candidates[0],
        "saved": saved,
        "clean_log_review_required": True,
    }
    unreal.log(MARKER + json.dumps(result, sort_keys=True))
    write_receipt(context, "assembly-candidate", result)
    return result


if __name__ == "__main__":
    main()
