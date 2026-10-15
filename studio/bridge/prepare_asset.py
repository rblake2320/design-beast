"""Runs in an owned background Blender process; preserves glTF meter units."""
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

source, output, budget = sys.argv[sys.argv.index("--") + 1:]
source, output, budget = Path(source), Path(output), int(budget)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 1.0
bpy.ops.import_scene.gltf(filepath=str(source))
objects = list(bpy.context.scene.objects)
meshes = [obj for obj in objects if obj.type == "MESH"]
if not meshes:
    raise RuntimeError("Imported asset has no mesh geometry")


def triangles():
    count = 0
    for obj in meshes:
        obj.data.calc_loop_triangles()
        count += len(obj.data.loop_triangles)
    return count


def bounds():
    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    return low, high


before = triangles()
initial_low, initial_high = bounds()
if before > budget:
    for obj in meshes:
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new("Beast triangle budget", "DECIMATE")
        mod.ratio = max(.001, .98 * budget / before)
        bpy.ops.object.modifier_apply(modifier=mod.name)
if not 0 < triangles() <= budget:
    raise RuntimeError("Triangle budget could not be satisfied")
low, high = bounds()
size = max(high - low)
if not math.isfinite(size) or size <= 0:
    raise RuntimeError("Asset has invalid bounds")
bpy.ops.object.select_all(action="DESELECT")
for obj in objects:
    obj.select_set(True)
bpy.ops.file.pack_all()
bpy.ops.export_scene.gltf(filepath=str(output / "model.glb"), export_format="GLB",
                          use_selection=True, export_yup=True, export_animations=False)
bpy.ops.export_scene.fbx(filepath=str(output / "asset.fbx"), use_selection=True,
                         apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                         object_types={"MESH", "EMPTY"}, bake_anim=False,
                         path_mode="COPY", embed_textures=True, axis_forward="-Z", axis_up="Y")
receipt = {"blender_version": bpy.app.version_string,
           "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
           "triangles_before": before, "triangles": triangles(),
           "mesh_objects": len(meshes), "material_slots": sum(len(o.material_slots) for o in meshes),
           "bounds_m": {"min": list(low), "max": list(high)},
           "source_bounds_m": {"min": list(initial_low), "max": list(initial_high)},
           "units": "meters", "unit_scale": 1.0}
(output / "blender-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")

# A render and camera live in the editable source, but do not enter mesh exports.
center = (low + high) * .5
bpy.ops.object.camera_add(location=center + Vector((1.5, -2.3, 1.35)) * size)
camera = bpy.context.object
camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
camera.data.type = "ORTHO"
camera.data.ortho_scale = size * 1.8
scene = bpy.context.scene
scene.camera = camera
for location, energy in [((2, -3, 4), 900), ((-3, -1, 2), 500), ((1, 3, 3), 700)]:
    bpy.ops.object.light_add(type="AREA", location=center + Vector(location) * size)
    light = bpy.context.object
    light.data.energy = energy * size * size
    light.data.shape = "DISK"
    light.data.size = size * 2
    light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
scene.world = bpy.data.worlds.new("Beast preview world")
scene.world.color = (.12, .12, .12)
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 16
scene.render.resolution_x = 640
scene.render.resolution_y = 480
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(output / "preview.png")
bpy.ops.wm.save_as_mainfile(filepath=str(output / "asset.blend"))
bpy.ops.render.render(write_still=True)
print("BEAST_ASSET_PREPARED")
