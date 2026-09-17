"""Stage 9-pre: events — photos taken close in time and place belong together.

This is how Google/Apple/PhotoPrism build "Thursday in Berlin": a new event starts when
the gap to the previous photo exceeds GAP_HOURS or the GPS position moves more than
RADIUS_KM. GPS is reverse-geocoded OFFLINE (reverse_geocoder, bundled GeoNames table) so
nothing leaves the machine. Events feed album naming: a GPS event is named from its
place and month; a no-GPS event still keeps its photos together for the embedding groups.
"""
from __future__ import annotations

import json
import math
from datetime import datetime

from .store import Store

GAP_HOURS = 6.0
RADIUS_KM = 25.0
MIN_EVENT = 3


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _gps(exif_json: str | None) -> tuple[float, float] | None:
    try:
        gps = json.loads(exif_json or "{}").get("gps")
        return (float(gps["lat"]), float(gps["lon"])) if gps else None
    except (ValueError, KeyError, TypeError):
        return None


def place_name(coord: tuple[float, float]) -> str | None:
    try:
        import reverse_geocoder as rg
        hit = rg.search([coord], mode=1)[0]
    except Exception:  # noqa: BLE001 — offline table missing → no place, still an event
        return None
    city, region, cc = hit.get("name", ""), hit.get("admin1", ""), hit.get("cc", "")
    return ", ".join(p for p in (city, region if cc == "US" else cc) if p) or None


def split_events(rows: list[dict], gap_hours: float = GAP_HOURS, radius_km: float = RADIUS_KM) -> list[list[dict]]:
    """rows: dicts with taken_at (ISO) and gps (lat, lon) | None, any order."""
    def ts(r):
        try:
            return datetime.fromisoformat(r["taken_at"])
        except (TypeError, ValueError):
            return datetime.min
    rows = sorted(rows, key=ts)
    events: list[list[dict]] = []
    for r in rows:
        if events:
            prev = events[-1][-1]
            far = (r["gps"] and prev["gps"] and _haversine_km(r["gps"], prev["gps"]) > radius_km)
            late = (ts(r) - ts(prev)).total_seconds() > gap_hours * 3600
            if not far and not late:
                events[-1].append(r); continue
        events.append([r])
    return _merge_trips(events, radius_km)


TRIP_GAP_HOURS = 48.0


def _centre(event: list[dict]) -> tuple[float, float] | None:
    coords = [r["gps"] for r in event if r["gps"]]
    if not coords:
        return None
    return sum(c[0] for c in coords) / len(coords), sum(c[1] for c in coords) / len(coords)


def _merge_trips(events: list[list[dict]], radius_km: float) -> list[list[dict]]:
    """Consecutive events at the same place within two days are one trip ("3 days in Asheville")."""
    merged: list[list[dict]] = []
    for ev in events:
        if merged:
            prev = merged[-1]
            a, b = _centre(prev), _centre(ev)
            try:
                gap_h = (datetime.fromisoformat(ev[0]["taken_at"])
                         - datetime.fromisoformat(prev[-1]["taken_at"])).total_seconds() / 3600
            except (TypeError, ValueError):
                gap_h = float("inf")
            if a and b and _haversine_km(a, b) <= radius_km and gap_h <= TRIP_GAP_HOURS:
                prev.extend(ev); continue
        merged.append(list(ev))
    return merged


def event_title(event: list[dict]) -> str | None:
    coords = [r["gps"] for r in event if r["gps"]]
    if not coords:
        return None
    centre = (sum(c[0] for c in coords) / len(coords), sum(c[1] for c in coords) / len(coords))
    place = place_name(centre)
    if not place:
        return None
    first = event[0]["taken_at"][:7]
    try:
        month = datetime.strptime(first, "%Y-%m").strftime("%B %Y")
    except ValueError:
        month = first
    return f"{place} - {month}"


def run(store: Store) -> dict:
    rows = [{"id": a["id"], "taken_at": a["taken_at"], "gps": _gps(a.get("exif"))}
            for a in store.assets(representatives_only=True)]
    events = split_events(rows)
    placed = 0
    with store.tx():
        store.execute("UPDATE assets SET event_id = NULL, event_title = NULL")
        for n, ev in enumerate(events, 1):
            title = event_title(ev) if len(ev) >= MIN_EVENT else None
            for r in ev:
                store.execute("UPDATE assets SET event_id = ?, event_title = ? WHERE id = ?", (n, title, r["id"]))
            placed += len(ev) if title else 0
    summary = {"representatives": len(rows), "events": len(events),
               "with_gps": sum(1 for r in rows if r["gps"]), "placed_by_gps": placed}
    store.log("events", summary)
    store.commit()
    return summary
