"""
Gate for dataset-export mode. Requires explicit license record, reviewer
identity, and split info before any JSONL/Parquet export is allowed.
"""
REQUIRED_FIELDS = ["source_authorization_record", "reviewer_id", "label_schema_version", "split"]


def check_export_ready(dataset_manifest: dict) -> dict:
    missing = [f for f in REQUIRED_FIELDS if not dataset_manifest.get(f)]
    return {"ready": len(missing) == 0, "missing_fields": missing}
