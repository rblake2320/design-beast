"""
Compiles ProcedureClaims into Beast's skill-validation contract format —
the same shape as the existing exact-replay manifest / compiled-skill
output already shipped, so this plugs into that instead of inventing a
second skill format.
"""
import json


def compile_skill_bundle(procedure_claims: list[dict], source_manifest: dict, output_path: str) -> dict:
    unapproved = [c for c in procedure_claims
                  if c["review_state"] in ("inferred", "uncertain") and not c.get("requires_human_approval")]
    if unapproved:
        raise ValueError(f"{len(unapproved)} claims lack required human approval flag — fix before export")

    bundle = {
        "source_manifest": source_manifest,
        "procedure_claims": procedure_claims,
        "evidence_backed": True,
        "hard_proof_boundary": True,
    }
    with open(output_path, "w") as f:
        json.dump(bundle, f, indent=2)
    return bundle
