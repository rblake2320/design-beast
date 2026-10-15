"""Offscreen UE 5.8 visual check in the dedicated asset workspace."""
import json
import os
import traceback
import uuid
from pathlib import Path

import unreal

folder = Path(os.environ["BEAST_VIEWPORT_FOLDER"])
receipt = json.loads((folder / "unreal-receipt.json").read_text())
state = {}


def capture_control():
    try:
        if not unreal.SystemLibrary.get_engine_version().startswith("5.8."):
            raise RuntimeError("Viewport requires UE 5.8")
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        level = receipt["destination"] + "/VisualCheck_" + uuid.uuid4().hex[:8]
        if not levels.new_level(level):
            raise RuntimeError("Could not create the dedicated visual-check map")
        meshes = []
        for item in receipt["meshes"]:
            mesh = unreal.load_asset(item["asset"])
            actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector())
            actor.static_mesh_component.set_static_mesh(mesh)
            actor.set_actor_label("Beast verified asset")
            meshes.append(mesh)
        box = meshes[0].get_bounds()
        center = box.origin
        size = max(box.box_extent.x, box.box_extent.y, box.box_extent.z) * 2
        camera = actors.spawn_actor_from_class(unreal.CameraActor,
            center + unreal.Vector(1.8 * size, -2.8 * size, 1.5 * size))
        camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(camera.get_actor_location(), center), False)
        camera.camera_component.set_editor_property("field_of_view", 45.0)
        sun = actors.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector())
        sun.set_actor_rotation(unreal.Rotator(-45, -30, 0), False)
        sun.light_component.set_editor_property("intensity", 5.0)
        sun.light_component.set_editor_property("atmosphere_sun_light", True)
        actors.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector())
        sky = actors.spawn_actor_from_class(unreal.SkyLight, unreal.Vector())
        sky.light_component.set_editor_property("real_time_capture", True)
        levels.save_current_level()
        for _ in range(120):
            yield
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).pilot_level_actor(camera)
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        for command in ("ShowFlag.Grid 0", "ShowFlag.CompositeEditorPrimitives 0", "ShowFlag.SelectionOutline 0"):
            unreal.SystemLibrary.execute_console_command(world, command)
        unreal.SystemLibrary.execute_console_command(world,
            'HighResShot 1280x720 filename="' + str(folder / "unreal-viewport.png") + '"')
        for _ in range(120):
            if (folder / "unreal-viewport.png").is_file():
                break
            yield
        if not (folder / "unreal-viewport.png").is_file():
            raise RuntimeError("Viewport screenshot did not land")
        state.update(outcome="Worked", engine_version=unreal.SystemLibrary.get_engine_version(),
                     level=level, assets=[item["asset"] for item in receipt["meshes"]],
                     screenshot="unreal-viewport.png")
    except Exception:
        state.update(outcome="Failed", error=traceback.format_exc())
    finally:
        (folder / "viewport-receipt.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        unreal.SystemLibrary.quit_editor()
    yield


runner = capture_control()
handle = None
def tick(delta):
    try:
        next(runner)
    except StopIteration:
        if handle is not None:
            unreal.unregister_slate_post_tick_callback(handle)
handle = unreal.register_slate_post_tick_callback(tick)
