import json
import unreal

asset_path = "/Game/MoodBuddyProof/Run001/MetaHumans/AdaProof/BP_AdaProof"
blueprint = unreal.load_asset(asset_path)
if blueprint is None:
    raise RuntimeError(f"Missing Blueprint: {asset_path}")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_subsystem.get_all_level_actors()
actor = next((a for a in actors if a.get_actor_label() == "BEAST_AdaProof"), None)
if actor is None:
    actor = actor_subsystem.spawn_actor_from_class(
        blueprint.generated_class(), unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator()
    )
    actor.set_actor_label("BEAST_AdaProof")

result = {
    "asset": asset_path,
    "actor": actor.get_path_name(),
    "class": actor.get_class().get_path_name(),
}
for prop in ("live_link_subject", "use_live_link"):
    try:
        value = actor.get_editor_property(prop)
        result[prop] = {"repr": repr(value), "type": str(type(value))}
    except Exception as exc:
        result[prop] = {"error": str(exc)}

actor_subsystem.set_selected_level_actors([actor])
try:
    level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    level_editor.editor_focus_viewport_on_actors([actor])
    result["focused"] = True
except Exception as exc:
    result["focus_error"] = str(exc)

unreal.log("BEAST_SPAWN_PROBE=" + json.dumps(result, sort_keys=True))
