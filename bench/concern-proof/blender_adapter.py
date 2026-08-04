"""Build or verify the benchmark Blender artifact from an agent answer."""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import bpy


def scalar(value):
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value))
    if not match:
        raise ValueError(f"not numeric: {value!r}")
    return float(match.group())


def values(path: Path) -> dict[str, object]:
    answer = json.loads(path.read_text(encoding="utf-8"))
    if answer["status"] != "answered":
        raise ValueError("answer abstained; no artifact may be built")
    return {item["name"]: item["value"] for item in answer["values"]}


def first(data: dict[str, object], *names: str):
    for name in names:
        if name in data:
            return data[name]
    raise KeyError(names[0])


def build(answer: Path, output: Path) -> None:
    data = values(answer)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=33, y_subdivisions=3, size=2)
    flute = bpy.context.object
    flute.name = "BenchmarkFlute"
    flute.location = tuple(scalar(first(data, f"location_{axis}")) for axis in "xyz")
    flute.rotation_euler = tuple(
        math.radians(scalar(first(data, f"rotation_{axis}", f"rotation_{axis}_deg")))
        for axis in "xyz"
    )
    flute.scale = tuple(scalar(first(data, f"scale_{axis}")) for axis in "xyz")

    bpy.ops.object.empty_add(type="SPHERE", location=flute.location)
    origin = bpy.context.object
    origin.name = "BendOrigin"
    origin.rotation_euler = flute.rotation_euler

    modifier = flute.modifiers.new("TutorialBend", "SIMPLE_DEFORM")
    modifier.deform_method = "BEND"
    modifier.deform_axis = str(first(data, "bend_axis")).strip().upper()[-1]
    modifier.angle = math.radians(scalar(first(data, "bend_angle_deg")))
    modifier.origin = origin
    bpy.context.view_layer.objects.active = flute
    flute.select_set(True)
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))


def verify(path: Path, receipt: Path) -> None:
    bpy.ops.wm.open_mainfile(filepath=str(path))
    flute = bpy.data.objects["BenchmarkFlute"]
    modifier = flute.modifiers["TutorialBend"]
    report = {
        "artifact": str(path),
        "opens": True,
        "location": list(flute.location),
        "rotation_deg": [math.degrees(value) for value in flute.rotation_euler],
        "scale": list(flute.scale),
        "bend_axis": modifier.deform_axis,
        "bend_angle_deg": math.degrees(modifier.angle),
        "origin": modifier.origin.name if modifier.origin else None,
        "evaluated_vertices": len(flute.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices),
    }
    receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    mode, source, output = sys.argv[sys.argv.index("--") + 1:]
    if mode == "build":
        build(Path(source), Path(output))
    elif mode == "verify":
        verify(Path(source), Path(output))
    else:
        raise ValueError(mode)
