"""
Aligns OCR/UI-state events with transcript segments on a shared timeline.
Preserves Beast's existing source-time evidence-map behavior (original
--start/--end timestamps preserved) rather than reinventing it.
"""
def align_to_timeline(evidence_events: list[dict], transcript_segments: list[dict]) -> list[dict]:
    timeline = []
    all_items = [{"type": "evidence", **e} for e in evidence_events] + \
                [{"type": "transcript", **t} for t in transcript_segments]
    return sorted(all_items, key=lambda x: x["source_time_start_ms"])
