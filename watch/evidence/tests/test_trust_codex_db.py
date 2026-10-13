"""Offline export integrity checks using ordinary synthetic event records.

These tests cover serialization and preservation of destination files only.
They make no assertion about authorization or authenticity of evidence.
"""

import json

import pytest

from exporters.dataset_jsonl import export_jsonl
from exporters.timeline import export_timeline


EXPORTERS = [
    pytest.param(export_jsonl, "events.jsonl", id="dataset-jsonl"),
    pytest.param(export_timeline, "timeline.json", id="timeline-json"),
]


def _events():
    return [
        {"event_id": "synthetic-1", "timestamp_ms": 0, "text": "Start"},
        {"event_id": "synthetic-2", "timestamp_ms": 1000, "text": "Finish"},
    ]


@pytest.mark.parametrize("exporter, filename", EXPORTERS)
def test_plain_event_records_round_trip(tmp_path, exporter, filename):
    destination = tmp_path / filename
    events = _events()
    exporter(events, str(destination))
    text = destination.read_text(encoding="utf-8")
    actual = (
        [json.loads(line) for line in text.splitlines()]
        if destination.suffix == ".jsonl"
        else json.loads(text)
    )
    assert actual == events


@pytest.mark.parametrize("exporter, filename", EXPORTERS)
@pytest.mark.parametrize("existing", [False, True], ids=["new-file", "existing-file"])
def test_serialization_error_preserves_destination(tmp_path, exporter, filename, existing):
    destination = tmp_path / filename
    previous = b'{"previous_export": true}\n'
    if existing:
        destination.write_bytes(previous)

    events = _events()
    # An application accidentally supplies an in-memory object instead of JSON.
    # Place it after a valid record to check the entire write transaction.
    events[1]["application_value"] = object()

    with pytest.raises((TypeError, ValueError)):
        exporter(events, str(destination))

    if existing:
        actual = destination.read_bytes()
        assert actual == previous, (
            f"serialization failure replaced a {len(previous)}-byte prior export "
            f"with {len(actual)} bytes"
        )
        assert set(tmp_path.iterdir()) == {destination}
    else:
        size = destination.stat().st_size if destination.exists() else 0
        assert not destination.exists(), f"serialization failure left {size} bytes"
        assert list(tmp_path.iterdir()) == []
