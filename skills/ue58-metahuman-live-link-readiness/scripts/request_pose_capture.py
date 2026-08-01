"""Request one collector-issued Live Link curve and viewport pose receipt."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import require_context

MARKER = "BEAST_POSE_CAPTURE_REQUESTED="


def main() -> dict:
    context = require_context()
    label = os.environ.get("BEAST_CAPTURE_LABEL", "").strip()
    if label not in {"neutral-a", "neutral-b", "expression"}:
        raise RuntimeError("BEAST_CAPTURE_LABEL must be neutral-a, neutral-b, or expression")
    subject = os.environ.get("BEAST_LIVE_LINK_SUBJECT", "me").strip()
    curve = os.environ.get("BEAST_LIVE_LINK_CURVE", "jawOpen").strip()
    samples = int(os.environ.get("BEAST_CAPTURE_SAMPLES", "10"))
    interval = float(os.environ.get("BEAST_CAPTURE_INTERVAL", "0.05"))
    output = os.path.join(context["receipt_dir"], "deformation")
    accepted = unreal.BeastEvidenceCollectorLibrary.request_pose_capture(
        subject,
        curve,
        output,
        label,
        samples,
        interval,
    )
    if not accepted:
        raise RuntimeError(
            "Collector rejected capture: "
            + unreal.BeastEvidenceCollectorLibrary.get_last_error()
        )
    result = {
        "state": "POSE_CAPTURE_REQUESTED",
        "project": context["project"],
        "run_id": context["run_id"],
        "label": label,
        "subject": subject,
        "curve": curve,
        "samples": samples,
        "interval": interval,
        "output": output,
    }
    unreal.log(MARKER + json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
