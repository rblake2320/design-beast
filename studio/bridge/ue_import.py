# Runs INSIDE UnrealEditor-Cmd (-run=pythonscript). Imports an FBX as a StaticMesh.
# Args: <fbx_path> [dest_path=/Game/BeastAssets]
import sys

import unreal

fbx = sys.argv[1]
dest = sys.argv[2] if len(sys.argv) > 2 else "/Game/BeastAssets"

options = unreal.FbxImportUI()
options.import_mesh = True
options.import_as_skeletal = False
options.import_animations = False
options.import_materials = True
options.import_textures = True
options.static_mesh_import_data.combine_meshes = True

task = unreal.AssetImportTask()
task.filename = fbx
task.destination_path = dest
task.automated = True
task.save = True
task.replace_existing = True
task.options = options

unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
paths = list(task.imported_object_paths or [])
print("BEAST_IMPORTED:", paths)
if not paths:
    raise SystemExit(1)
