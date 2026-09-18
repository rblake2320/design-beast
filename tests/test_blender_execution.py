"""Closed-contract negatives plus explicitly opted-in real Blender artifact checks."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from beast.blender_contract import bind_fields, validate
from beast.blender_runner import execute, measure_checks, read_json

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def plan():
    return read_json(ROOT / "examples/blender/blockout.json")


def test_example_has_three_objects(plan):
    assert set(validate(plan)) == {"Base", "CoralCube", "TealSphere"}


def test_partial_acceptance_never_passes():
    from scripts.verify_blender_execution import EXPECTED_CASES, acceptance_state
    cases = [{"case": name, "passed": True} for name in EXPECTED_CASES]
    for count in range(5):
        assert not acceptance_state(cases[:count], complete=True)["ok"]
    assert not acceptance_state(cases)["ok"]
    assert acceptance_state(cases, complete=True)["ok"]
    assert not acceptance_state(cases[::-1], complete=True)["ok"]


@pytest.mark.parametrize("value", [None, [], "script", 2, {}, {"schema": "wrong"}])
def test_malformed_envelope(value):
    with pytest.raises(ValueError):
        validate(value)


@pytest.mark.parametrize("field,value", [("action", "python"), ("action", []),
                                         ("object", "../escape"), ("object", "__BeastCamera"),
                                         ("primitive", "script"), ("primitive", {})])
def test_rejects_unbounded_operations(plan, field, value):
    plan["steps"][0][field] = value
    with pytest.raises(ValueError):
        validate(plan)


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -0.1, 101, "1", {}, None])
def test_transform_scale_is_bounded(plan, value):
    plan["steps"][1]["scale"][0] = value
    with pytest.raises(ValueError):
        validate(plan)


def test_duplicate_steps_objects_forward_targets_and_unknown_keys(plan):
    for bad in (plan["steps"] + [plan["steps"][0]], plan["steps"][1:], []):
        candidate = copy.deepcopy(plan)
        candidate["steps"] = bad
        with pytest.raises(ValueError):
            validate(candidate)
    plan["output"] = "C:/outside"
    with pytest.raises(ValueError):
        validate(plan)


def test_material_bounds(plan):
    plan["steps"][2]["rgba"][3] = 0
    with pytest.raises(ValueError):
        validate(plan)


def test_denied_before_any_output_or_child(tmp_path, plan, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("child launched"))
    with pytest.raises(ValueError, match="allow-execute"):
        execute(plan, tmp_path / "run", sys.executable)
    assert list(tmp_path.iterdir()) == []


def test_unknown_action_denied_before_output(tmp_path, plan, monkeypatch):
    plan["steps"][0]["action"] = "exec"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("child launched"))
    with pytest.raises(ValueError):
        execute(plan, tmp_path / "run", sys.executable, allow_execute=True)
    assert not (tmp_path / "run").exists()


def test_existing_run_never_reissued(tmp_path, plan, monkeypatch):
    marker = tmp_path / "original.txt"
    marker.write_text("preserve")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("child launched"))
    with pytest.raises(FileExistsError):
        execute(plan, tmp_path, sys.executable, allow_execute=True)
    assert marker.read_text() == "preserve"


@pytest.mark.parametrize("timeout", [0, 601, float("nan"), True])
def test_invalid_deadline(tmp_path, plan, timeout):
    with pytest.raises(ValueError):
        execute(plan, tmp_path / "run", sys.executable, allow_execute=True, timeout=timeout)


def test_timeout_retains_unknown_intent(tmp_path, plan, monkeypatch):
    output = tmp_path / "run"

    def timeout(command, **kwargs):
        intent = read_json(output / "receipt.json")
        assert intent["status"] == "outcome_unknown"
        assert intent["processes"][-1]["status"] == "outcome_unknown"
        assert "--python-exit-code" in command and "--disable-autoexec" in command
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", timeout)
    result = execute(plan, output, sys.executable, allow_execute=True)
    assert result["status"] == "outcome_unknown" and not result["ok"]
    assert (output / "build.log").is_file()
    assert read_json(output / "receipt.json") == result


def test_child_failure_does_not_verify(tmp_path, plan, monkeypatch):
    calls = []

    def fail(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 23)

    monkeypatch.setattr(subprocess, "run", fail)
    result = execute(plan, tmp_path / "run", sys.executable, allow_execute=True)
    assert len(calls) == 1 and not result["ok"] and result["status"] == "failed"


def test_exit_zero_without_artifact_is_failure(tmp_path, plan, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, 0))
    result = execute(plan, tmp_path / "run", sys.executable, allow_execute=True)
    assert not result["ok"] and "FileNotFoundError" in result["error"]


def test_measurement_must_match_native_state(plan):
    objects = validate(plan)
    for obj in objects.values():
        obj.update(type="MESH", vertices=8, polygons=6)
        obj.update(base_vertices=482 if obj["primitive"] == "uv_sphere" else 8,
                   base_polygons=512 if obj["primitive"] == "uv_sphere" else 6,
                   primitive_shape=obj["primitive"], modifier_state=None,
                   modifier_count=0, render_visible=True)
    measurement = {"version": plan["blender_version"], "objects": objects}
    assert all(measure_checks(plan, measurement).values())
    measurement["objects"]["CoralCube"]["scale"][0] = 3
    assert not all(measure_checks(plan, measurement).values())
    measurement["objects"]["TealSphere"]["vertices"] = 0
    assert not measure_checks(plan, measurement)["TealSphere.geometry"]


def test_missing_object_or_wrong_version_fails(plan):
    gates = measure_checks(plan, {"version": "0.0.0", "objects": {}})
    assert not any(gates.values())


def test_triangle_cannot_prove_cube(plan):
    objects = validate(plan)
    for obj in objects.values():
        obj.update(type="MESH", vertices=3, polygons=1, base_vertices=3, base_polygons=1,
                   primitive_shape="cube", modifier_state=None)
    gates = measure_checks(plan, {"version": plan["blender_version"], "objects": objects})
    assert not gates["CoralCube.base_topology"]


def test_malformed_object_measurement_is_classified(plan):
    with pytest.raises(ValueError, match="object measurement"):
        measure_checks(plan, {"version": "5.1.2", "objects": {"Base": []}})


def test_disabled_bend_fails(plan):
    plan["steps"].append({"id":"bend", "action":"bend", "object":"CoralCube", "axis":"Y", "angle_deg":45})
    objects = validate(plan)
    objects["CoralCube"]["modifier_state"] = {"type":"SIMPLE_DEFORM", "method":"BEND", "viewport":False, "render":True}
    assert not measure_checks(plan, {"version":"5.1.2", "objects":objects})["CoralCube.modifier_state"]


def test_noop_bend_cannot_prove_deformation(plan):
    plan["steps"].append({"id":"bend", "action":"bend", "object":"CoralCube", "axis":"Y", "angle_deg":45})
    objects = validate(plan)
    objects["CoralCube"]["max_vertex_displacement"] = 0
    assert not measure_checks(plan, {"version":"5.1.2", "objects":objects})["CoralCube.bend_effect"]


def test_atomic_replace_retries_only_replace(tmp_path, monkeypatch):
    from beast.blender_runner import atomic_json
    original = os.replace
    calls = []

    def transient(source, dest):
        calls.append((source, dest))
        if len(calls) < 3:
            error = PermissionError("simulated sharing denial")
            error.winerror = 5
            raise error
        original(source, dest)

    monkeypatch.setattr(os, "replace", transient)
    atomic_json(tmp_path / "receipt.json", {"ok": False})
    assert len(calls) == 3
    assert read_json(tmp_path / "receipt.json") == {"ok": False}


def test_persistent_replace_denial_preserves_both_receipts(tmp_path, monkeypatch):
    from beast.blender_runner import atomic_json
    path = tmp_path / "receipt.json"
    atomic_json(path, {"status":"outcome_unknown"})

    def denied(*args):
        error = PermissionError("simulated persistent denial")
        error.winerror = 5
        raise error

    monkeypatch.setattr(os, "replace", denied)
    with pytest.raises(PermissionError):
        atomic_json(path, {"status":"failed"})
    assert read_json(path)["status"] == "outcome_unknown"
    assert read_json(path.with_suffix(".json.tmp"))["status"] == "failed"


def test_strict_json(tmp_path):
    path = tmp_path / "bad.json"
    for value in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
        path.write_text(value)
        with pytest.raises(ValueError):
            read_json(path)


def test_binding_requires_resolved_matching_target(plan):
    plan["steps"][1]["scale"][0] = {"field": "base_width"}
    state = {"schema": "beast.watch.typed-state/v1", "status": "answered", "application": "Blender",
             "version": "5.1.2", "values": [{"name": "base_width", "value": 2.4}]}
    bound, used = bind_fields(plan, state)
    assert used == ["base_width"] and bound["steps"][1]["scale"][0] == 2.4
    for key, value in (("status", "insufficient_evidence"), ("application", "Inkscape"),
                       ("version", "5.0.0"), ("errors", ["bad frame"])):
        bad = {**state, key: value}
        with pytest.raises(ValueError):
            bind_fields(plan, bad)


def test_cli_rejection_is_structured(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/blender_execute.py"),
                             str(ROOT / "examples/blender/blockout.json"), "--output", str(tmp_path / "out")],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "rejected"
    assert not (tmp_path / "out").exists()


def test_watch_binding_recompiles_pixels_and_rejects_tamper(tmp_path, plan, monkeypatch):
    from PIL import Image
    from watch.typed_evidence import document_fingerprint
    from beast.blender_runner import digest
    from scripts import blender_execute

    frame = tmp_path / "frame.png"
    Image.new("RGB", (16, 16), (20, 30, 40)).save(frame)
    target = {"schema":"beast.watch.typed-target/v1", "application":"Blender", "version":"5.1.2",
              "fields":[{"name":"width", "type":"number", "minimum":0.1, "maximum":10}]}
    timeline = {"bundle_fingerprint":"synthetic-test-only", "frames":[
        {"id":"f1", "file":"frame.png", "source_seconds":1, "sha256":digest(frame)}]}
    observations = {"schema":"beast.watch.typed-observations/v1",
                    "target_fingerprint":document_fingerprint(target),
                    "timeline_fingerprint":timeline["bundle_fingerprint"], "observations":[
                        {"field":"width", "raw_value":2.4, "phase":"final", "confidence":0.99,
                         "evidence":[{"frame_id":"f1", "method":"manual_review", "region":[0,0,16,16]}]}]}
    plan["steps"][1]["scale"][0] = {"field":"width"}
    for name, content in (("plan", plan), ("target", target), ("observations", observations), ("timeline", timeline)):
        (tmp_path / f"{name}.json").write_text(json.dumps(content))
    calls = []

    def capture(plan, *args, **kwargs):
        calls.append((plan, kwargs["evidence"]))
        return {"ok":True, "status":"test_only"}

    monkeypatch.setattr(blender_execute, "execute", capture)
    argv = [str(tmp_path / "plan.json"), "--output", str(tmp_path / "out"), "--allow-execute"]
    for name in ("target", "observations", "timeline"):
        argv.extend(["--" + name, str(tmp_path / f"{name}.json")])
    assert blender_execute.main(argv) == 0
    assert calls[0][0]["steps"][1]["scale"][0] == 2.4
    assert calls[0][1]["bound_fields"] == ["width"]
    Image.new("RGB", (16, 16), (50, 30, 40)).save(frame)
    assert blender_execute.main(argv) == 2
    assert len(calls) == 1


def test_malformed_measurement_keeps_failure_receipt(tmp_path, plan, monkeypatch):
    from beast.blender_runner import atomic_json
    output = tmp_path / "run"

    def fake(command, **kwargs):
        if command[-2] == "build":
            (output / "scene.blend").write_bytes(b"test fixture, not Blender")
        else:
            atomic_json(output / "measurement.json", {"version":"5.1.2", "objects":{"Base":[]}})
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake)
    result = execute(plan, output, sys.executable, allow_execute=True)
    assert result["status"] == "failed"
    assert "object measurement" in result["error"]
    assert read_json(output / "receipt.json")["status"] == "failed"


@pytest.mark.skipif(not os.environ.get("BEAST_TEST_BLENDER"), reason="explicit real CPU Blender opt-in required")
def test_live_blender_saved_artifact(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/blender_execute.py"),
                             str(ROOT / "examples/blender/blockout.json"), "--output", str(tmp_path / "live"),
                             "--blender", os.environ["BEAST_TEST_BLENDER"], "--allow-execute"],
                            capture_output=True, text=True, timeout=270)
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = read_json(tmp_path / "live/receipt.json")
    assert receipt["ok"] and all(receipt["gates"].values())
    assert len(receipt["processes"]) == 2
    assert receipt["source_claim"] == "owner_authored"
