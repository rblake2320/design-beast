"""
Compiles ProcedureClaims into Beast's skill-validation contract format —
the same shape as the existing exact-replay manifest / compiled-skill
output already shipped, so this plugs into that instead of inventing a
second skill format.
"""
import json


from review.evidence_gate import validate_claim

# Provisional vocabulary: only an explicit "authorized" source is exportable (fail closed).
AUTHORIZED_SOURCE_STATUSES = frozenset({"authorized"})


def compile_skill_bundle(procedure_claims: list[dict], source_manifest: dict, output_path: str) -> dict:
    if not procedure_claims:
        raise ValueError("no procedure claims: an empty bundle carries no evidence and cannot be exported")
    if (source_manifest or {}).get("authorization_status") not in AUTHORIZED_SOURCE_STATUSES:
        raise ValueError("source is not explicitly authorized for export (authorization_status must be 'authorized')")
    invalid = [(c.get("step_id"), validate_claim(c)["errors"]) for c in procedure_claims]
    invalid = [(step, errs) for step, errs in invalid if errs]
    if invalid:
        raise ValueError(f"{len(invalid)} claims fail the review gate; first: {invalid[0]}")

    bundle = {
        "source_manifest": source_manifest,
        "procedure_claims": procedure_claims,
        "evidence_backed": True,
        "hard_proof_boundary": True,
    }
    with open(output_path, "w") as f:
        json.dump(bundle, f, indent=2)
    return bundle
