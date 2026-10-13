"""
Compiles ProcedureClaims into Beast's skill-validation contract format —
the same shape as the existing exact-replay manifest / compiled-skill
output already shipped, so this plugs into that instead of inventing a
second skill format.
"""
import json


from review.evidence_gate import validate_claim
from review.provenance_gate import check_source_authorized


def compile_skill_bundle(procedure_claims: list[dict], source_manifest: dict, output_path: str) -> dict:
    if not isinstance(procedure_claims, list) or not procedure_claims:
        raise ValueError("no procedure claims: an empty bundle carries no evidence and cannot be exported")
    if not check_source_authorized(source_manifest)["authorized"]:
        raise ValueError("source is not authorized for export (authorization_status must be one of the canonical authorized_* states)")
    invalid = [(c.get("step_id") if isinstance(c, dict) else None, validate_claim(c)["errors"]) for c in procedure_claims]
    invalid = [(step, errs) for step, errs in invalid if errs]
    if invalid:
        raise ValueError(f"{len(invalid)} claims fail the review gate; first: {invalid[0]}")
    step_ids = [c["step_id"] for c in procedure_claims]
    if len(set(step_ids)) != len(step_ids):
        raise ValueError("duplicate step_id: references would be ambiguous")

    bundle = {
        "source_manifest": source_manifest,
        "procedure_claims": procedure_claims,
        "evidence_backed": True,
        "hard_proof_boundary": True,
    }
    with open(output_path, "w") as f:
        json.dump(bundle, f, indent=2)
    return bundle
