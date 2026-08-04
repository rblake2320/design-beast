from enrichers.dedupe import dedupe_events


def test_dedupe_collapses_static_text():
    events = [
        {"source_time_start_ms": 0, "source_time_end_ms": 100, "modality": "screen_text",
         "content": "npm test", "frame_refs": ["f1.png"]},
        {"source_time_start_ms": 100, "source_time_end_ms": 200, "modality": "screen_text",
         "content": "npm test", "frame_refs": ["f2.png"]},
    ]
    result = dedupe_events(events)
    assert len(result) == 1
    assert result[0]["source_time_end_ms"] == 200
    assert result[0]["frame_refs"] == ["f1.png", "f2.png"]
