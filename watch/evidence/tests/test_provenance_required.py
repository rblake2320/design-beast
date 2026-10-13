from review.provenance_gate import check_source_authorized

# Schema-complete SourceManifest (source_manifest.schema.json required fields).
MANIFEST = {"source_id": "synthetic-src", "sha256": "0" * 64,
            "ingested_at": "2026-10-12T00:00:00+00:00"}


def test_rejects_unauthorized_source():
    result = check_source_authorized(dict(MANIFEST, authorization_status="unverified_do_not_use"))
    assert result["authorized"] is False


def test_accepts_owned_source():
    result = check_source_authorized(dict(MANIFEST, authorization_status="authorized_owned"))
    assert result["authorized"] is True
