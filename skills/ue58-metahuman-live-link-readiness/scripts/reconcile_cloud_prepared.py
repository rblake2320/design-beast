"""Adopt user-completed UE 5.8 cloud preparation without repeating cloud work."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import read_receipt, require_context, require_under_run, write_receipt

MARKER = "BEAST_METAHUMAN_CLOUD_RECONCILED="


def main() -> dict:
    context = require_context()
    if os.environ.get("BEAST_USER_AUTHORIZED_METAHUMAN_CLOUD") != "1":
        raise RuntimeError("User authorization must be recorded before adopting cloud output")
    read_receipt(context, "preflight", "PREFLIGHT_READY")
    target = require_under_run(
        os.environ.get("BEAST_MH_TARGET", context["content_root"] + "/Characters/AdaProof"),
        context,
    )
    character = unreal.load_asset(target)
    if character is None:
        raise RuntimeError(f"Missing MetaHuman Character: {target}")

    skin_settings = character.get_editor_property("skin_settings")
    resolutions = skin_settings.get_editor_property("desired_texture_sources_resolutions")
    fields = (
        "face_albedo",
        "face_normal",
        "face_cavity",
        "face_animated_maps",
        "body_albedo",
        "body_normal",
        "body_cavity",
        "body_masks",
    )
    resolution_readback = {
        field: str(resolutions.get_editor_property(field)) for field in fields
    }
    all_configured_2k = all(
        resolutions.get_editor_property(field) == unreal.RequestTextureResolution.RES2K
        for field in fields
    )
    assembly = None
    try:
        assembly = read_receipt(context, "assembly-candidate", "ASSEMBLY_CANDIDATE")
    except RuntimeError:
        pass
    assembled_blueprint = assembly.get("blueprint") if assembly else None
    assembled_output_exists = bool(
        assembled_blueprint and unreal.EditorAssetLibrary.does_asset_exist(assembled_blueprint)
    )
    # UE unloads editable Character data after a successful assembly. In that
    # post-assembly state can_build_meta_human() emits a misleading error, so
    # verify the generated output instead of repeating a pre-build readiness test.
    if assembled_output_exists:
        can_build = None
    else:
        subsystem = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
        can_build = bool(subsystem.can_build_meta_human(character, log_error=True))
    result = {
        "state": "CLOUD_OUTPUT_RECONCILED" if assembled_output_exists else "ASSEMBLY_ELIGIBLE",
        "project": context["project"],
        "run_id": context["run_id"],
        "asset": target,
        "preparation_source": "USER_COMPLETED_UI_RECONCILED_BY_READBACK",
        "requested_rig_type": "USER_COMPLETED_UI",
        "blendshape_rig_verified": False,
        "texture_source_resolution_configured": "2K_ALL_EIGHT",
        "texture_source_resolution_readback": resolution_readback,
        "all_eight_configured_2k": all_configured_2k,
        "high_resolution_textures": bool(character.has_high_resolution_textures),
        "can_build": can_build,
        "assembled_blueprint": assembled_blueprint,
        "assembled_output_exists": assembled_output_exists,
        "cloud_work_performed": False,
        "cloud_output_already_present": True,
    }
    preassembly_ready = bool(result["high_resolution_textures"] and result["can_build"])
    if not all_configured_2k or not (preassembly_ready or assembled_output_exists):
        raise RuntimeError("Existing cloud preparation failed readback: " + json.dumps(result))
    unreal.log(MARKER + json.dumps(result, sort_keys=True))
    write_receipt(context, "cloud", result)
    return result


if __name__ == "__main__":
    main()
