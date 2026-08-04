"""Execute and measure the held-out Inkscape metaballs typed state."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import deque
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

SVG = "http://www.w3.org/2000/svg"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def values(state: dict) -> dict[str, object]:
    if state.get("status") != "answered":
        raise ValueError("typed state is incomplete; execution is forbidden")
    return {row["name"]: row["value"] for row in state["values"]}


def matrix(data: dict[str, object]) -> list[float]:
    result = [float(data[f"a{row}{column}"])
              for row in range(4) for column in range(5)]
    if len(result) != 20:
        raise ValueError("feColorMatrix requires exactly 20 values")
    return result


def build_svg(data: dict[str, object], *, filtered: bool,
              center_distance: float | None = None) -> str:
    required_order = ["feGaussianBlur", "feColorMatrix", "feColorMatrix"]
    actual_order = [data["primitive_1"], data["primitive_2"], data["primitive_3"]]
    if actual_order != required_order or data["color_matrix_type"] != "matrix":
        raise ValueError(f"unsupported primitive contract: {actual_order}")
    if (data["object_count"] != 2 or data["shape_kind"] != "circle" or
            data["layout_axis"] != "horizontal" or data["grouped"] is not True):
        raise ValueError("unsupported source-geometry contract")
    diameter = float(data["circle_diameter"])
    group_width = float(data["initial_group_width"])
    group_height = float(data["initial_group_height"])
    if abs(group_height - diameter) > 0.001 or group_width <= 2 * diameter:
        raise ValueError("source geometry is inconsistent with two separated circles")
    if (data["spacing_strategy"] != "move_closer" or
            data["success_condition"] != "single_connected_component"):
        raise ValueError("unsupported feedback strategy")
    radius = diameter / 2
    if center_distance is None:
        center_distance = group_width - diameter
    if center_distance <= 0 or center_distance > group_width - diameter:
        raise ValueError("center distance must move inward from the evidenced start")
    left_x, right_x = 400 - center_distance / 2, 400 + center_distance / 2
    numbers = " ".join(f"{value:g}" for value in matrix(data))
    definitions = ""
    style = ""
    if filtered:
        definitions = (
            '<defs><filter id="metaball" x="-50%" y="-50%" width="200%" height="200%" '
            'color-interpolation-filters="sRGB">'
            f'<feGaussianBlur stdDeviation="{float(data["std_deviation_x"]):g} '
            f'{float(data["std_deviation_y"]):g}" result="blur"/>'
            f'<feColorMatrix in="blur" type="matrix" values="{numbers}" result="threshold1"/>'
            f'<feColorMatrix in="threshold1" type="matrix" values="{numbers}" result="threshold2"/>'
            '</filter></defs>'
        )
        style = ' filter="url(#metaball)"'
    return (
        f'<svg xmlns="{SVG}" width="800" height="480" viewBox="0 0 800 480">'
        f'{definitions}<g{style} fill="#ff2688">'
        f'<circle cx="{left_x:g}" cy="240" r="{radius:g}"/>'
        f'<circle cx="{right_x:g}" cy="240" r="{radius:g}"/>'
        '</g></svg>\n'
    )


def render(inkscape: Path, svg: Path, png: Path) -> None:
    subprocess.run([str(inkscape), str(svg), "--export-type=png",
                    f"--export-filename={png}"], check=True,
                   capture_output=True, text=True, timeout=120)


def connected_components(image: Image.Image, threshold: int = 128) -> int:
    alpha = image.convert("RGBA").getchannel("A")
    width, height = alpha.size
    foreground = {(x, y) for y in range(height) for x in range(width)
                  if alpha.getpixel((x, y)) >= threshold}
    count = 0
    while foreground:
        count += 1
        start = foreground.pop()
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in foreground:
                    foreground.remove(neighbor)
                    queue.append(neighbor)
    return count


def inspect_svg(path: Path) -> dict[str, object]:
    root = ET.parse(path).getroot()
    blur = root.findall(f".//{{{SVG}}}feGaussianBlur")
    matrices = root.findall(f".//{{{SVG}}}feColorMatrix")
    return {
        "primitive_order": [element.tag.rsplit("}", 1)[-1]
                            for element in list(root.find(f".//{{{SVG}}}filter"))],
        "std_deviation": blur[0].attrib["stdDeviation"] if len(blur) == 1 else None,
        "matrix_count": len(matrices),
        "matrix_values_equal": len(matrices) == 2 and
                               matrices[0].attrib.get("values") == matrices[1].attrib.get("values"),
        "matrix_value_count": len(matrices[0].attrib.get("values", "").split())
                              if matrices else 0,
    }


def main(state_path: Path, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    data = values(state)
    control_svg, filtered_svg = out / "control.svg", out / "metaballs.svg"
    control_png, filtered_png = out / "control.png", out / "metaballs.png"
    control_svg.write_text(build_svg(data, filtered=False), encoding="utf-8")
    inkscape = Path(r"C:\Program Files\Inkscape\bin\inkscape.exe")
    render(inkscape, control_svg, control_png)
    diameter = float(data["circle_diameter"])
    initial_distance = float(data["initial_group_width"]) - diameter
    search = []
    selected: tuple[Path, Path, float] | None = None
    for index in range(11):
        distance = max(diameter * 0.5, initial_distance - index * diameter * 0.1)
        candidate_svg = out / f"search-{index:02d}.svg"
        candidate_png = out / f"search-{index:02d}.png"
        candidate_svg.write_text(
            build_svg(data, filtered=True, center_distance=distance), encoding="utf-8")
        render(inkscape, candidate_svg, candidate_png)
        with Image.open(candidate_png) as candidate:
            candidate.load()
            components = connected_components(candidate)
            center_alpha = candidate.convert("RGBA").getpixel((400, 240))[3]
        search.append({"index": index, "center_distance": distance,
                       "components": components, "center_alpha": center_alpha,
                       "svg_sha256": sha256(candidate_svg),
                       "png_sha256": sha256(candidate_png)})
        if components == 1 and center_alpha >= 250:
            selected = candidate_svg, candidate_png, distance
            break
    if selected is None:
        filtered_svg.write_text(candidate_svg.read_text(encoding="utf-8"),
                                encoding="utf-8")
        filtered_png.write_bytes(candidate_png.read_bytes())
    else:
        chosen_svg, chosen_png, _ = selected
        filtered_svg.write_text(chosen_svg.read_text(encoding="utf-8"), encoding="utf-8")
        filtered_png.write_bytes(chosen_png.read_bytes())
    structure = inspect_svg(filtered_svg)
    with Image.open(control_png) as control, Image.open(filtered_png) as filtered:
        control.load(), filtered.load()
        center = (400, 240)
        measured = {
            "control_components": connected_components(control),
            "filtered_components": connected_components(filtered),
            "control_center_alpha": control.convert("RGBA").getpixel(center)[3],
            "filtered_center_alpha": filtered.convert("RGBA").getpixel(center)[3],
            "width": filtered.width, "height": filtered.height,
            "selected_center_distance": selected[2] if selected else None,
        }
    gates = {
        "typed_state_answered": state["status"] == "answered",
        "primitive_order_exact": structure["primitive_order"] ==
                                 ["feGaussianBlur", "feColorMatrix", "feColorMatrix"],
        "blur_exact": structure["std_deviation"] == "34.79 34.79",
        "two_identical_20_value_matrices": structure["matrix_count"] == 2 and
                                           structure["matrix_values_equal"] and
                                           structure["matrix_value_count"] == 20,
        "control_is_two_objects": measured["control_components"] == 2,
        "filter_fuses_to_one_object": measured["filtered_components"] == 1,
        "gap_changes_from_empty_to_filled": measured["control_center_alpha"] == 0 and
                                            measured["filtered_center_alpha"] >= 250,
        "render_size_exact": measured["width"] == 800 and measured["height"] == 480,
    }
    receipt = {
        "schema": "beast.heldout.metaballs-execution/v1",
        "ok": all(gates.values()),
        "typed_state_fingerprint": state["compilation_fingerprint"],
        "inkscape_version": subprocess.run(
            [str(inkscape), "--version"], capture_output=True, text=True,
            check=True).stdout.strip(),
        "structure": structure, "search": search,
        "measured": measured, "gates": gates,
        "artifacts": {path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
                      for path in (control_svg, filtered_svg, control_png, filtered_png)},
    }
    (out / "execution-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
