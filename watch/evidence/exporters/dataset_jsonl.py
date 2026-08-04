"""Exports aligned evidence + procedure claims as JSONL training records."""
import json


def export_jsonl(records: list[dict], output_path: str) -> None:
    with open(output_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
