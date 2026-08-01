"""Spawn or reuse the assembled UE 5.8 MetaHuman proof actor."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import read_receipt, require_context, require_under_run, write_receipt

MARKER = "BEAST_METAHUMAN_SPAWNED="


def main() -> dict:
    context = require_context()
    if os.environ.get("BEAST_USER_REVIEWED_ASSEMBLY_LOG") != "1":
        raise RuntimeError("User must review the clean assembly log before spawning")
    assembly = read_receipt(context, "assembly-candidate", "ASSEMBLY_CANDIDATE")
    asset_path = os.environ.get("BEAST_MH_BLUEPRINT", "").strip()
    if not asset_path:
        raise RuntimeError("BEAST_MH_BLUEPRINT must use the path discovered by assemble.py")
    require_under_run(asset_path, context)
    if asset_path != assembly.get("blueprint"):
        raise RuntimeError("BEAST_MH_BLUEPRINT does not match the discovered assembly receipt")
    actor_label = os.environ.get("BEAST_MH_ACTOR_LABEL", f"BEAST_{context['run_id']}")
    blueprint = unreal.load_asset(asset_path)
    if blueprint is None:
        raise RuntimeError(f"Missing generated Blueprint: {asset_path}")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = next((item for item in actors.get_all_level_actors() if item.get_actor_label() == actor_label), None)
    expected_class = blueprint.generated_class()
    if actor is not None and actor.get_class() != expected_class:
        raise RuntimeError(f"Actor-label collision with wrong class: {actor_label}")
    if actor is None:
        actor = actors.spawn_actor_from_class(
            expected_class, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator()
        )
        if actor is None:
            raise RuntimeError(f"Failed to spawn generated Blueprint: {asset_path}")
        actor.set_actor_label(actor_label)
    actors.set_selected_level_actors([actor])
    saved = bool(unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True))
    if not saved:
        raise RuntimeError("Spawned actor exists but the proof map could not be saved")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    result = {
        "state": "SPAWNED",
        "project": context["project"],
        "run_id": context["run_id"],
        "asset": asset_path,
        "actor": actor.get_path_name(),
        "actor_label": actor_label,
        "class": actor.get_class().get_path_name(),
        "world": world.get_path_name(),
        "saved": saved,
        "assembly_state": (
            "ADOPTED_LOCAL_ASSEMBLY"
            if assembly.get("assembly_mode") == "ADOPTED_LOCAL_UE58_BLUEPRINT"
            else "ASSEMBLED"
        ),
        "assembly_mode": assembly.get("assembly_mode", "BUILT_IN_FRESH_RUN"),
        "assembly_log_reviewed_by_user": True,
    }
    unreal.log(MARKER + json.dumps(result, sort_keys=True))
    write_receipt(context, "spawn", result)
    return result


if __name__ == "__main__":
    main()
