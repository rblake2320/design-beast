#!/usr/bin/env python3
"""Generate Beast Studio's OpenAPI contract from the live FastAPI app.

    python scripts/generate_openapi.py            # writes openapi.json
    python scripts/generate_openapi.py --check     # exit 1 if openapi.json is stale

Never touches the live studio/jobs.db: jobs.DB_PATH is redirected to a
throwaway temp file BEFORE studio/server.py is imported (server.py calls
jobs.init() at import time). Does not modify studio/server.py or
studio/jobs.py — the contract version below is layered onto the generated
schema in this script, not on the FastAPI app object itself.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STUDIO = REPO / "studio"
OPENAPI_JSON = REPO / "openapi.json"

# Contract version: bump on any breaking change to a request/response shape.
# Independent of studio/server.py's own (unset) FastAPI app version, since
# that file is out of scope for this generator to modify.
CONTRACT_VERSION = "1.0.0"


def generate() -> dict:
    sys.path.insert(0, str(STUDIO))
    import jobs as jobs_mod
    original_db = jobs_mod.DB_PATH
    with tempfile.TemporaryDirectory(prefix="beast-openapi-gen-") as tmp:
        # jobs uses a thread-local connection, so changing DB_PATH alone is
        # insufficient when generate() is called inside a larger pytest run.
        # Close both sides of the swap and restore the caller's DB afterward.
        if hasattr(jobs_mod._LOCAL, "conn"):
            jobs_mod._LOCAL.conn.close()
            del jobs_mod._LOCAL.conn
        jobs_mod.DB_PATH = Path(tmp) / "jobs.db"
        try:
            import server  # noqa: E402 — first import initializes the temp DB
            jobs_mod.init()  # required when server was already imported
            schema = server.app.openapi()
        finally:
            if hasattr(jobs_mod._LOCAL, "conn"):
                jobs_mod._LOCAL.conn.close()
                del jobs_mod._LOCAL.conn
            jobs_mod.DB_PATH = original_db

    schema["info"]["version"] = CONTRACT_VERSION
    schema["info"]["title"] = "Beast Studio API"
    schema["info"]["description"] = (
        "Local AI production API for Beast Studio (127.0.0.1:8787, this "
        "machine only). Contract generated from the live FastAPI app — see "
        "AGENT_ACCESS.md for operational rules (credit/privacy defaults, "
        "backend-sharing etiquette) that this schema does not itself "
        "encode. Sync endpoints return results directly; async endpoints "
        "return {id} and are polled via GET /api/run/{run_id} or streamed "
        "via GET /api/events/{run_id} (SSE)."
    )
    schema["servers"] = [{"url": "http://127.0.0.1:8787",
                          "description": "local Beast Studio server"}]
    return schema


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if openapi.json doesn't match a fresh generation")
    args = ap.parse_args()

    fresh = generate()
    fresh_text = json.dumps(fresh, indent=2, sort_keys=True) + "\n"

    if args.check:
        if not OPENAPI_JSON.exists():
            print("openapi.json does not exist — run without --check to generate it")
            return 1
        current = OPENAPI_JSON.read_text(encoding="utf-8")
        if current != fresh_text:
            print("openapi.json is STALE — regenerate with "
                  "`python scripts/generate_openapi.py`")
            return 1
        print("openapi.json is up to date")
        return 0

    OPENAPI_JSON.write_text(fresh_text, encoding="utf-8")
    print(f"wrote {OPENAPI_JSON} ({len(fresh['paths'])} paths, "
          f"contract v{CONTRACT_VERSION})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
