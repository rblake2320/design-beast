"""Execute the compiled glass procedure in Blender (headless) and record a structural readback.

blender -b --factory-startup -P execute_glass.py -- <typed-state.json> <out_dir>

Values come only from typed-state.json. The scene (cube, backdrop, area light, camera)
is a declared stand-in: the tutorial built it in an earlier video and never shows it.
"""
import colorsys
import json
import os
import sys
from pathlib import Path

import bpy

state_path, out = Path(sys.argv[-2]).resolve(), Path(sys.argv[-1]).resolve()
# Stand-in set. run2 used "white"; repair run3 moved to "studio" to match the
# tutorial's blue-grey title shots. Materials are never changed by the repair.
SET = {
    "white": {"samples": 256, "world": (0.05, 0.05, 0.06, 1), "backdrop": (0.6, 0.6, 0.6, 1), "energy": 1500},
    "studio": {"samples": 1024, "world": (0.18, 0.22, 0.30, 1), "backdrop": (0.20, 0.24, 0.30, 1), "energy": 900},
}[os.environ.get("BEAST_SET", "white")]
out.mkdir(parents=True, exist_ok=True)
state = json.loads(state_path.read_text(encoding="utf-8"))
assert state["status"] == "answered", "refusing to execute an unresolved typed state"
V = {row["name"]: row["value"] for row in state["values"]}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def base_rgba(prefix):
    # Blender's picker shows HSV in display (sRGB) space; sockets take scene-linear RGB.
    r, g, b = colorsys.hsv_to_rgb(V[f"{prefix}.base_h"], V[f"{prefix}.base_s"], V[f"{prefix}.base_v"])
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), 1.0)


# Principled BSDF v1 (3.x) -> v2 (4.0+) socket names.
SOCKETS = {"metallic": "Metallic", "specular": "Specular IOR Level", "roughness": "Roughness",
           "ior": "IOR", "transmission": "Transmission Weight"}
VARIANTS = {
    "transparent": {},
    "frosted": {"roughness": V["frosted.roughness"]},
    "tinted": {"base": "tinted"},
}

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "GPU"
prefs = bpy.context.preferences.addons["cycles"].preferences
for backend in ("OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = backend
        prefs.get_devices()
        if any(d.type == backend for d in prefs.devices):
            break
    except TypeError:
        continue
for d in prefs.devices:
    d.use = d.type == prefs.compute_device_type
scene.cycles.samples = SET["samples"]
scene.cycles.use_denoising = True
scene.cycles.seed = 0
scene.render.resolution_x, scene.render.resolution_y = 1280, 720
scene.view_settings.view_transform = "Standard"

world = bpy.data.worlds.new("World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = SET["world"]
scene.world = world

# Stand-in set: curved backdrop plane (light grey, per narration), area light, camera.
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, -1))
backdrop = bpy.context.active_object
bg = bpy.data.materials.new("backdrop")
bg.use_nodes = True
bg.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = SET["backdrop"]
backdrop.data.materials.append(bg)
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 8, 14), rotation=(1.5708, 0, 0))
bpy.context.active_object.data.materials.append(bg)
bpy.ops.object.light_add(type="AREA", location=(-3, -2, 5), rotation=(0.6, -0.5, 0))
light = bpy.context.active_object
light.data.energy, light.data.size = SET["energy"], 4
bpy.ops.object.camera_add(location=(5.2, -6.4, 3.4), rotation=(1.18, 0, 0.68))
scene.camera = bpy.context.active_object

bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
cube = bpy.context.active_object
cube.name = "GlassCube"

readback = {}
for name, override in VARIANTS.items():
    mat = bpy.data.materials.new(f"{name} glass")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.distribution = V["distribution"].upper().replace(" ", "_")
    bsdf.inputs["Base Color"].default_value = base_rgba(override.get("base", "transparent"))
    for key, socket in SOCKETS.items():
        bsdf.inputs[socket].default_value = override.get(key, V[f"transparent.{key}"])
    cube.data.materials.clear()
    cube.data.materials.append(mat)
    scene.render.filepath = str(out / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    readback[name] = {
        "distribution": bsdf.distribution,
        "base_color_linear": [round(c, 6) for c in bsdf.inputs["Base Color"].default_value],
        **{socket: round(bsdf.inputs[socket].default_value, 6) for socket in SOCKETS.values()},
    }
    if name == "tinted":
        bpy.ops.object.select_all(action="DESELECT")
        cube.select_set(True)
        bpy.ops.export_scene.gltf(filepath=str(out / "tinted_glass.glb"), export_format="GLB",
                                  use_selection=True)

(out / "readback.json").write_text(json.dumps({
    "blender": bpy.app.version_string,
    "device": [f"{d.type}:{d.name}" for d in prefs.devices if d.use],
    "materials": readback}, indent=2), encoding="utf-8")
print("BEAST_EXECUTE_OK")
