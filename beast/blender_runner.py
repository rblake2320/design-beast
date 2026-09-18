"""Standalone Blender execution with write-ahead receipts and fresh-process verification."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

from beast.blender_contract import require, validate

REPO = Path(__file__).resolve().parents[1]
WORKER = REPO / "scripts" / "blender_worker.py"


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path, max_bytes=2_000_000):
    require(Path(path).stat().st_size <= max_bytes, "JSON input exceeds size limit")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"invalid {value}")))


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    # Windows may transiently deny replacement while another reader owns a
    # non-sharing handle. Retry this exact replace only, never the Blender job.
    for attempt in range(5):
        try:
            os.replace(temporary, path)
            break
        except PermissionError as exc:
            if attempt == 4 or getattr(exc, "winerror", 5) not in (5, 32, 33):
                raise
            time.sleep(0.02 * (2 ** attempt))


def measure_checks(plan, measurement):
    """Compare reopened native state, not Blender's exit status or prose."""
    expected = validate(plan)
    require(isinstance(measurement, dict) and isinstance(measurement.get("objects"), dict),
            "malformed measurement")
    actual = measurement["objects"]
    gates = {"version_exact": measurement.get("version") == plan["blender_version"],
             "object_set_exact": set(actual) == set(expected)}

    def close(a, b):
        if isinstance(b, dict):
            return isinstance(a, dict) and set(a) == set(b) and all(close(a[k], v) for k, v in b.items())
        if isinstance(b, list):
            return isinstance(a, list) and len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
        if type(b) in (int, float):
            return type(a) in (int, float) and math.isfinite(a) and math.isclose(a, b, abs_tol=1e-4)
        return a == b

    for name, want in expected.items():
        got = actual.get(name, {})
        require(isinstance(got, dict), "object measurement must be an object")
        gates[f"{name}.type"] = got.get("type") == "MESH"
        for key in ("location", "rotation_deg", "scale", "material", "bend"):
            gates[f"{name}.{key}"] = key in got and close(got[key], want[key])
        topology = {"cube": (8, 6), "uv_sphere": (482, 512), "grid": (136, 99)}[want["primitive"]]
        gates[f"{name}.base_topology"] = (got.get("base_vertices"), got.get("base_polygons")) == topology
        gates[f"{name}.primitive_shape"] = got.get("primitive_shape") == want["primitive"]
        gates[f"{name}.modifier_state"] = got.get("modifier_state") == (
            {"type": "SIMPLE_DEFORM", "method": "BEND", "viewport": True, "render": True}
            if want["bend"] else None) and "modifier_state" in got
        gates[f"{name}.modifier_count"] = got.get("modifier_count") == (1 if want["bend"] else 0)
        gates[f"{name}.render_visible"] = got.get("render_visible") is True
        if want["bend"] and want["bend"]["angle_deg"] != 0:
            displacement = got.get("max_vertex_displacement")
            gates[f"{name}.bend_effect"] = (type(displacement) in (int, float) and
                                             math.isfinite(displacement) and displacement > 1e-6)
        gates[f"{name}.geometry"] = (type(got.get("vertices")) is int and got["vertices"] > 0
                                      and type(got.get("polygons")) is int and got["polygons"] > 0)
    return gates


def execute(plan, output, blender, *, allow_execute=False, timeout=120, evidence=None):
    require(allow_execute is True, "execution requires --allow-execute")
    validate(plan)
    require(type(timeout) in (int, float) and math.isfinite(timeout) and 1 <= timeout <= 600,
            "timeout must be 1..600 seconds per process")
    blender = Path(blender).expanduser().resolve(strict=True)
    require(blender.is_file(), "Blender executable is not a file")
    output = Path(output).absolute()
    require(output.parent.is_dir(), "output parent must already exist")
    # Atomic reservation: never overwrite, resume or reissue an existing run.
    output.mkdir(exist_ok=False)
    output = output.resolve()
    started = time.monotonic()
    receipt = {"schema": "beast.blender.execution/v1", "status": "outcome_unknown", "ok": False,
               "procedure_id": plan["id"], "authorization": "explicit_local_execute",
               "renderer": "CYCLES_CPU", "threads": 2, "processes": [],
               "source_claim": "typed_bindings" if evidence is not None else "owner_authored",
               "boundary": "Structural execution only; visual acceptance and tutorial comprehension not proven."}
    atomic_json(output / "receipt.json", receipt)
    try:
        atomic_json(output / "procedure.json", plan)
        if evidence is not None:
            atomic_json(output / "typed-evidence.json", evidence)
        receipt["procedure_sha256"] = digest(output / "procedure.json")
        receipt["worker_sha256"] = digest(WORKER)
        receipt["contract_sha256"] = digest(REPO / "beast" / "blender_contract.py")
        receipt["executable_sha256"] = digest(blender)
        for mode in ("build", "verify"):
            command = [str(blender), "--background", "--factory-startup", "--disable-autoexec",
                       "--threads", "2", "--python-exit-code", "23", "--python", str(WORKER),
                       "--", mode, str(output)]
            process_record = {"phase": mode, "command": command, "status": "outcome_unknown"}
            receipt["processes"].append(process_record)
            atomic_json(output / "receipt.json", receipt)
            with (output / f"{mode}.log").open("wb") as log:
                # No shell or interactive window; only this child is killed on timeout.
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                        timeout=timeout, cwd=output,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            process_record.update(status="exited", returncode=result.returncode)
            require(result.returncode == 0, f"Blender {mode} failed ({result.returncode}); see {mode}.log")
            if mode == "build":
                receipt["saved_scene_sha256"] = digest(output / "scene.blend")
        require(digest(output / "scene.blend") == receipt["saved_scene_sha256"],
                "saved scene changed during verification")
        measurement = read_json(output / "measurement.json")
        gates = measure_checks(plan, measurement)
        from PIL import Image, ImageStat
        for index in range(4):
            with Image.open(output / f"view-{index}.png") as image:
                image.load()
                gates[f"view-{index}.decoded"] = image.size == (512, 384)
                gates[f"view-{index}.nonuniform"] = max(ImageStat.Stat(image.convert("RGB")).stddev) > 2
        trace = read_json(output / "steps.json", max_bytes=32_000_000)
        require(isinstance(trace, list) and all(isinstance(s, dict) for s in trace), "malformed step trace")
        gates["step_trace_complete"] = (isinstance(trace, list) and
                                       [s.get("id") for s in trace] == [s["id"] for s in plan["steps"]])
        if gates["step_trace_complete"]:
            for index, step in enumerate(trace):
                prefix = {**plan, "steps": plan["steps"][:index + 1]}
                checks = measure_checks(prefix, step.get("observed"))
                gates[f"step.{step['id']}"] = all(checks.values())
        receipt["gates"] = gates
        receipt["ok"] = all(gates.values())
        receipt["status"] = "structurally_verified" if receipt["ok"] else "failed"
    except subprocess.TimeoutExpired:
        receipt["status"] = "outcome_unknown"
        receipt["error"] = "Blender timed out; child stopped, partial artifacts retained; no automatic replay"
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        receipt["status"] = "failed"
        receipt["error"] = f"{type(exc).__name__}: {exc}"
    receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
    receipt["artifacts"] = {p.name: {"sha256": digest(p), "bytes": p.stat().st_size}
                            for p in sorted(output.iterdir()) if p.is_file() and p.name != "receipt.json"}
    atomic_json(output / "receipt.json", receipt)
    return receipt
