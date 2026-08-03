"""Discover Live Link fields on the generated MetaHuman actor and components."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import read_receipt, require_context

MARKER = "BEAST_METAHUMAN_LIVELINK_FIELDS="


def main() -> list[dict]:
    context = require_context()
    spawn = read_receipt(context, "spawn", "SPAWNED")
    actor_label = os.environ.get("BEAST_MH_ACTOR_LABEL", f"BEAST_{context['run_id']}")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = next((item for item in actors.get_all_level_actors() if item.get_actor_label() == actor_label), None)
    if actor is None:
        raise RuntimeError(f"Actor is not in the level: {actor_label}")
    if actor.get_path_name() != spawn.get("actor") or actor.get_class().get_path_name() != spawn.get("class"):
        raise RuntimeError("Spawned actor does not match the reviewed assembly receipt chain")
    objects = [("actor", actor)] + [
        (component.get_name(), component)
        for component in actor.get_components_by_class(unreal.ActorComponent)
    ]
    candidates = (
        "LiveLinkSubject",
        "live_link_subject",
        "LiveLinkSubjectName",
        "live_link_subject_name",
        "UseLiveLink",
        "use_live_link",
    )
    report = []
    for label, obj in objects:
        values = {}
        for prop in candidates:
            try:
                value = obj.get_editor_property(prop)
                values[prop] = {"repr": repr(value), "type": str(type(value))}
            except Exception:
                pass
        if values:
            report.append(
                {"label": label, "class": obj.get_class().get_path_name(), "properties": values}
            )
    if not any(
        "LiveLinkSubject" in item["properties"] and "UseLiveLink" in item["properties"]
        for item in report
    ):
        raise RuntimeError("Required UE 5.8 Live Link actor fields were not found")
    unreal.log(MARKER + json.dumps(report, sort_keys=True))
    return report


if __name__ == "__main__":
    main()
