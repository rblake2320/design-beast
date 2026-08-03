"""Build, render, and measure the silent-tutorial SVG benchmark."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image


def load(path: Path) -> dict[str, object]:
    answer = json.loads(path.read_text(encoding="utf-8"))
    if answer["status"] != "answered":
        raise ValueError("answer is incomplete; no SVG artifact may be built")
    data = {item["name"]: item["value"] for item in answer["values"]}
    required = {"spread_method"}
    for index in range(5):
        required |= {f"stop{index}_offset", f"stop{index}_rgba"}
    missing = sorted(required - data.keys())
    if missing:
        raise ValueError(f"missing values: {missing}")
    return data


def main(answer: Path, svg: Path, png: Path, receipt: Path) -> None:
    data = load(answer)
    spread = str(data["spread_method"]).lower()
    if spread == "direct":
        spread = "repeat"
    stops = []
    for index in range(5):
        rgba = str(data[f"stop{index}_rgba"]).lower().lstrip("#")
        if len(rgba) != 8:
            raise ValueError(f"invalid RGBA: {rgba}")
        offset = float(data[f"stop{index}_offset"])
        stops.append(
            f'<stop offset="{offset:.2f}" stop-color="#{rgba[:6]}" '
            f'stop-opacity="{int(rgba[6:], 16) / 255:.6f}"/>'
        )
    payload = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="640" '
        'viewBox="0 0 640 640"><defs>'
        f'<radialGradient id="g" cx="50%" cy="50%" r="12%" spreadMethod="{spread}">'
        + "".join(stops)
        + '</radialGradient></defs><rect width="640" height="640" fill="url(#g)"/></svg>\n'
    )
    svg.parent.mkdir(parents=True, exist_ok=True)
    svg.write_text(payload, encoding="utf-8")
    inkscape = Path(r"C:\Program Files\Inkscape\bin\inkscape.exe")
    subprocess.run([str(inkscape), str(svg), "--export-type=png",
                    f"--export-filename={png}"], check=True, capture_output=True)
    ET.parse(svg)
    with Image.open(png) as image:
        image.load()
        row = [image.convert("RGB").getpixel((x, image.height // 2)) for x in range(image.width)]
    transitions = sum(
        1 for left, right in zip(row, row[1:])
        if sum(abs(a - b) for a, b in zip(left, right)) > 24
    )
    report = {
        "svg": str(svg), "png": str(png), "opens": True,
        "spread_method": spread, "stops": 5,
        "width": 640, "height": 640, "row_color_transitions": transitions,
    }
    receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(*(Path(value) for value in sys.argv[1:5]))
