"""Read the native evidence collector status without changing it."""

from __future__ import annotations

import json
import unreal


def main() -> dict:
    result = {
        "pending": bool(unreal.BeastEvidenceCollectorLibrary.is_capture_pending()),
        "receipt": unreal.BeastEvidenceCollectorLibrary.get_last_receipt_path(),
        "error": unreal.BeastEvidenceCollectorLibrary.get_last_error(),
    }
    unreal.log("BEAST_POSE_CAPTURE_STATUS=" + json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
