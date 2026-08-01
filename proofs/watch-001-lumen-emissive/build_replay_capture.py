"""Build, replay, validate, and capture tutorial proof 001 in real UE 5.8."""
import json
import time
import traceback
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence"
EVIDENCE.mkdir(exist_ok=True)
LOG = []
STATE = {}


def record(event, **details):
    row = {"time_unix": time.time(), "event": event, **details}
    LOG.append(row)
    unreal.log(f"BEAST_PROOF {event}: {details}")


def set_prop(obj, name, value):
    obj.set_editor_property(name, value)
    actual = obj.get_editor_property(name)
    object_type = (obj.get_class().get_name() if hasattr(obj, "get_class")
                   else type(obj).__name__)
    record("set_property", object=object_type, property=name,
           requested=str(value), actual=str(actual))
    return actual


def spawn_mesh(label, mesh_path, location, scale, material=None):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.StaticMeshActor, unreal.Vector(*location))
    actor.set_actor_label(label)
    actor.set_actor_scale3d(unreal.Vector(*scale))
    component = actor.static_mesh_component
    component.set_static_mesh(unreal.load_asset(mesh_path))
    if material:
        component.set_material(0, material)
    record("spawn_actor", label=label, cls="StaticMeshActor", location=location,
           scale=scale, mesh=mesh_path)
    return actor


