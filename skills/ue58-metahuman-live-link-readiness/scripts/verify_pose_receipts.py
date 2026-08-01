"""Verify three collector-issued pose receipts without accepting manual curve values."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import statistics
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_rmse(left: Image.Image, right: Image.Image) -> float:
    if left.size != right.size:
        raise ValueError(f"Image sizes differ: {left.size} != {right.size}")
    stat = ImageStat.Stat(ImageChops.difference(left.convert("L"), right.convert("L")))
    return (stat.mean[0] ** 2 + stat.var[0]) ** 0.5 / 255.0


def load_receipt(path: Path) -> tuple[dict, Image.Image]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("state") != "POSE_CAPTURED":
        raise ValueError(f"Not a collector pose receipt: {path}")
    if not str(data.get("engine_version", "")).startswith("5.8"):
        raise ValueError(f"Receipt was not captured in UE 5.8: {path}")
    run_id = str(data.get("run_id", ""))
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,40}", run_id):
        raise ValueError(f"Receipt has no valid run identity: {path}")
    if path.resolve().parent.parent.name != run_id:
        raise ValueError(f"Receipt path does not match its run identity: {path}")
    actor = data.get("actor")
    if not isinstance(actor, dict) or not actor.get("path"):
        raise ValueError(f"Receipt has no bound actor identity: {path}")
    requested = int(data.get("requested_samples", 0))
    samples = data.get("samples", [])
    if requested < 5 or len(samples) != requested:
        raise ValueError(f"Incomplete sample burst in {path}")
    platform_times = [float(item["platform_seconds"]) for item in samples]
    source_times = [float(item["source_world_seconds"]) for item in samples]
    if platform_times != sorted(platform_times) or source_times != sorted(source_times):
        raise ValueError(f"Non-monotonic sample timestamps in {path}")
    image_meta = data["image"]
    image_path = Path(image_meta["path"]).resolve()
    if image_path.parent != path.resolve().parent:
        raise ValueError(f"Image escaped the receipt directory: {image_path}")
    if not image_path.is_file() or sha256_file(image_path) != image_meta.get("sha256", "").lower():
        raise ValueError(f"Image hash mismatch: {image_path}")
    image = Image.open(image_path).convert("RGB")
    if list(image.size) != [int(image_meta["width"]), int(image_meta["height"])]:
        raise ValueError(f"Image dimensions disagree with receipt: {image_path}")
    return data, image


def verify(
    neutral_a_path: Path,
    neutral_b_path: Path,
    expression_path: Path,
    crop: tuple[int, int, int, int],
) -> dict:
    loaded = [load_receipt(path) for path in (neutral_a_path, neutral_b_path, expression_path)]
    receipts = [item[0] for item in loaded]
    images = [item[1] for item in loaded]
    identity_fields = (
        "engine_version",
        "project",
        "run_id",
        "subject",
        "curve",
        "editor_view",
        "actor",
    )
    for field in identity_fields:
        if any(receipt.get(field) != receipts[0].get(field) for receipt in receipts[1:]):
            raise ValueError(f"Capture identity changed across poses: {field}")
    labels = [receipt.get("capture_label") for receipt in receipts]
    if labels != ["neutral-a", "neutral-b", "expression"]:
        raise ValueError(f"Expected neutral-a, neutral-b, expression receipts; got {labels}")

    left, top, width, height = crop
    if min(left, top) < 0 or min(width, height) < 32:
        raise ValueError("Crop must be a positive face region of at least 32x32")
    right, bottom = left + width, top + height
    if any(right > image.width or bottom > image.height for image in images):
        raise ValueError("Crop extends outside a captured frame")
    crops = [image.crop((left, top, right, bottom)) for image in images]

    neutral_a_values = [float(item["value"]) for item in receipts[0]["samples"]]
    neutral_b_values = [float(item["value"]) for item in receipts[1]["samples"]]
    expression_values = [float(item["value"]) for item in receipts[2]["samples"]]
    neutral_median = statistics.median(neutral_a_values + neutral_b_values)
    expression_median = statistics.median(expression_values)
    curve_delta = abs(expression_median - neutral_median)
    continuity = max(
        (sum(1 for _ in group) for passes, group in itertools.groupby(
            abs(value - neutral_median) >= 0.20 for value in expression_values
        ) if passes),
        default=0,
    )
    neutral_rmse = normalized_rmse(crops[0], crops[1])
    expression_rmse = normalized_rmse(crops[0], crops[2])
    render_threshold = max(0.03, 5.0 * neutral_rmse)
    gates = {
        "source_delta": curve_delta >= 0.20,
        "continuity": continuity >= 3,
        "neutral_stability": neutral_rmse <= 0.01,
        "rendered_deformation": expression_rmse >= render_threshold,
    }
    return {
        "schema": 1,
        "state": "DEFORMATION_MEASURED" if all(gates.values()) else "MEASUREMENT_REJECTED",
        "promotion_allowed": False,
        "pending_gate": "visual-region review tied to the three image hashes",
        "identity": {field: receipts[0][field] for field in identity_fields},
        "source_receipts": [
            {"path": str(path.resolve()), "sha256": sha256_file(path.resolve())}
            for path in (neutral_a_path, neutral_b_path, expression_path)
        ],
        "source_images": [receipt["image"] for receipt in receipts],
        "crop": {"left": left, "top": top, "width": width, "height": height},
        "metrics": {
            "neutral_curve_median": neutral_median,
            "expression_curve_median": expression_median,
            "curve_delta": curve_delta,
            "continuity_samples": continuity,
            "neutral_rmse": neutral_rmse,
            "expression_rmse": expression_rmse,
            "render_threshold": render_threshold,
        },
        "gates": gates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("neutral_a", type=Path)
    parser.add_argument("neutral_b", type=Path)
    parser.add_argument("expression", type=Path)
    parser.add_argument("--crop", nargs=4, type=int, metavar=("LEFT", "TOP", "WIDTH", "HEIGHT"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.neutral_a, args.neutral_b, args.expression, tuple(args.crop))
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["state"] == "DEFORMATION_MEASURED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
