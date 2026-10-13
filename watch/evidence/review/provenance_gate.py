"""
Blocks extraction from running against a source that hasn't been through
media-provenance ingestion. No source_manifest, no extraction.
"""
def check_source_authorized(source_manifest: dict) -> dict:
    allowed = {"authorized_owned", "authorized_licensed",
               "authorized_public_domain", "authorized_fair_use_research"}
    if not isinstance(source_manifest, dict):
        return {"authorized": False, "status": None, "reason": "source manifest must be an object"}
    status = source_manifest.get("authorization_status")
    return {
        "authorized": status in allowed,
        "status": status,
        "reason": None if status in allowed else f"'{status}' is not an authorized status",
    }
