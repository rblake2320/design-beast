import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CLI = REPO / "scripts" / "evidence_intake.py"


def _run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed Python executable and repo CLI
        [sys.executable, str(CLI), *(str(arg) for arg in args)],
        cwd=REPO,
        text=True,
        capture_output=True,
        timeout=30,
    )


def test_cli_admit_timeline_receipt_and_compile(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    manifest = tmp_path / "manifest.json"
    admitted = _run(
        "admit", source, manifest,
        "--status", "owned",
        "--approved-by", "user:owner",
        "--basis", "test fixture owner",
        "--allow-use", "evidence_analysis",
        "--allow-use", "procedure_learning",
        "--approved-at", "2026-08-04T21:00:00Z",
    )
    assert admitted.returncode == 0, admitted.stderr

    bundle = tmp_path / "watch"
    frame_dir = bundle / "frames"
    frame_dir.mkdir(parents=True)
    frame = frame_dir / "f.jpg"
    frame.write_bytes(b"pixels")
    phash = "0123456789abcdef"
    timeline = {
        "schema": "beast.watch.timeline/v3",
        "source": {"sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        "sampling": {"strategy": "fixture"},
        "frames": [{
            "id": "frame-0001", "file": "frames/f.jpg",
            "source_seconds": 1.0, "perceptual_hash": phash,
            "sha256": hashlib.sha256(frame.read_bytes()).hexdigest(),
        }],
        "transcript": {"method": "none", "segments": []},
        "bundle_fingerprint": hashlib.sha256(f"1.0:{phash}".encode()).hexdigest(),
    }
    timeline_path = bundle / "timeline.json"
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
    events_path = tmp_path / "events.json"
    converted = _run("timeline-events", manifest, timeline_path, events_path)
    assert converted.returncode == 0, converted.stderr
    event_id = json.loads(events_path.read_text(encoding="utf-8"))["events"][0]["event_id"]

    claim_path = tmp_path / "claim.json"
    claimed = _run(
        "claim", claim_path,
        "--description", "Render the retained frame result",
        "--event-id", event_id,
        "--state", "verified_by_execution",
        "--execution-receipt-id", "receipt-cli",
    )
    assert claimed.returncode == 0, claimed.stderr
    claim_id = json.loads(claim_path.read_text(encoding="utf-8"))["claim_id"]

    result = tmp_path / "result.txt"
    result.write_text("measured=true", encoding="utf-8")
    spec = tmp_path / "receipt-spec.json"
    spec.write_text(json.dumps({
        "receipt_id": "receipt-cli",
        "claim_ids": [claim_id],
        "success": True,
        "environment_fingerprint": "e" * 64,
        "executed_at": "2026-08-04T21:01:00Z",
        "artifact_base": ".",
        "artifacts": [{"label": "result", "path": "result.txt"}],
        "checks": [{"name": "result", "passed": True,
                    "evidence": "fixture readback matched"}],
    }), encoding="utf-8")
    receipt_path = tmp_path / "receipt.json"
    receipted = _run("receipt", spec, receipt_path)
    assert receipted.returncode == 0, receipted.stderr

    compiled_path = tmp_path / "bundle.json"
    compiled = _run(
        "compile", manifest, events_path, claim_path, receipt_path, compiled_path,
        "--artifact-root", tmp_path,
    )
    assert compiled.returncode == 0, compiled.stderr
    assert json.loads(compiled_path.read_text(encoding="utf-8"))["gates"][
        "promotion_allowed"] is True


def test_google_vision_cli_fails_before_network_without_explicit_flag(tmp_path):
    image = tmp_path / "image.jpg"
    image.write_bytes(b"image")
    manifest_path = tmp_path / "manifest.json"
    admitted = _run(
        "admit", image, manifest_path,
        "--status", "owned", "--approved-by", "user:owner",
        "--basis", "owner supplied", "--allow-use", "cloud_analysis",
        "--approved-at", "2026-08-04T21:00:00Z",
    )
    assert admitted.returncode == 0

    # A parent event fixture is intentionally omitted: explicit cloud
    # authorization fails before any request can be attempted.
    parent = tmp_path / "parent.json"
    parent.write_text("{}", encoding="utf-8")
    output = tmp_path / "cloud.json"
    denied = _run("google-vision", manifest_path, parent, image, output)
    assert denied.returncode == 2
    assert "explicit authorization" in denied.stderr
    assert not output.exists()
