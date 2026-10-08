"""Receiving-side proof inside UE 5.8; unique import destination, load/save readback."""
import hashlib
import json
import os
import re
from pathlib import Path

import unreal

version = unreal.SystemLibrary.get_engine_version()
if not version.startswith("5.8."):
    raise RuntimeError("Requires UE 5.8")
source = Path(os.environ["BEAST_ASSET_INPUT"]).resolve()
receipt = Path(os.environ["BEAST_ASSET_RECEIPT"]).resolve()
run_id = os.environ["BEAST_ASSET_RUN"]
if not re.fullmatch(r"[a-zA-Z0-9_-]+", run_id):
    raise RuntimeError("Invalid run identity")
dest = "/Game/BeastAssets/Run_" + run_id
verify_only = os.environ.get("BEAST_ASSET_VERIFY") == "1"
if verify_only:
    paths = list(unreal.EditorAssetLibrary.list_assets(dest, recursive=True))
else:
    if unreal.EditorAssetLibrary.does_directory_exist(dest):
        raise RuntimeError("Import destination already exists")
    task = unreal.AssetImportTask()
    task.filename = str(source)
    task.destination_path = dest
    task.automated = True
    task.save = True
    task.replace_existing = False
    task.async_ = False
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = list(task.imported_object_paths)
meshes = []
for asset_path in paths:
    asset = unreal.load_asset(asset_path)
    if isinstance(asset, unreal.StaticMesh):
        if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
            raise RuntimeError("Mesh save failed")
        loaded = unreal.load_asset(asset_path)
        box = loaded.get_bounds()
        extent = box.box_extent
        if max(extent.x, extent.y, extent.z) <= 0:
            raise RuntimeError("Mesh has no bounds")
        meshes.append({"asset": asset_path, "bounds_extent_cm": [extent.x, extent.y, extent.z],
                       "material_slots": len(loaded.static_materials),
                       "lods": loaded.get_num_lods()})
if not meshes:
    raise RuntimeError("Import produced no reloadable static meshes")
project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())
out = {"engine_version": version, "project": project, "run_id": run_id,
       "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
       "destination": dest, "meshes": meshes, "reloaded": True,
       "verification_process": verify_only}
temp = receipt.with_suffix(".tmp")
temp.write_text(json.dumps(out, indent=2), encoding="utf-8")
os.replace(temp, receipt)
print("BEAST_UE58_IMPORTED " + str(len(meshes)))
