import json
import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import verify_higgsfield_proof as proof


ROOT = Path(__file__).resolve().parents[2] / "proofs/higgsfield-creative"


def test_retained_proof():
    assert proof.verify(ROOT)["artifacts"] == 5


@pytest.mark.parametrize("attack", ["duplicate", "receipt_escape", "checksum"])
def test_manifest_tampering_rejected(monkeypatch, attack):
    original = Path.read_text
    manifest = json.loads(original(ROOT / "artifact-manifest.json", encoding="utf-8"))
    if attack == "duplicate":
        manifest["artifacts"] = [manifest["artifacts"][0]] * 5
    elif attack == "receipt_escape":
        manifest["artifacts"][0]["receipt"] = "../outside.json"
    else:
        manifest["artifacts"][0]["sha256"] = "0" * 64
    def substitute(path, *args, **kwargs):
        if path.name == "artifact-manifest.json":
            return json.dumps(manifest)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", substitute)
    with pytest.raises(ValueError):
        proof.verify(ROOT)
