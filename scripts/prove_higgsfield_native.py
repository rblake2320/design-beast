"""One explicitly authorized native job, then real Studio upload. No implicit retries."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))
from higgsfield_cli import generate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-paid-proof", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    destination = ROOT / "proofs/higgsfield-native"
    if args.verify_only:
        receipt = json.loads((destination / "native-refinement.png.higgsfield.json").read_text())
        output = destination / "native-refinement.png"
        local_hash = hashlib.sha256(output.read_bytes()).hexdigest()
        if not receipt["ok"] or receipt["status"] != "completed" or receipt["transport"] != "native_cli":
            raise ValueError("native completion receipt required")
        if local_hash != receipt["artifact_sha256"]:
            raise ValueError("native artifact checksum mismatch")
        uploaded = json.loads((destination / "studio-upload.json").read_text())["file"]
        if Path(uploaded).name != uploaded or not uploaded.endswith(".png"):
            raise ValueError("invalid Studio filename")
        with urllib.request.urlopen("http://127.0.0.1:8787/uploads/" + uploaded, timeout=30) as response:
            imported_hash = hashlib.sha256(response.read(128 * 1024 * 1024)).hexdigest()
        if imported_hash != local_hash:
            raise ValueError("live Studio artifact differs from native output")
        print(json.dumps({"ok": True, "native_job": receipt["job_id"],
                          "sha256": local_hash, "live_studio_bytes_match": True}))
        return 0
    if not args.allow_paid_proof:
        parser.error("requires explicit --allow-paid-proof after cost preflight")
    destination.mkdir(exist_ok=True)
    output = destination / "native-refinement.png"
    result = generate("nano_banana_2",
                      "Preserve the reference composition and improve only the fine ceramic surface texture.",
                      output, ["--image", "2b1029a0-de52-45a1-ad46-4b160c8cc1fd",
                               "--resolution", "4k", "--aspect_ratio", "16:9"])
    print(json.dumps(result), flush=True)
    if "error" in result:
        return 1
    payload = json.dumps({"name": output.name,
                          "data": base64.b64encode(output.read_bytes()).decode("ascii")}).encode()
    request = urllib.request.Request("http://127.0.0.1:8787/api/upload", payload,
                                     {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        upload = json.load(response)
    (destination / "studio-upload.json").write_text(json.dumps(upload, indent=2), encoding="utf-8")
    print(json.dumps({"studio_upload": upload}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
