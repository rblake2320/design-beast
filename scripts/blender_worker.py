"""Trusted native worker, launched only in disposable background Blender processes."""
from __future__ import annotations

import json
from itertools import product
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from beast.blender_contract import require, validate
from beast.blender_runner import atomic_json, read_json


def evaluated_bounds(obj, mesh):
    points = [obj.matrix_world @ v.co for v in mesh.vertices]
    return [list(corner) for corner in product(*[(min(p[i] for p in points), max(p[i] for p in points))
                                                for i in range(3)])]


def primitive_shape(mesh):
    """Independent base-mesh invariants; do not trust an authored primitive label."""
    coords = [v.co for v in mesh.vertices]
    if len(coords) == 8 and len(mesh.polygons) == 6:
        if len({tuple(round(v, 6) for v in p) for p in coords}) == 8 and all(
                all(abs(abs(v) - 1) < 1e-6 for v in p) for p in coords):
            return "cube"
    if len(coords) == 482 and len(mesh.polygons) == 512:
        if all(abs(p.length - 1) < 1e-5 for p in coords):
            return "uv_sphere"
    if len(coords) == 136 and len(mesh.polygons) == 99:
        if (all(abs(p.z) < 1e-6 for p in coords) and
                len({round(p.x, 5) for p in coords}) == 34 and
                len({round(p.y, 5) for p in coords}) == 4):
            return "grid"
    return "unknown"


def observe():
    bpy.context.view_layer.update()
    result = {}
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
        mat = obj.active_material
        material = None
        if mat:
            shader = mat.node_tree.nodes.get("Principled BSDF")
            material = {"rgba": list(shader.inputs["Base Color"].default_value),
                        "roughness": shader.inputs["Roughness"].default_value,
                        "metallic": shader.inputs["Metallic"].default_value}
        bend = obj.modifiers.get("BeastBend")
        result[obj.name] = {"type": obj.type, "location": list(obj.location),
                            "rotation_deg": [math.degrees(v) for v in obj.rotation_euler],
                            "scale": list(obj.scale), "vertices": len(mesh.vertices),
                            "polygons": len(mesh.polygons), "material": material,
                            "base_vertices": len(obj.data.vertices), "base_polygons": len(obj.data.polygons),
                            "primitive_shape": primitive_shape(obj.data),
                            "modifier_count": len(obj.modifiers), "render_visible": not obj.hide_render,
                            "max_vertex_displacement": max(
                                ((v.co - obj.data.vertices[i].co).length for i, v in enumerate(mesh.vertices)),
                                default=0) if len(mesh.vertices) == len(obj.data.vertices) else None,
                            "modifier_state": {"type": bend.type, "method": bend.deform_method,
                                               "viewport": bend.show_viewport, "render": bend.show_render}
                            if bend else None,
                            "bend": {"axis": bend.deform_axis, "angle_deg": math.degrees(bend.angle)}
                            if bend else None,
                            "bounds": evaluated_bounds(obj, mesh)}
        obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
    return {"version": bpy.app.version_string, "objects": result}


def build(plan, output):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    trace = []
    for step in plan["steps"]:
        name, action = step["object"], step["action"]
        if action == "add_mesh":
            if step["primitive"] == "cube":
                bpy.ops.mesh.primitive_cube_add(size=2)
            elif step["primitive"] == "uv_sphere":
                bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1)
            else:
                bpy.ops.mesh.primitive_grid_add(x_subdivisions=33, y_subdivisions=3, size=2)
            bpy.context.object.name = name
        else:
            obj = bpy.data.objects[name]
            if action == "transform":
                obj.location = step["location"]
                obj.rotation_euler = [math.radians(v) for v in step["rotation_deg"]]
                obj.scale = step["scale"]
            elif action == "material":
                mat = bpy.data.materials.new(name + "Material")
                mat.use_nodes = True
                shader = mat.node_tree.nodes.get("Principled BSDF")
                for target, source in (("Base Color", "rgba"), ("Roughness", "roughness"), ("Metallic", "metallic")):
                    shader.inputs[target].default_value = step[source]
                obj.data.materials.clear()
                obj.data.materials.append(mat)
            elif action == "bend":
                modifier = obj.modifiers.new("BeastBend", "SIMPLE_DEFORM")
                modifier.deform_method = "BEND"
                modifier.deform_axis = step["axis"]
                modifier.angle = math.radians(step["angle_deg"])
        trace.append({"id": step["id"], "action": action, "observed": observe()})
        atomic_json(output / "steps.json", trace)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "scene.blend"))


def render_views(output):
    scene = bpy.context.scene
    points = [Vector(corner) for obj in observe()["objects"].values() for corner in obj["bounds"]]
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    center = (low + high) / 2
    radius = max((high - low).length / 2, 0.1)
    scene.world = bpy.data.worlds.new("BeastWorld")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.08, 0.10, 0.14, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.45
    for name, offset, power in (("Key", (2, -3, 4), 160), ("Fill", (-3, -1, 2), 90), ("Rim", (1, 3, 3), 140)):
        data = bpy.data.lights.new("Beast" + name, "AREA")
        light = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(light)
        light.location = center + Vector(offset) * radius
        light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
        data.energy, data.size = power * radius * radius, 2 * radius
    camera = bpy.data.objects.new("BeastCamera", bpy.data.cameras.new("BeastCamera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = radius * 3.2
    camera.data.clip_end = max(1000, radius * 20)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = False
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 2
    scene.render.resolution_x, scene.render.resolution_y = 512, 384
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    for index, angle in enumerate((-50, -20, 20, 50)):
        theta = math.radians(angle)
        camera.location = center + Vector((math.sin(theta), -math.cos(theta), 0.65)) * radius * 4
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(output / f"view-{index}.png")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    mode, directory = sys.argv[sys.argv.index("--") + 1:]
    output = Path(directory).resolve(strict=True)
    plan = read_json(output / "procedure.json")
    validate(plan)
    require(bpy.app.version_string == plan["blender_version"], "Blender version mismatch")
    if mode == "build":
        build(plan, output)
    elif mode == "verify":
        bpy.ops.wm.open_mainfile(filepath=str(output / "scene.blend"), use_scripts=False)
        atomic_json(output / "measurement.json", observe())
        render_views(output)
    else:
        raise ValueError("unknown worker mode")
