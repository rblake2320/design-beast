"""Headless Blender -> UE exporter with correct scale/axis conventions.

Usage:
  blender -b scene.blend -P blender_export.py -- --out asset.fbx --skeletal
  blender -b scene.blend -P blender_export.py -- --out asset.glb
  blender -b scene.blend -P blender_export.py -- --out a.fbx --skeletal --objects Armature,Body

FBX (--skeletal) for rigs/animation; GLB (default for .glb out) for static PBR meshes.
"""
import argparse
import sys

import bpy


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True, help="output path (.fbx or .glb)")
    p.add_argument("--skeletal", action="store_true", help="export armature + baked anim (FBX only)")
    p.add_argument("--objects", default="", help="comma-separated object names (default: all)")
    return p.parse_args(argv)


def main():
    args = parse_args()

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 0.01  # UE convention; prevents 0.01-scale bones

    # Selection
    bpy.ops.object.select_all(action="DESELECT")
    if args.objects:
        names = [n.strip() for n in args.objects.split(",")]
        for n in names:
            obj = bpy.data.objects.get(n)
            if obj is None:
                print(f"ERROR: object '{n}' not found", file=sys.stderr)
                sys.exit(1)
            obj.select_set(True)
        use_selection = True
    else:
        for obj in scene.objects:
            if obj.type in {"MESH", "ARMATURE"}:
                obj.select_set(True)
        use_selection = True

    # Apply transforms on selected meshes/armatures
    for obj in bpy.context.selected_objects:
        bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    out = args.out
    if out.lower().endswith(".fbx"):
        bpy.ops.export_scene.fbx(
            filepath=out,
            use_selection=use_selection,
            global_scale=1.0,
            apply_scale_options="FBX_SCALE_ALL",
            axis_forward="-Z",
            axis_up="Y",
            mesh_smooth_type="FACE",
            use_tspace=True,
            add_leaf_bones=False,
            bake_anim=args.skeletal,
            object_types={"ARMATURE", "MESH"} if args.skeletal else {"MESH"},
        )
    elif out.lower().endswith((".glb", ".gltf")):
        bpy.ops.export_scene.gltf(
            filepath=out,
            export_format="GLB",
            use_selection=use_selection,
            export_yup=True,
            export_apply=True,
        )
    else:
        print("ERROR: --out must end in .fbx, .glb or .gltf", file=sys.stderr)
        sys.exit(1)

    print(f"EXPORTED: {out}")


main()
