"""Git's platform newline conversion must not rewrite hash-bound evidence."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_committed_pixel_state_bytes_match_recorded_hashes():
    report = json.loads((ROOT / "proofs/watch-pixel-state/blender-02/report.json").read_text())
    for index, row in enumerate(report["frames"]):
        relative = f"proofs/watch-pixel-state/blender-02/frame-{index:03d}/state.json"
        blob = subprocess.run(["git", "show", f"HEAD:{relative}"], cwd=ROOT,
                              check=True, capture_output=True).stdout
        assert hashlib.sha256(blob).hexdigest() == row["state_sha256"], relative
