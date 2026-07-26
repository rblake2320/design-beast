# Beast Studio SDKs

Two lightweight clients for the Beast Studio local API
(`http://127.0.0.1:8787`, this machine only), tested against the versioned
OpenAPI endpoint/request contract at [`../openapi.json`](../openapi.json).

The server does not yet declare FastAPI response models, so OpenAPI response
schemas are currently unpopulated. Response types in the SDKs are maintained
against the server's actual return shapes; they are not generated from the
schema. Treat response-model drift as a known contract limitation.

| | Python | TypeScript |
|---|---|---|
| Path | [`python/`](python/) | [`typescript/`](typescript/) |
| Runtime deps | `requests` | none (uses platform `fetch`) |
| Requires | Python 3.10+ | Node 22.6+ (or any modern browser bundler) |
| Tests | `python -m pytest sdk/python/tests -q` | `cd sdk/typescript && node --test tests/` |

Neither SDK touches `studio/server.py` or `studio/jobs.py` — they are pure
HTTP clients against the existing API surface.

## Contract (`openapi.json`)

Generated from the live FastAPI app, not hand-written:

```
python scripts/generate_openapi.py          # regenerate after any server.py route change
python scripts/generate_openapi.py --check  # CI-style: exit 1 if stale
```

The generator redirects `jobs.DB_PATH` to a throwaway temp file **before**
importing `studio/server.py` (which calls `jobs.init()` at import time), so
it never touches the live `studio/jobs.db`.

`sdk/python/tests/test_openapi_contract.py` fails the build if:
- `openapi.json` is stale relative to a fresh generation (route added/changed
  without regenerating), or
- any documented endpoint has no mapped SDK method (`EXPECTED_COVERAGE` in
  that file — update it when you add a new endpoint).

**Contract version** is tracked independently of `server.py`'s own (unset)
FastAPI app version, since that file is out of scope for the generator to
modify — see `CONTRACT_VERSION` in `scripts/generate_openapi.py`. Bump it on
any breaking request/response shape change; both SDK packages' own
`version` fields track it too.

## Design choices shared by both clients

- **Credit/privacy flags default to `false`.** `allow_cloud_fallback`
  (refine, animate) and `allow_hosted_fallback` (to3d) are never sent `true`
  unless the caller explicitly passes it — matching AGENT_ACCESS.md rule 1.
  Every SDK has a test asserting this default.
- **API-level errors are returned, not thrown, by default.** Beast Studio's
  own error contract is JSON (`{"error": ..., "code": ...}`), matching how
  AGENT_ACCESS.md already documents consuming this API. Both clients accept
  a `raiseForStatus`/`raise_for_status` constructor option for callers who
  prefer exception-based handling of non-2xx responses. Transport-level
  failures (connection refused, non-JSON body) always raise
  `BeastStudioError`, independent of that option.
- **`wait(runId)` prefers SSE, falls back to polling.** Both clients expose
  `eventsUrl()`/`events_url()` (just the URL, for callers who want to drive
  their own `EventSource`/SSE client) and a dependency-free streaming
  generator (`streamEvents()`/`stream_events()`) that parses `data:` frames
  directly — no `EventSource` (browser-only) or extra package required. If
  the stream can't be opened, `wait()` transparently falls back to polling
  `status()`.

## What isn't covered

Operational rules that live outside the HTTP contract — backend-sharing
etiquette (don't stop a service another agent started), VRAM contention
(don't run `quality:"cinema"` alongside image generation), and the
quality-loop workflow (`expand` → 4 variations → `run` → act on the judge's
`fix`) — are documented in [`../AGENT_ACCESS.md`](../AGENT_ACCESS.md), not
re-encoded here. Read both.
