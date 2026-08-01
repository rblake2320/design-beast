"""Adopt a previously assembled local UE 5.8 MetaHuman Blueprint into a fresh run."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import read_receipt, require_context, require_under_run, write_receipt

MARKER = "BEAST_METAHUMAN_ASSEMBLY_ADOPTED="


def main() -> dict:
    context = require_context()
    preflight = read_receipt(context, "preflight", "PREFLIGHT_READY")
    source = os.environ.get("BEAST_MH_EXISTING_BLUEPRINT", "").strip()
    if not source:
        raise RuntimeError("BEAST_MH_EXISTING_BLUEPRINT must name a reviewed local UE 5.8 Blueprint")
    target = require_under_run(
        os.environ.get(
            "BEAST_MH_BLUEPRINT",
            context["content_root"] + "/MetaHumans/AdaProof/BP_AdaProof",
        ),
        context,
    )
    assets = unreal.EditorAssetLibrary
    if not assets.does_asset_exist(source):
        raise RuntimeError(f"Existing assembled Blueprint is missing: {source}")
    source_asset = unreal.load_asset(source)
    if source_asset is None or source_asset.get_class().get_name() != "Blueprint":
        raise RuntimeError(f"Existing asset is not a Blueprint: {source}")
    if assets.does_asset_exist(target):
        raise RuntimeError(f"Fresh-run Blueprint target already exists: {target}")
    duplicated = assets.duplicate_asset(source, target)
    if duplicated is None or duplicated.get_class().get_name() != "Blueprint":
        raise RuntimeError(f"Failed to duplicate reviewed Blueprint into fresh run: {target}")
    if not assets.save_asset(target, only_if_is_dirty=False):
        raise RuntimeError(f"Failed to save adopted Blueprint: {target}")
    result = {
        "state": "ASSEMBLY_CANDIDATE",
        "project": context["project"],
        "run_id": context["run_id"],
        "asset": preflight["asset"],
        "blueprint": target,
        "assembly_mode": "ADOPTED_LOCAL_UE58_BLUEPRINT",
        "source_blueprint": source,
        "new_asset_count": 1,
        "dependencies_reused_from_prior_local_assembly": True,
        "external_work_performed": False,
        "clean_log_review_required": True,
    }
    unreal.log(MARKER + json.dumps(result, sort_keys=True))
    write_receipt(context, "assembly-candidate", result)
    return result


if __name__ == "__main__":
    main()
