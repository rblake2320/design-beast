"""Exports the aligned evidence timeline (from enrichers/timestamp_align.py) to JSON."""
import json


def export_timeline(timeline_items: list[dict], output_path: str) -> None:
    with open(output_path, "w") as f:
        json.dump(timeline_items, f, indent=2)
