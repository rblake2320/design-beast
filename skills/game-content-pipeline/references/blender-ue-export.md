# Blender 5.1 → UE 5.8 Export

## Scene setup (once per .blend)

```python
import bpy
s = bpy.context.scene
s.unit_settings.system = 'METRIC'
s.unit_settings.scale_length = 0.01   # THE critical setting — fixes 0.01-scale bones in UE
```
Then select all, Apply All Transforms (`bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)`).

## Format decision

- **Skeletal mesh / animation / morph targets / LODs → FBX**
- **Static mesh with PBR materials → GLB** (Interchange auto-creates Material Instances from metallic-roughness; "Import Into Level" is glTF/MaterialX-only)
- **Full scene sync → USD** (only when genuinely needed)

## FBX export (skeletal) — exact kwargs

```python
bpy.ops.export_scene.fbx(
    filepath=out_path,
    use_selection=True,
    global_scale=1.0,
    apply_scale_options='FBX_SCALE_ALL',
    axis_forward='-Z', axis_up='Y',
    mesh_smooth_type='FACE',
    use_tspace=True,
    add_leaf_bones=False,
    bake_anim=True,                    # False for mesh-only export
    object_types={'ARMATURE', 'MESH'},
)
```

## GLB export (static)

```python
bpy.ops.export_scene.gltf(
    filepath=out_path,                 # .glb
    export_format='GLB',
    use_selection=True,
    export_yup=True,
    export_apply=True,                 # apply modifiers
)
```

⚠️ Blender 5.0 swapped the FBX **importer** to C++ ufbx; the **exporter** is unchanged, but verify kwargs against 5.1.2 with `blender -b --python-expr "import bpy; help(bpy.ops.export_scene.fbx)"` if an export errors.

## Headless invocation

```bash
"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b asset.blend -P scripts/blender_export.py -- --out asset.fbx --skeletal
```
Use `scripts/blender_export.py` in this skill — it wires the settings above.

## Interactive alternative: Blender MCP bridge

Blender must be running. The bridge (~50 tools: add_object, modifiers, geometry nodes, materials, keyframes, render, export_file, execute_python) hits a listener on :9876 inside Blender. `execute_python` is the escape hatch — result must be a **dict** (`result = {"key": value}`).

## Do NOT use Send-to-Unreal addon in automation

Epic's repo is dead (2.4.3, Nov 2023). The live fork poly-hammer/BlenderTools (Send to Unreal 2.6.7) has a Blender 5.0 patch but nothing claims 5.1/UE 5.8 testing. Headless bpy export + UE python import is the reliable path.

## Import side (UE)

Interchange is default since 5.4 (handles fbx/gltf/glb/usd). If Interchange-FBX misbehaves, legacy importer: console var `Interchange.FeatureFlags.Import.FBX=false`.

Headless import example (run via `UnrealEditor-Cmd.exe -run=pythonscript`):
```python
import unreal
task = unreal.AssetImportTask()
task.filename = r"C:\path\asset.fbx"
task.destination_path = "/Game/Assets/Characters"
task.automated = True
task.save = True
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
```

## Rigging paths

1. **Rigify** (free, ships in Blender): generate rig → export deform bones only.
2. **Auto-Rig Pro** ($40): dedicated UE export presets — the solo-dev standard.
3. **UE-side retargeting**: IK Rig + IK Retargeter make Mixamo→UE-Mannequin near one-click since 5.4.
4. Control Rig Physics (Beta, 5.8) for physical secondary motion.

## Nanite / Lumen asset rules

- Nanite: opaque or masked materials ONLY (no translucency), DX12 + SM6, skip LOD generation entirely. Skeletal Nanite is Experimental (no morph targets) — verify before relying on it.
- Lumen: no lightmap UVs needed; keep materials instanced; watch Surface Cache card coverage on complex interiors.
