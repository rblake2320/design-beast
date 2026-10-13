"""
Compiles ProcedureClaims into Beast's skill-validation contract format —
the same shape as the existing exact-replay manifest / compiled-skill
output already shipped, so this plugs into that instead of inventing a
second skill format.
"""
import json
import os
import tempfile

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

    # Declared scope, not proof: the gate checked shape, authorization status and review_state rules.
    # Authorization is a declaration, references are not resolved against an evidence store, and
    # execution fields are reported receipts that have not been independently verified.
    bundle = {
        "source_manifest": source_manifest,
        "procedure_claims": procedure_claims,
        "review_gate_passed": True,
        "verification_scope": {
            "authorization": "declared",
            "references": "IDs_present_unresolved",
            "execution": "reported_receipts_not_independently_verified",
        },
    }
    # Serialize fully before touching the filesystem: a non-JSON value must refuse with no output file.
    try:
        text = json.dumps(bundle, indent=2, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"bundle is not serializable as JSON; nothing written: {exc}") from exc
    # Write to a temp file in the destination directory, then atomically replace: no partial output.
    directory = os.path.dirname(os.path.abspath(output_path))
    fd, temporary = tempfile.mkstemp(dir=directory, prefix=".bundle-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output_path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    return bundle
