"""Bind an exact Live Link subject and require actor-property readback."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import read_receipt, require_context, write_receipt

MARKER = "BEAST_METAHUMAN_BOUND_READY="


def main() -> dict:
    context = require_context()
    spawn = read_receipt(context, "spawn", "SPAWNED")
    if spawn.get("assembly_state") not in {
        "ASSEMBLED",
        "ADOPTED_LOCAL_ASSEMBLY",
    } or not spawn.get("assembly_log_reviewed_by_user"):
        raise RuntimeError("Reviewed assembled or locally adopted state is required before Live Link binding")
    actor_label = os.environ.get("BEAST_MH_ACTOR_LABEL", f"BEAST_{context['run_id']}")
    subject_name = os.environ.get("BEAST_LIVE_LINK_SUBJECT", "me")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = next((item for item in actors.get_all_level_actors() if item.get_actor_label() == actor_label), None)
    if actor is None:
        raise RuntimeError(f"Actor is not in the level: {actor_label}")
    if actor.get_path_name() != spawn.get("actor") or actor.get_class().get_path_name() != spawn.get("class"):
        raise RuntimeError("Binding actor does not match the reviewed assembly receipt chain")

    subject = actor.get_editor_property("LiveLinkSubject")
    subject.set_editor_property("name", unreal.Name(subject_name))
    actor.set_editor_property("LiveLinkSubject", subject)
    actor.set_editor_property("UseLiveLink", True)

    read_subject = str(
        actor.get_editor_property("LiveLinkSubject").get_editor_property("name")
    )
    read_enabled = bool(actor.get_editor_property("UseLiveLink"))
    live_subject = unreal.LiveLinkSubjectName(name=unreal.Name(subject_name))
    enabled_names = {
        str(item.get_editor_property("name"))
        for item in unreal.LiveLinkBlueprintLibrary.get_live_link_enabled_subject_names(False)
    }
    subject_enabled = bool(
        unreal.LiveLinkBlueprintLibrary.is_live_link_subject_enabled(live_subject)
    )
    subject_state = unreal.LiveLinkBlueprintLibrary.get_live_link_subject_state(live_subject)
    connected = subject_state == unreal.LiveLinkSubjectState.CONNECTED
    result = {
        "state": "BOUND_READY",
        "project": context["project"],
        "run_id": context["run_id"],
        "actor": actor.get_path_name(),
        "subject": read_subject,
        "use_live_link": read_enabled,
        "enabled_subject_names": sorted(enabled_names),
        "subject_enabled": subject_enabled,
        "subject_state": str(subject_state),
        "animation_confirmed": False,
    }
    if (
        read_subject != subject_name
        or not read_enabled
        or subject_name not in enabled_names
        or not subject_enabled
        or not connected
    ):
        result["state"] = "BINDING_CONFIGURED"
        raise RuntimeError("Live Link binding failed readback: " + json.dumps(result))
    unreal.log(MARKER + json.dumps(result, sort_keys=True))
    write_receipt(context, "bound-ready", result)
    return result


if __name__ == "__main__":
    main()
