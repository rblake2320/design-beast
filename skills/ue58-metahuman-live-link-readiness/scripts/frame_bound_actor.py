"""Frame the BOUND_READY MetaHuman's head in the active UE 5.8 level viewport."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import read_receipt, require_context

MARKER = "BEAST_BOUND_ACTOR_FRAMED="


def vector_dict(value: unreal.Vector) -> dict[str, float]:
    return {"x": value.x, "y": value.y, "z": value.z}


def main() -> dict:
    context = require_context()
    bound = read_receipt(context, "bound-ready", "BOUND_READY")
    actor = unreal.load_object(None, bound["actor"])
    if actor is None:
        raise RuntimeError("BOUND_READY actor is not loaded in the active proof map")

    origin, extent = actor.get_actor_bounds(False, True)
    if min(extent.x, extent.y, extent.z) <= 0:
        raise RuntimeError(f"BOUND_READY actor has invalid bounds: {extent}")

    distance = float(os.environ.get("BEAST_FRAME_DISTANCE", "180"))
    head_fraction = float(os.environ.get("BEAST_FRAME_HEAD_FRACTION", "0.72"))
    direction_name = os.environ.get("BEAST_FRAME_DIRECTION", "actor-forward").strip().lower()
    if not 50.0 <= distance <= 1000.0 or not 0.25 <= head_fraction <= 1.0:
        raise RuntimeError("Invalid face-framing distance or head fraction")

    target = unreal.Vector(origin.x, origin.y, origin.z + extent.z * head_fraction)
    directions = {
        "actor-forward": actor.get_actor_forward_vector(),
        "+x": unreal.Vector(1.0, 0.0, 0.0),
        "-x": unreal.Vector(-1.0, 0.0, 0.0),
        "+y": unreal.Vector(0.0, 1.0, 0.0),
        "-y": unreal.Vector(0.0, -1.0, 0.0),
    }
    if direction_name not in directions:
        raise RuntimeError(f"Invalid BEAST_FRAME_DIRECTION: {direction_name}")
    camera = target + directions[direction_name] * distance
    rotation = unreal.MathLibrary.find_look_at_rotation(camera, target)
    subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    subsystem.set_level_viewport_camera_info(camera, rotation)

    read_location, read_rotation = subsystem.get_level_viewport_camera_info()
    if (read_location - camera).length() > 0.1:
        raise RuntimeError("UE 5.8 did not retain the requested proof camera location")

    result = {
        "state": "BOUND_ACTOR_FRAMED",
        "project": context["project"],
        "run_id": context["run_id"],
        "actor": actor.get_path_name(),
        "bounds_origin": vector_dict(origin),
        "bounds_extent": vector_dict(extent),
        "camera": vector_dict(read_location),
        "rotation": {
            "pitch": read_rotation.pitch,
            "yaw": read_rotation.yaw,
            "roll": read_rotation.roll,
        },
        "target": vector_dict(target),
        "distance": distance,
        "direction": direction_name,
    }
    unreal.log(MARKER + json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
