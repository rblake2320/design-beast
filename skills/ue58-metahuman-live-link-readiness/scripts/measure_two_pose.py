"""Evaluate the numerical two-pose promotion gate on aligned face crops."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def normalized_rmse(left: Path, right: Path) -> float:
    first = Image.open(left).convert("L")
    second = Image.open(right).convert("L")
    if first.size != second.size:
        raise ValueError(f"Image sizes differ: {first.size} != {second.size}")
    stat = ImageStat.Stat(ImageChops.difference(first, second))
    return math.sqrt(stat.mean[0] ** 2 + stat.var[0]) / 255.0


def evaluate(
    neutral_noise: float,
    expression_rmse: float,
    curve_neutral: float,
    curve_expression: float,
    continuity_passes: int,
    visual_validity_confirmed: bool,
) -> dict:
    curve_delta = abs(curve_expression - curve_neutral)
    render_threshold = max(0.03, 5.0 * neutral_noise)
    gates = {
        "source_delta": curve_delta >= 0.20,
        "continuity": continuity_passes >= 3,
        "neutral_stability": neutral_noise <= 0.01,
        "rendered_deformation": expression_rmse >= render_threshold,
        "visual_validity": visual_validity_confirmed,
    }
    return {
        "state": "DEFORMATION_CANDIDATE" if all(gates.values()) else "METRICS_REJECTED",
        "passed_metrics": all(gates.values()),
        "promotion_allowed": False,
        "reason": "Raw UE Live Link sampling and capture-provenance collector is not yet implemented",
        "metrics": {
            "neutral_rmse": neutral_noise,
            "expression_rmse": expression_rmse,
            "render_threshold": render_threshold,
            "curve_neutral": curve_neutral,
            "curve_expression": curve_expression,
            "curve_delta": curve_delta,
            "continuity_passes_of_five": continuity_passes,
        },
        "gates": gates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("neutral_a", type=Path)
    parser.add_argument("neutral_b", type=Path)
    parser.add_argument("expression", type=Path)
    parser.add_argument("--curve-neutral", type=float, required=True)
    parser.add_argument("--curve-expression", type=float, required=True)
    parser.add_argument("--continuity-passes", type=int, choices=range(0, 6), required=True)
    parser.add_argument(
        "--visual-validity-confirmed",
        action="store_true",
        help="Confirm reviewed changes are facial deformation, not camera/UI/lighting motion",
    )
    args = parser.parse_args()
    neutral_noise = normalized_rmse(args.neutral_a, args.neutral_b)
    expression_rmse = normalized_rmse(args.neutral_a, args.expression)
    result = evaluate(
        neutral_noise,
        expression_rmse,
        args.curve_neutral,
        args.curve_expression,
        args.continuity_passes,
        args.visual_validity_confirmed,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 3 if result["passed_metrics"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
