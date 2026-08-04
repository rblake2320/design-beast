# Gap closure — Google Vision/Video Intelligence safety features

Added 2026-08-04 (local Claude session) in response to the gap report:

| Gap | Closed by |
|---|---|
| Cloud Vision SAFE_SEARCH_DETECTION | `watch/evidence/extractors/safe_search.py` |
| Cloud Vision WEB_DETECTION (reverse image / entities) | `watch/evidence/extractors/web_entities.py` |
| Video Intelligence EXPLICIT_CONTENT_DETECTION (not in the original report, same pre-filter rationale for screen recordings) | `watch/evidence/extractors/explicit_content_video.py` |

Design decisions (all tested in `tests/test_safety_extractors.py`, 17 tests):

- **Fail-closed everywhere**: API failure or UNKNOWN likelihood = quarantine,
  never a pass. Quarantine emits an event — no silent drops.
- **SafeSearch is a pre-filter gate**: run before other extractors; verdict is
  recorded in provenance either way. Piggybacks on the landmark
  images.annotate call (no extra request).
- **Web detection enforces a scenes-not-people boundary**: frames must be
  screened person-free before the API is called; person-flagged and
  unscreened frames are refused and human-gated. Opt-out is explicit
  (`require_person_screening=False`) for person-free-by-construction sources.
- Match/entity/similar events are ONE clue signal each, feeding the existing
  2-independent-clue gate; similar-image confidence capped at 0.3.

Also fixed while integrating:
- `tests/conftest.py` — latent import defect: extractors use flat
  `from base import ...` imports but nothing put `extractors/` on sys.path;
  any test importing an extractor failed collection.
- `pytest.ini` — anchors rootdir (also stops pytest walking up into
  unrelated parent configs).

Suite: 23 passed (was 6). API calls remain stubbed contract-style, matching
the package's existing extractors — wiring is the merge-time step.
