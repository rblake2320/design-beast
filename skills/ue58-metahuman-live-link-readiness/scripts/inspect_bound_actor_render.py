"""Report render-relevant state for the loaded BOUND_READY actor and its components."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import read_receipt, require_context


def safe_call(obj, method, default=None):
    try:
        return getattr(obj, method)()
    except Exception:
        return default


def safe_property(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def main() -> list[dict]:
    context = require_context()
    bound = read_receipt(context, "bound-ready", "BOUND_READY")
    actor = unreal.load_object(None, bound["actor"])
    if actor is None:
        raise RuntimeError("BOUND_READY actor is not loaded")

    report = []
    for component in actor.get_components_by_class(unreal.ActorComponent):
        item = {
            "name": component.get_name(),
            "class": component.get_class().get_path_name(),
            "registered": safe_call(component, "is_registered"),
            "active": safe_call(component, "is_active"),
            "visible": safe_call(component, "is_visible"),
            "hidden_in_game": safe_property(component, "hidden_in_game"),
        }
        if isinstance(component, unreal.SkeletalMeshComponent):
            mesh = safe_property(component, "skeletal_mesh_asset")
            item.update(
                {
                    "skeletal_mesh": mesh.get_path_name() if mesh else None,
                    "animation_mode": str(safe_property(component, "animation_mode")),
                    "anim_class": str(safe_property(component, "anim_class")),
                }
            )
        report.append(item)
    unreal.log("BEAST_BOUND_ACTOR_RENDER=" + json.dumps(report, sort_keys=True))
    return report


if __name__ == "__main__":
    main()
