"""
Mechanically enforces the 5 review states from the council review, so the
no-faking rule is code, not just documentation:
observed -> inferred -> uncertain -> verified_by_execution -> rejected
A ProcedureClaim must never be exported as final if its review_state is
'inferred' or 'uncertain' without requires_human_approval=True.
"""
VALID_STATES = ["observed", "inferred", "uncertain", "verified_by_execution", "rejected"]


def _nonempty_text(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def validate_claim(claim) -> dict:
    if not isinstance(claim, dict):
        return {"valid": False, "errors": ["claim must be an object"]}
    errors = []
    if not _nonempty_text(claim.get("step_id")):
        errors.append("claim requires a nonempty step_id")
    if not _nonempty_text(claim.get("description")):
        errors.append("claim requires a nonempty description")
    evidence = claim.get("evidence_event_ids")
    if not (isinstance(evidence, list) and evidence and all(_nonempty_text(e) for e in evidence)):
        errors.append("claim requires a nonempty list of evidence_event_ids")
    if claim.get("review_state") not in VALID_STATES:
        errors.append(f"invalid review_state: {claim.get('review_state')}")
    if claim.get("review_state") in ("inferred", "uncertain") and claim.get("requires_human_approval") is not True:
        errors.append("inferred/uncertain claims MUST set requires_human_approval to boolean true")
    if claim.get("review_state") == "verified_by_execution":
        replay = claim.get("replay_result")
        if not isinstance(replay, dict):
            errors.append("verified_by_execution requires a replay_result record")
        elif replay.get("success") is not True:
            errors.append("verified_by_execution requires replay_result.success == true")
        elif "exit_code" in replay and not (type(replay["exit_code"]) is int and replay["exit_code"] == 0):
            errors.append("replay_result.exit_code contradicts success == true")
    return {"valid": len(errors) == 0, "errors": errors}
