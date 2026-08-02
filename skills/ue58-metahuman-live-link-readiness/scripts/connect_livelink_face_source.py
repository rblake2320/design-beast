"""Create the UE 5.8 Live Link Face source and connect it to an iOS device."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import require_context, write_receipt

MARKER = "BEAST_LIVELINK_FACE_SOURCE="


def main() -> dict:
    context = require_context()
    address = os.environ.get("BEAST_LIVE_LINK_FACE_ADDRESS", "").strip()
    subject_name = os.environ.get("BEAST_LIVE_LINK_SUBJECT", "me").strip()
    port = int(os.environ.get("BEAST_LIVE_LINK_FACE_PORT", "14785"))
    if not address:
        raise RuntimeError("BEAST_LIVE_LINK_FACE_ADDRESS is required")
    if not subject_name:
        raise RuntimeError("BEAST_LIVE_LINK_SUBJECT is required")
    if not 1 <= port <= 65535:
        raise RuntimeError(f"Invalid Live Link Face port: {port}")

    response = unreal.BeastEvidenceCollectorLibrary.connect_live_link_face_source(
        subject_name,
        address,
        port,
    )
    # UE's generated Python wrapper exposes only the FString out parameter for
    # this bool-returning UFUNCTION. Empty OutError means the native call passed.
    error = str(response or "")
    connected = not error
    if not connected:
        raise RuntimeError(
            "UE 5.8 native Live Link Face bridge failed: "
            + json.dumps(
                {
                    "address": address,
                    "port": port,
                    "subject": subject_name,
                    "error": str(error),
                },
                sort_keys=True,
            )
        )

    result = {
        "state": "SOURCE_CONNECT_REQUESTED",
        "project": context["project"],
        "run_id": context["run_id"],
        "subject": subject_name,
        "address": address,
        "port": port,
        "native_bridge": True,
        "connect_accepted": True,
        "animation_confirmed": False,
    }
    unreal.log(MARKER + json.dumps(result, sort_keys=True))
    write_receipt(context, "livelink-face-source", result)
    return result


if __name__ == "__main__":
    main()
