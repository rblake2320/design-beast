"""Exports aligned evidence + procedure claims as JSONL training records."""
import json

from .atomic import write_text_atomic


def export_jsonl(records: list[dict], output_path: str) -> None:
    # Serialize every record before touching the destination: a bad value writes nothing and keeps any prior export.
    try:
        text = "".join(json.dumps(r, allow_nan=False) + "\n" for r in records)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"record is not serializable as JSON; nothing written: {exc}") from exc
    write_text_atomic(output_path, text)
