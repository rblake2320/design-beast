"""Export bounded review frames and custody metadata, never source media/audio."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import retain


def main():
    for name in ("dense-repair-01", "heldout-repair-01"):
        bundle = Path("watched") / name
        output = Path("proofs/watch-repair/inputs") / name
        output.mkdir(parents=True, exist_ok=False)
        timeline = json.loads((bundle / "timeline.json").read_text(encoding="utf-8"))
        if len(timeline["frames"]) != 61:
            raise ValueError("unexpected frame count")
        (output / "frames").mkdir()
        for row in timeline["frames"]:
            source = (bundle / row["file"]).resolve()
            if not source.is_relative_to(bundle.resolve()):
                raise ValueError("frame escapes bundle")
            pixels = source.read_bytes()
            if hashlib.sha256(pixels).hexdigest() != row["sha256"]:
                raise ValueError("frame custody mismatch")
            destination = output / "frames" / source.name
            with destination.open("xb") as stream:
                stream.write(pixels)
        for filename in ("timeline.json", "source.json", "inspection.json", "inspection.result.json"):
            shutil.copyfile(bundle / filename, output / filename)
        retain(output / "export.json", {"source_bundle": name, "frames": 61,
            "source_media_included": False, "audio_included": False, "transcript_included": False,
            "purpose": "bounded independent visual verification of repair claims"})
    print("Exported 122 review frames, no source video or transcript.")


if __name__ == "__main__":
    main()
