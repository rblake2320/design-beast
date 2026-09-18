"""Closed, data-only Blender action contract. No eval, scripts or input .blend files."""
from __future__ import annotations

import copy
import math
import re

SCHEMA = "beast.blender.procedure/v1"
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,47}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, required, optional=()):
    require(isinstance(value, dict), "expected an object")
    require(set(required) <= set(value) <= set(required) | set(optional),
            f"expected keys {sorted(required)}, optional {sorted(optional)}")


def number(value, low, high):
    require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
            f"expected finite number in {low}..{high}")


def vector(value, count, low, high):
    require(isinstance(value, list) and len(value) == count, f"expected {count}-vector")
    for item in value:
        number(item, low, high)


def validate(plan):
    keys(plan, {"schema", "id", "blender_version", "steps"})
    require(plan["schema"] == SCHEMA, "unsupported Blender procedure schema")
    require(isinstance(plan["id"], str) and NAME.fullmatch(plan["id"]), "invalid procedure id")
    require(isinstance(plan["blender_version"], str) and
            re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", plan["blender_version"]),
            "blender_version must be exact major.minor.patch")
    steps = plan["steps"]
    require(isinstance(steps, list) and 1 <= len(steps) <= 128, "expected 1..128 steps")
    objects, ids = {}, set()
    for step in steps:
        require(isinstance(step, dict), "step must be an object")
        action = step.get("action")
        extra = {"add_mesh": {"primitive"}, "transform": {"location", "rotation_deg", "scale"},
                 "material": {"rgba", "roughness", "metallic"},
                 "bend": {"axis", "angle_deg"}}
        require(isinstance(action, str) and action in extra, "unsupported action")
        keys(step, {"id", "action", "object"} | extra[action])
        sid, name = step["id"], step["object"]
        require(isinstance(sid, str) and NAME.fullmatch(sid) and sid not in ids,
                "invalid or duplicate step id")
        require(isinstance(name, str) and NAME.fullmatch(name), "invalid object name")
        ids.add(sid)
        if action == "add_mesh":
            require(name not in objects, "object already exists")
            require(isinstance(step["primitive"], str) and
                    step["primitive"] in {"cube", "uv_sphere", "grid"}, "unsupported primitive")
            objects[name] = {"primitive": step["primitive"], "location": [0, 0, 0],
                             "rotation_deg": [0, 0, 0], "scale": [1, 1, 1],
                             "material": None, "bend": None}
        else:
            require(name in objects, "target must be created by an earlier step")
            if action == "transform":
                vector(step["location"], 3, -100, 100)
                vector(step["rotation_deg"], 3, -360, 360)
                vector(step["scale"], 3, 0.001, 100)
                objects[name].update({k: step[k] for k in ("location", "rotation_deg", "scale")})
            elif action == "material":
                vector(step["rgba"], 4, 0, 1)
                require(step["rgba"][3] == 1, "v1 supports opaque materials only")
                number(step["roughness"], 0, 1)
                number(step["metallic"], 0, 1)
                objects[name]["material"] = {k: step[k] for k in ("rgba", "roughness", "metallic")}
            elif action == "bend":
                require(isinstance(step["axis"], str) and step["axis"] in {"X", "Y", "Z"},
                        "bend axis must be X, Y or Z")
                number(step["angle_deg"], -180, 180)
                require(step["angle_deg"] == 0 or abs(step["angle_deg"]) >= 0.1,
                        "nonzero bend must be at least 0.1 degrees")
                require(objects[name]["bend"] is None, "only one bend per object")
                objects[name]["bend"] = {"axis": step["axis"], "angle_deg": step["angle_deg"]}
    require(len(objects) <= 32, "at most 32 meshes")
    return copy.deepcopy(objects)


def bind_fields(template, state):
    """Bind only values recompiled by Watch; do not accept loose model 'answers'."""
    require(isinstance(state, dict) and state.get("schema") == "beast.watch.typed-state/v1"
            and state.get("status") == "answered" and not state.get("errors")
            and not state.get("unresolved"), "typed evidence is unresolved")
    require(state.get("application", "").casefold() == "blender", "target is not Blender")
    require(state.get("version") == template.get("blender_version"), "target version mismatch")
    values = {row["name"]: row["value"] for row in state["values"]}
    used = set()

    def bind(value):
        if isinstance(value, dict):
            if "field" in value:
                require(set(value) == {"field"} and isinstance(value["field"], str)
                        and value["field"] in values, "unknown or malformed field binding")
                used.add(value["field"])
                return values[value["field"]]
            return {k: bind(v) for k, v in value.items()}
        if isinstance(value, list):
            return [bind(v) for v in value]
        return value

    result = bind(template)
    require(bool(used), "typed template must consume at least one evidenced field")
    validate(result)
    return result, sorted(used)
