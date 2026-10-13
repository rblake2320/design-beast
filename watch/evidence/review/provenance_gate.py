"""
Blocks extraction from running against a source that hasn't been through
media-provenance ingestion. No source_manifest, no extraction.

Shape follows watch/evidence/schema/source_manifest.schema.json: required
source_id, sha256, authorization_status and ingested_at, with string types.
"""
AUTHORIZED_STATES = frozenset({"authorized_owned", "authorized_licensed",
                               "authorized_public_domain", "authorized_fair_use_research"})
REQUIRED_STRING_FIELDS = ("source_id", "sha256", "ingested_at")


def check_source_authorized(source_manifest) -> dict:
    if not isinstance(source_manifest, dict):
        return {"authorized": False, "status": None, "reason": "source manifest must be an object"}
    missing = [f for f in REQUIRED_STRING_FIELDS
               if not isinstance(source_manifest.get(f), str) or not source_manifest[f].strip()]
    if missing:
        return {"authorized": False, "status": source_manifest.get("authorization_status"),
                "reason": f"source manifest requires nonempty string fields: {', '.join(missing)}"}
    status = source_manifest.get("authorization_status")
    if not isinstance(status, str):
        return {"authorized": False, "status": None,
                "reason": "authorization_status must be a string"}
    authorized = status in AUTHORIZED_STATES
    return {
        "authorized": authorized,
        "status": status,
        "reason": None if authorized else f"'{status}' is not an authorized status",
    }
