import json
import unreal

subject_name = "me"
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = next(
    (a for a in actor_subsystem.get_all_level_actors() if a.get_actor_label() == "BEAST_AdaProof"),
    None,
)
if actor is None:
    raise RuntimeError("BEAST_AdaProof is not in the level")

subject = actor.get_editor_property("LiveLinkSubject")
subject.set_editor_property("name", unreal.Name(subject_name))
actor.set_editor_property("LiveLinkSubject", subject)
actor.set_editor_property("UseLiveLink", True)

# UE 5.8's Python Actor wrapper does not expose RerunConstructionScripts.
# The generated MetaHuman properties update immediately, so validate their
# reflected values directly instead of treating that unavailable helper as a
# binding failure.

read_subject = actor.get_editor_property("LiveLinkSubject")
read_enabled = actor.get_editor_property("UseLiveLink")
result = {
    "actor": actor.get_path_name(),
    "subject": str(read_subject.get_editor_property("name")),
    "use_live_link": bool(read_enabled),
}
if result["subject"] != subject_name or not result["use_live_link"]:
    raise RuntimeError("Live Link binding failed read-back validation: " + json.dumps(result))

unreal.log("BEAST_LIVELINK_BOUND=" + json.dumps(result, sort_keys=True))
