"""Independent verifier for Beast signed evidence JSONL.

This intentionally shares no implementation code with the writer.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

GENESIS = "0" * 64


def verify(path: Path, public_path: Path, evidence_root: Path | None = None) -> dict:
    key = serialization.load_pem_public_key(public_path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        return {"ok": False, "error": "public key is not Ed25519"}
    raw = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    key_hash = hashlib.sha256(raw).hexdigest()
    expected_prev = GENESIS
    count = 0
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            full = json.loads(line)
            signature = base64.b64decode(full.pop("signature"), validate=True)
            recorded_hash = full.pop("chain_hash")
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            return {"ok": False, "error": f"line {line_no}: malformed: {exc}"}
        if full.get("prev") != expected_prev:
            return {"ok": False, "error": f"line {line_no}: broken previous link"}
        if full.get("signing_key_sha256") != key_hash:
            return {"ok": False, "error": f"line {line_no}: signing key mismatch"}
        payload = json.dumps(full, sort_keys=True, separators=(",", ":")).encode("utf-8")
        actual_hash = hashlib.sha256(payload).hexdigest()
        if actual_hash != recorded_hash:
            return {"ok": False, "error": f"line {line_no}: content hash mismatch"}
        try:
            key.verify(signature, payload)
        except InvalidSignature:
            return {"ok": False, "error": f"line {line_no}: invalid signature"}
        if evidence_root is not None:
            root = evidence_root.resolve()
            for record in full.get("evidence", []):
                evidence_path = (root / record["path"]).resolve()
                if not evidence_path.is_relative_to(root) or not evidence_path.is_file():
                    return {"ok": False, "error": f"line {line_no}: evidence missing or outside root: {record.get('path')}"}
                if evidence_path.stat().st_size != int(record["bytes"]):
                    return {"ok": False, "error": f"line {line_no}: evidence byte count changed: {record['path']}"}
                if hashlib.sha256(evidence_path.read_bytes()).hexdigest() != record["sha256"]:
                    return {"ok": False, "error": f"line {line_no}: evidence hash changed: {record['path']}"}
        expected_prev = recorded_hash
        count += 1
    return {"ok": True, "entries": count, "head": expected_prev, "signing_key_sha256": key_hash}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args(argv)
    result = verify(args.ledger, args.public, args.evidence_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
