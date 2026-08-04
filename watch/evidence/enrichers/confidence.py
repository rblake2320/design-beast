"""
Aggregates confidence across multiple corroborating clues. Enforces the
standard OSINT rule: never confirm a hypothesis from one clue.
"""
def aggregate_confidence(events: list[dict], min_independent_sources: int = 2) -> dict:
    sources = {e["extractor"]["name"] for e in events}
    avg_conf = sum(e["confidence"] for e in events) / len(events) if events else 0.0
    return {
        "independent_source_count": len(sources),
        "meets_threshold": len(sources) >= min_independent_sources,
        "average_confidence": round(avg_conf, 3),
        "sources": sorted(sources),
    }
