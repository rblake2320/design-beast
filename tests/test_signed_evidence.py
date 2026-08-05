import importlib.util
import json
from pathlib import Path

from beast import signed_chain

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("independent_verifier", ROOT / "scripts" / "verify_signed_evidence.py")
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def make_chain(tmp_path):
    private = tmp_path / "private.pem"
    public = tmp_path / "public.pem"
    ledger = tmp_path / "evidence.jsonl"
    signed_chain.generate_keypair(private, public)
    signed_chain.append(ledger, private, event="probe", subject="pack", evidence=[{"sha256": "a" * 64}])
    signed_chain.append(ledger, private, event="practice", subject="pack", evidence=[{"sha256": "b" * 64}])
    return ledger, private, public


def test_independent_verifier_accepts_intact_chain(tmp_path):
    ledger, _, public = make_chain(tmp_path)
    result = verifier.verify(ledger, public)
    assert result["ok"] is True
    assert result["entries"] == 2


def test_content_tampering_is_detected(tmp_path):
    ledger, _, public = make_chain(tmp_path)
    rows = ledger.read_text().splitlines()
    entry = json.loads(rows[0])
    entry["subject"] = "rewritten"
    rows[0] = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    ledger.write_text("\n".join(rows) + "\n")
    result = verifier.verify(ledger, public)
    assert result["ok"] is False
    assert "hash mismatch" in result["error"] or "signature" in result["error"]


def test_deletion_and_wrong_key_are_detected(tmp_path):
    ledger, _, public = make_chain(tmp_path)
    ledger.write_text(ledger.read_text().splitlines()[1] + "\n")
    assert verifier.verify(ledger, public)["ok"] is False
    other_private = tmp_path / "other-private.pem"
    other_public = tmp_path / "other-public.pem"
    signed_chain.generate_keypair(other_private, other_public)
    assert verifier.verify(ledger, other_public)["ok"] is False


def test_keygen_refuses_overwrite(tmp_path):
    private = tmp_path / "private.pem"
    public = tmp_path / "public.pem"
    signed_chain.generate_keypair(private, public)
    try:
        signed_chain.generate_keypair(private, public)
        assert False, "expected overwrite refusal"
    except FileExistsError:
        pass


def test_verifier_can_bind_signed_receipt_to_current_evidence_bytes(tmp_path):
    private = tmp_path / "private.pem"
    public = tmp_path / "public.pem"
    ledger = tmp_path / "evidence.jsonl"
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("original")
    signed_chain.generate_keypair(private, public)
    signed_chain.append(
        ledger, private, event="proof", subject="artifact",
        evidence=[{"path": "artifact.txt", "bytes": 8,
                   "sha256": __import__("hashlib").sha256(b"original").hexdigest()}],
    )
    assert verifier.verify(ledger, public, tmp_path)["ok"] is True
    artifact.write_text("rewritten")
    result = verifier.verify(ledger, public, tmp_path)
    assert result["ok"] is False
    assert "evidence" in result["error"]
