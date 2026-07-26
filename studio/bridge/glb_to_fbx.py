# Headless Blender: GLB -> UE-ready FBX.
# Usage: blender -b -P glb_to_fbx.py -- <in.glb> <out.fbx>
import sys

import bpy

src, dst = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)

# TRELLIS meshes arrive ~1 unit tall; UE works in cm — scale to a usable prop size.
for obj in bpy.data.objects:
    if obj.type == "MESH":
        obj.scale = (100, 100, 100)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

bpy.ops.export_scene.fbx(
    filepath=dst,
    apply_unit_scale=True,
    apply_scale_options="FBX_SCALE_NONE",
    use_mesh_modifiers=True,
    path_mode="COPY",
    embed_textures=True,
)
print("FBX_WRITTEN:", dst)
