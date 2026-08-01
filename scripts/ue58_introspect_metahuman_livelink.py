import json
import unreal

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = next(
    (a for a in actor_subsystem.get_all_level_actors() if a.get_actor_label() == "BEAST_AdaProof"),
    None,
)
if actor is None:
    raise RuntimeError("BEAST_AdaProof is not in the level")

objects = [("actor", actor)]
for component in actor.get_components_by_class(unreal.ActorComponent):
    objects.append((component.get_name(), component))

candidate_properties = [
    "LiveLinkSubject",
    "live_link_subject",
    "LiveLinkSubjectName",
    "live_link_subject_name",
    "UseLiveLink",
    "use_live_link",
    "UseARKitFace",
    "use_ar_kit_face",
]
report = []
for label, obj in objects:
    matching_attrs = [name for name in dir(obj) if "live" in name.lower() or "arkit" in name.lower()]
    values = {}
    for prop in candidate_properties:
        try:
            value = obj.get_editor_property(prop)
            values[prop] = {"repr": repr(value), "type": str(type(value))}
        except Exception:
            pass
    if matching_attrs or values:
        report.append(
            {
                "label": label,
                "class": obj.get_class().get_path_name(),
                "attrs": matching_attrs,
                "properties": values,
            }
        )

unreal.log("BEAST_LIVELINK_INTROSPECTION=" + json.dumps(report, sort_keys=True))
