"""
Compiles ProcedureClaims into Beast's skill-validation contract format —
the same shape as the existing exact-replay manifest / compiled-skill
output already shipped, so this plugs into that instead of inventing a
second skill format.
"""
import json
import os
import tempfile
from pathlib import Path

from watch.evidence.review.evidence_gate import validate_claim


def compile_skill_bundle(procedure_claims: list[dict], source_manifest: dict, output_path: str) -> dict:
    if not isinstance(procedure_claims, list) or not procedure_claims:
        raise ValueError("candidate bundle requires nonempty claims")
    if not isinstance(source_manifest, dict) or not source_manifest.get("source_id"):
        raise ValueError("candidate bundle requires a source_id")
    for claim in procedure_claims:
        result = validate_claim(claim)
        if not result["valid"]:
            raise ValueError("; ".join(result["errors"]))
    unapproved = [c for c in procedure_claims
                  if c["review_state"] in ("inferred", "uncertain") and not c.get("requires_human_approval")]
    if unapproved:
        raise ValueError(f"{len(unapproved)} claims lack required human approval flag — fix before export")

    bundle = {
        "source_manifest": source_manifest,
        "procedure_claims": procedure_claims,
        "schema": "beast.candidate-bundle/v1",
        "evidence_backed": False,
        "hard_proof_boundary": False,
        "promotion_allowed": False,
        "boundary": "Unverified candidate export; an approval-required flag is not approval or execution proof.",
    }
    target = Path(output_path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                         delete=False) as f:
            temporary = f.name
            json.dump(bundle, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, target)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return bundle
