"""
Collapses repeated OCR/landmark reads of the same static content across
consecutive frames into a single time-ranged EvidenceEvent, so 8 seconds
of a static terminal screen doesn't produce 240 duplicate events.
"""
def dedupe_events(events: list[dict], similarity_threshold: float = 0.92) -> list[dict]:
    if not events:
        return []
    events = sorted(events, key=lambda e: e["source_time_start_ms"])
    merged = [events[0]]
    for ev in events[1:]:
        last = merged[-1]
        if (ev["modality"] == last["modality"]
                and ev.get("content") == last.get("content")):
            last["source_time_end_ms"] = ev["source_time_end_ms"]
            last["frame_refs"].extend(ev.get("frame_refs", []))
        else:
            merged.append(ev)
    return merged
