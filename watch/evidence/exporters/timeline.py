"""Exports the aligned evidence timeline (from enrichers/timestamp_align.py) to JSON."""
import json

from .atomic import write_text_atomic


def export_timeline(timeline_items: list[dict], output_path: str) -> None:
    # Serialize before touching the destination: a bad value writes nothing and keeps any prior export.
    try:
        text = json.dumps(timeline_items, indent=2, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"timeline is not serializable as JSON; nothing written: {exc}") from exc
    write_text_atomic(output_path, text)
