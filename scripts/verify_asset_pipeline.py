"""Exercise the shipped static-asset flow without spending generation credits.

python scripts/verify_asset_pipeline.py --source <owned.glb> --output <folder> [--unreal]
Provider retrieval can be checked separately using Studio's existing-task picker.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "studio"))
import asset_pipeline as pipeline  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--unreal", action="store_true")
    parser.add_argument("--viewport", action="store_true", help="GPU-admitted offscreen Unreal visual check")
    args = parser.parse_args()
    if args.viewport and not args.unreal:
        parser.error("--viewport requires --unreal")
    folder = args.output.resolve()
    if folder.exists():
        parser.error("output must be a fresh directory")
    folder.mkdir(parents=True)
    t = time.monotonic()
    result = {"source": args.source.name, "credits_spent": 0, "checks": []}
    try:
        prepared = pipeline.prepare(args.source.resolve(), folder, 30000)
        result["checks"].append({"scenario": "real Blender preparation", "outcome": "Worked",
                                 "receipt": prepared})
        # Reimport the shipped GLB in a fresh Blender process and compare bounds.
        probe = folder / "reopen.py"
        probe.write_text("import bpy,json;from mathutils import Vector\n"
            + "bpy.ops.wm.read_factory_settings(use_empty=True)\n"
            + "bpy.ops.import_scene.gltf(filepath=" + repr(str(folder / "model.glb")) + ")\n"
            + "points=[o.matrix_world@Vector(c) for o in bpy.context.scene.objects if o.type=='MESH' for c in o.bound_box]\n"
            + "low=[min(p[i] for p in points) for i in range(3)];high=[max(p[i] for p in points) for i in range(3)]\n"
            + "open(" + repr(str(folder / "reopen.json")) + ",'w').write(json.dumps({'min':low,'max':high}))\n")
        pipeline.run_owned([str(pipeline.config.path("blender")), "-b", "--python-exit-code", "1",
                            "-P", str(probe)], folder, "reopen.log")
        reopened = json.loads((folder / "reopen.json").read_text())
        expected = prepared["blender"]["bounds_m"]
        difference = max(abs(reopened[key][i] - expected[key][i]) for key in ("min", "max") for i in range(3))
        if difference > .0001:
            raise pipeline.AssetError("Export bounds changed on reopen")
        result["checks"].append({"scenario": "GLB reopened in fresh Blender", "outcome": "Worked",
                                 "max_bounds_difference_m": difference})
        if args.unreal:
            ue = pipeline.import_unreal(folder / "model.glb", folder)
            result["checks"].append({"scenario": "Unreal 5.8 import and asset readback", "outcome": "Worked", "receipt": ue})
            # Separate process: reload saved packages with no import operation.
            exe, project = pipeline.unreal_target()
            verification = folder / "unreal-reopened.json"
            env = os.environ.copy()
            env.update(BEAST_ASSET_INPUT=str(folder / "model.glb"), BEAST_ASSET_RUN=folder.name,
                       BEAST_ASSET_RECEIPT=str(verification), BEAST_ASSET_VERIFY="1")
            script = REPO / "studio/bridge/import_asset_ue58.py"
            pipeline.run_owned([str(exe), str(project), "-run=pythonscript", f"-script={script}",
                "-nullrhi", "-unattended", "-nop4", "-nosplash", "-stdout"], folder,
                "unreal-reopened.log", env=env, timeout=900)
            reopened_ue = json.loads(verification.read_text())
            if reopened_ue["meshes"] != ue["meshes"] or not reopened_ue["verification_process"]:
                raise pipeline.AssetError("Saved Unreal meshes changed on restart")
            result["checks"].append({"scenario": "saved meshes reloaded in separate Unreal process",
                                     "outcome": "Worked", "meshes": reopened_ue["meshes"]})
            if args.viewport:
                import resource_guard
                admission = resource_guard.admission("unreal_full", use_cache=False)
                pipeline.atomic_json(folder / "viewport-admission.json", admission)
                if not admission["admitted"]:
                    raise pipeline.AssetError("Unreal viewport GPU admission denied: " + "; ".join(admission["reasons"]))
                env = os.environ.copy()
                env["BEAST_VIEWPORT_FOLDER"] = str(folder)
                script = REPO / "studio/bridge/capture_asset_ue58.py"
                pipeline.run_owned([str(exe), str(project), "-RenderOffscreen", "-unattended", "-nop4",
                    "-nosplash", "-stdout", "-ExecCmds=py " + str(script)], folder,
                    "viewport.log", env=env, timeout=120)
                viewport = json.loads((folder / "viewport-receipt.json").read_text())
                if viewport.get("outcome") != "Worked":
                    raise pipeline.AssetError("Unreal viewport capture failed; inspect retained receipt")
                result["checks"].append({"scenario": "Unreal rendered viewport", "outcome": "Worked",
                                         "receipt": viewport, "visual_review": "required"})
        result["outcome"] = "Worked"
        code = 0
    except Exception as error:
        result.update(outcome="Failed", error=str(error))
        code = 1
    result["elapsed_seconds"] = round(time.monotonic() - t, 3)
    pipeline.atomic_json(folder / "verification.json", result)
    print(json.dumps({"outcome": result["outcome"], "checks": len(result["checks"]),
                      "elapsed_seconds": result["elapsed_seconds"], "error": result.get("error")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
