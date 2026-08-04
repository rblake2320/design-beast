from enrichers.timestamp_align import align_to_timeline


def test_align_sorts_by_start_time():
    evidence = [{"source_time_start_ms": 500, "modality": "screen_text"}]
    transcript = [{"source_time_start_ms": 100, "text": "hello"}]
    result = align_to_timeline(evidence, transcript)
    assert result[0]["source_time_start_ms"] == 100
    assert result[1]["source_time_start_ms"] == 500