def create_emissive_material():
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    path = "/Game/Proof/M_TutorialEmissive"
    old = unreal.load_asset(path)
    if old:
        unreal.EditorAssetLibrary.delete_asset(path)
    material = tools.create_asset("M_TutorialEmissive", "/Game/Proof",
                                  unreal.Material, unreal.MaterialFactoryNew())
    set_prop(material, "shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, -420, -80)
    set_prop(color, "parameter_name", "Color")
    set_prop(color, "default_value", unreal.LinearColor(1.0, 0.055, 0.01, 1.0))
    intensity = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, -420, 100)
    set_prop(intensity, "parameter_name", "Intensity")
    set_prop(intensity, "default_value", 25.0)
    multiply = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -150, 0)
    unreal.MaterialEditingLibrary.connect_material_expressions(color, "", multiply, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(intensity, "", multiply, "B")
    unreal.MaterialEditingLibrary.connect_material_property(
        multiply, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    record("create_material", asset=path, shading_model="MSM_UNLIT",
           graph="VectorParameter(Color) * ScalarParameter(Intensity) -> Emissive Color")
    return material


def build_scene():
    level = "/Game/Proof/L_WatchTutorialProof"
    unreal.EditorLevelLibrary.new_level(level)
    material = create_emissive_material()
    # A simple enclosed test space makes emissive bounce and exposure differences visible.
    spawn_mesh("Floor", "/Engine/BasicShapes/Cube.Cube", (0, 0, -25), (10, 10, 0.5))
    spawn_mesh("BackWall", "/Engine/BasicShapes/Cube.Cube", (450, 0, 250), (0.5, 10, 5))
    spawn_mesh("LeftWall", "/Engine/BasicShapes/Cube.Cube", (0, -475, 250), (10, 0.5, 5))
    spawn_mesh("RightWall", "/Engine/BasicShapes/Cube.Cube", (0, 475, 250), (10, 0.5, 5))
    spawn_mesh("EmissiveSphere", "/Engine/BasicShapes/Sphere.Sphere",
               (250, 0, 175), (1.4, 1.4, 1.4), material)
    post = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.PostProcessVolume, unreal.Vector(0, 0, 0))
    post.set_actor_label("TutorialPostProcess")
    set_prop(post, "unbound", True)
    settings = post.get_editor_property("settings")
    # Baseline: required methods are explicit, but the two learned overrides are absent.
    set_prop(settings, "override_dynamic_global_illumination_method", True)
    set_prop(settings, "dynamic_global_illumination_method",
             unreal.DynamicGlobalIlluminationMethod.LUMEN)
    set_prop(settings, "override_auto_exposure_method", True)
    set_prop(settings, "auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
    set_prop(settings, "override_auto_exposure_bias", True)
    set_prop(settings, "auto_exposure_bias", 1.0)
    set_prop(settings, "override_lumen_scene_detail", True)
    set_prop(settings, "lumen_scene_detail", 1.0)
    post.set_editor_property("settings", settings)
    camera = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.CameraActor, unreal.Vector(-750, 0, 220), unreal.Rotator(0, 0, 0))
    camera.set_actor_label("ProofCamera")
    camera.set_actor_rotation(unreal.Rotator(-5, 0, 0), False)
    unreal.EditorLevelLibrary.set_level_viewport_camera_info(
        unreal.Vector(-750, 0, 220), unreal.Rotator(-5, 0, 0))
    unreal.EditorLevelLibrary.save_current_level()
    STATE.update(post=post, camera=camera, settings=settings, level=level)
    record("baseline_ready", level=level, exposure_bias=1.0, lumen_scene_detail=1.0)


def apply_learned_settings():
    settings = STATE["post"].get_editor_property("settings")
    set_prop(settings, "override_auto_exposure_method", True)
    set_prop(settings, "auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
    set_prop(settings, "override_auto_exposure_bias", True)
    set_prop(settings, "auto_exposure_bias", 15.0)
    set_prop(settings, "override_lumen_scene_detail", True)
    set_prop(settings, "lumen_scene_detail", 2.0)
    STATE["post"].set_editor_property("settings", settings)
    unreal.EditorLevelLibrary.save_current_level()
    record("learned_settings_applied", evidence={
        "manual_exposure": "video 00:02:27.000 forensic seek",
        "exposure_bias_15": "video 00:02:27.800 forensic frame",
        "lumen_scene_detail_2": "video 00:02:54.500 corrective forensic frame",
        "infinite_extent": "transcript 00:02:12.959–00:02:17.480",
    })


def validate():
    settings = STATE["post"].get_editor_property("settings")
    checks = {
        "post_process_unbound": bool(STATE["post"].get_editor_property("unbound")),
        "manual_exposure_override": bool(settings.override_auto_exposure_method),
        "manual_exposure": settings.auto_exposure_method == unreal.AutoExposureMethod.AEM_MANUAL,
        "exposure_bias_override": bool(settings.override_auto_exposure_bias),
        "exposure_bias_15": abs(float(settings.auto_exposure_bias) - 15.0) < 0.001,
        "lumen_detail_override": bool(settings.override_lumen_scene_detail),
        "lumen_detail_2": abs(float(settings.lumen_scene_detail) - 2.0) < 0.001,
        "material_exists": unreal.EditorAssetLibrary.does_asset_exist(
            "/Game/Proof/M_TutorialEmissive"),
        "level_exists": unreal.EditorAssetLibrary.does_asset_exist(STATE["level"]),
    }
    passed = all(checks.values())
    record("validation", passed=passed, checks=checks)
    result = {
        "schema": "beast.watch.proof/v1", "proof": "watch-001-lumen-emissive",
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "source": "https://www.youtube.com/watch?v=AO5I0yJEcPY",
        "status": "structural_pass" if passed else "failed",
        "checks": checks, "events": LOG,
        "visual_validation": "pending screenshot comparison",
    }
    (ROOT / "replay-log.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    if not passed:
        raise RuntimeError(f"structural validation failed: {checks}")


def capture(path):
    task = unreal.AutomationLibrary.take_high_res_screenshot(
        1280, 720, str(path), camera=STATE["camera"])
    if not task.is_valid_task():
        raise RuntimeError(f"screenshot task invalid: {path}")
    while not task.is_task_done():
        yield
    record("screenshot", file=str(path), exists=path.exists())


@unreal.AutomationScheduler.add_latent_command
def proof_start():
    try:
        (ROOT / "failure.txt").unlink(missing_ok=True)
        build_scene()
    except Exception:
        (ROOT / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
        unreal.SystemLibrary.quit_editor()
        return
    yield


@unreal.AutomationScheduler.add_latent_command
def capture_before():
    yield from capture(EVIDENCE / "before.png")


@unreal.AutomationScheduler.add_latent_command
def proof_apply():
    apply_learned_settings()
    yield


@unreal.AutomationScheduler.add_latent_command
def capture_after():
    yield from capture(EVIDENCE / "after.png")


@unreal.AutomationScheduler.add_latent_command
def proof_finish():
    try:
        validate()
    except Exception:
        (ROOT / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
    unreal.SystemLibrary.quit_editor()
    yield
