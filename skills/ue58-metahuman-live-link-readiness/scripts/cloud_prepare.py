"""Explicitly gated UE 5.8 Full Rig and texture-source preparation."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import read_receipt, require_context, require_under_run, write_receipt

MARKER = "BEAST_METAHUMAN_CLOUD_PREPARED="


def _require_opt_in() -> None:
    flags = ("BEAST_ALLOW_METAHUMAN_CLOUD", "BEAST_USER_AUTHORIZED_METAHUMAN_CLOUD")
    missing = [name for name in flags if os.environ.get(name) != "1"]
    if missing:
        raise RuntimeError("Cloud work requires explicit opt-in flags: " + ", ".join(missing))


def main() -> dict:
    context = require_context()
    _require_opt_in()
    read_receipt(context, "preflight", "PREFLIGHT_READY")
    target = require_under_run(
        os.environ.get("BEAST_MH_TARGET", context["content_root"] + "/Characters/AdaProof"),
        context,
    )
    character = unreal.load_asset(target)
    if character is None:
        raise RuntimeError(f"Missing MetaHuman Character: {target}")
    subsystem = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
    added_here = False
    if not subsystem.is_object_added_for_editing(character):
        if not subsystem.try_add_object_to_edit(character):
            raise RuntimeError(f"Unable to register MetaHuman for editing: {target}")
        added_here = True
    try:
        rig_name = "JOINTS_AND_BLEND_SHAPES"
        rig_type = getattr(unreal.MetaHumanRigType, rig_name, None)
        if rig_type is None:
            rig_name = "JOINTS_AND_BLENDSHAPES"
            rig_type = getattr(unreal.MetaHumanRigType, rig_name)
        rig_request = unreal.MetaHumanCharacterAutoRiggingRequestParams()
        rig_request.blocking = True
        rig_request.report_progress = False
        rig_request.rig_type = rig_type
        subsystem.request_auto_rigging(character, rig_request)

        skin_settings = character.get_editor_property("skin_settings")
        resolutions = skin_settings.get_editor_property("desired_texture_sources_resolutions")
        for field in (
            "face_albedo",
            "face_normal",
            "face_cavity",
            "face_animated_maps",
            "body_albedo",
            "body_normal",
            "body_cavity",
            "body_masks",
        ):
            resolutions.set_editor_property(field, unreal.RequestTextureResolution.RES2K)
        skin_settings.set_editor_property("desired_texture_sources_resolutions", resolutions)
        subsystem.commit_skin_settings(character, skin_settings)
        texture_request = unreal.MetaHumanCharacterTextureRequestParams()
        texture_request.blocking = True
        texture_request.report_progress = False
        subsystem.request_texture_sources(character, texture_request)
    finally:
        if added_here and subsystem.is_object_added_for_editing(character):
            subsystem.remove_object_to_edit(character)

    unreal.EditorAssetLibrary.save_asset(target, only_if_is_dirty=False)
    committed_skin = character.get_editor_property("skin_settings")
    committed_resolutions = committed_skin.get_editor_property(
        "desired_texture_sources_resolutions"
    )
    resolution_readback = {
        field: str(committed_resolutions.get_editor_property(field))
        for field in (
            "face_albedo",
            "face_normal",
            "face_cavity",
            "face_animated_maps",
            "body_albedo",
            "body_normal",
            "body_cavity",
            "body_masks",
        )
    }
    all_configured_2k = all(
        committed_resolutions.get_editor_property(field)
        == unreal.RequestTextureResolution.RES2K
        for field in resolution_readback
    )
    result = {
        "state": "ASSEMBLY_ELIGIBLE",
        "project": context["project"],
        "run_id": context["run_id"],
        "asset": target,
        "requested_rig_type": rig_name,
        "blendshape_rig_verified": False,
        "texture_source_resolution_configured": "2K_ALL_EIGHT",
        "texture_source_resolution_readback": resolution_readback,
        "all_eight_configured_2k": all_configured_2k,
        "high_resolution_textures": bool(character.has_high_resolution_textures),
        "can_build": bool(subsystem.can_build_meta_human(character, log_error=True)),
        "cloud_work_performed": True,
    }
    if not all_configured_2k or not result["high_resolution_textures"] or not result["can_build"]:
        raise RuntimeError("Cloud preparation failed readback: " + json.dumps(result))
    unreal.log(MARKER + json.dumps(result, sort_keys=True))
    write_receipt(context, "cloud", result)
    return result


if __name__ == "__main__":
    main()
