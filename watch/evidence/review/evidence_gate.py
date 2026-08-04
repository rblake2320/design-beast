"""
Mechanically enforces the 5 review states from the council review, so the
no-faking rule is code, not just documentation:
observed -> inferred -> uncertain -> verified_by_execution -> rejected
A ProcedureClaim must never be exported as final if its review_state is
'inferred' or 'uncertain' without requires_human_approval=True.
"""
VALID_STATES = ["observed", "inferred", "uncertain", "verified_by_execution", "rejected"]


def validate_claim(claim: dict) -> dict:
    errors = []
    if claim.get("review_state") not in VALID_STATES:
        errors.append(f"invalid review_state: {claim.get('review_state')}")
    if claim.get("review_state") in ("inferred", "uncertain") and not claim.get("requires_human_approval"):
        errors.append("inferred/uncertain claims MUST set requires_human_approval=True")
    if claim.get("review_state") == "verified_by_execution" and not claim.get("replay_result"):
        errors.append("verified_by_execution requires a replay_result record")
    return {"valid": len(errors) == 0, "errors": errors}
