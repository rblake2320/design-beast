"""Offline audit of the retained MCP proof; never submits a cloud request."""
import hashlib
import json
from pathlib import Path

from PIL import Image


def verify(root: Path) -> dict:
    manifest = json.loads((root / "artifact-manifest.json").read_text(encoding="utf-8"))
    if manifest["transport"] != "higgsfield_mcp_connector":
        raise ValueError("unexpected proof transport")
    records = manifest["artifacts"]
    expected = {f"candidate-{i}.png" for i in range(1, 5)} | {"refined-4k.png"}
    if (len(records) != 5 or {r["file"] for r in records} != expected
            or len({r["job_id"] for r in records}) != 5):
        raise ValueError("all four candidates and refinement are required")
    for record in records:
        path = (root / record["file"]).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("missing or escaping artifact")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("artifact checksum mismatch")
        with Image.open(path) as image:
            image.load()
            if list(image.size) != record["dimensions"]:
                raise ValueError("artifact dimensions mismatch")
        expected_receipt = "refinement-result.json" if record["file"] == "refined-4k.png" else "candidates.json"
        receipt_path = (root / record["receipt"]).resolve()
        if (record["receipt"] != expected_receipt
                or not receipt_path.is_relative_to(root.resolve()) or not receipt_path.is_file()):
            raise ValueError("missing or escaping receipt")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        matches = [j for j in receipt["jobs"] if j["job_id"] == record["job_id"]]
        if len(matches) != 1 or matches[0]["status"] != "completed":
            raise ValueError("artifact lacks a completed provider receipt")
    return {"ok": True, "artifacts": len(records), "transport": manifest["transport"],
            "boundary": "Offline integrity audit, not independent provider attestation or CLI authentication proof."}


if __name__ == "__main__":
    print(json.dumps(verify(Path(__file__).resolve().parents[1] / "proofs/higgsfield-creative")))
