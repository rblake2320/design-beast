"""Contract tests: openapi.json is well-formed, not stale, and every documented
endpoint has SDK coverage. GPU-free, no live server — regenerates the schema
against a throwaway DB the same way scripts/generate_openapi.py does.

    cd design-beast && python -m pytest sdk/python/tests/test_openapi_contract.py -q
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OPENAPI_JSON = REPO / "openapi.json"

sys.path.insert(0, str(REPO / "scripts"))
import generate_openapi  # noqa: E402

# Every path+method Beast Studio exposes that an agent/client is meant to
# call, mapped to the Python SDK method that covers it. "/" (index.html) is
# intentionally excluded — it serves the web UI, not an API response.
EXPECTED_COVERAGE = {
    ("GET", "/api/recipes"): "recipes",
    ("POST", "/api/upload"): "upload",
    ("POST", "/api/expand"): "expand",
    ("POST", "/api/judge"): "judge",
    ("POST", "/api/tts"): "tts",
    ("GET", "/api/backends"): "backends",
    ("POST", "/api/backend"): "backend",
    ("GET", "/api/health"): "health",
    ("GET", "/api/runs"): "runs",
    ("GET", "/api/registry"): "registry",
    ("GET", "/api/ledger/verify"): "verify_ledger",
    ("POST", "/api/run"): "run",
    ("POST", "/api/refine"): "refine",
    ("POST", "/api/animate"): "animate",
    ("POST", "/api/to3d"): "to3d",
    ("POST", "/api/to_ue"): "to_ue",
    ("GET", "/api/run/{run_id}"): "status",
    ("POST", "/api/job/{run_id}/cancel"): "cancel",
    ("POST", "/api/job/{run_id}/retry"): "retry",
    ("GET", "/api/events/{run_id}"): "stream_events",  # + events_url()
}


def test_openapi_json_checked_in_and_valid():
    assert OPENAPI_JSON.exists(), "openapi.json must be generated and checked in"
    schema = json.loads(OPENAPI_JSON.read_text(encoding="utf-8"))
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "Beast Studio API"
    assert schema["info"]["version"]
    assert schema["paths"], "schema has no paths — generation likely broke"


def test_openapi_json_matches_fresh_generation():
    """Fails if server.py's routes changed since openapi.json was last
    regenerated — the same check `generate_openapi.py --check` runs."""
    fresh = generate_openapi.generate()
    fresh_text = json.dumps(fresh, indent=2, sort_keys=True) + "\n"
    current = OPENAPI_JSON.read_text(encoding="utf-8")
    assert current == fresh_text, (
        "openapi.json is stale — run `python scripts/generate_openapi.py` "
        "and check in the result")


def test_openapi_generation_restores_caller_database():
    """Schema generation must not poison tests or servers sharing jobs.py."""
    import jobs

    original = jobs.DB_PATH
    generate_openapi.generate()
    assert jobs.DB_PATH == original
    assert jobs._db().execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
    ).fetchone()


def test_every_documented_endpoint_has_sdk_coverage():
    schema = json.loads(OPENAPI_JSON.read_text(encoding="utf-8"))
    documented = {
        (method.upper(), path)
        for path, methods in schema["paths"].items()
        for method in methods
        if path != "/"
    }
    missing = documented - set(EXPECTED_COVERAGE)
    assert not missing, f"endpoints with no SDK coverage mapping: {missing}"


def test_expected_coverage_methods_exist_on_client():
    sys.path.insert(0, str(REPO / "sdk" / "python"))
    from beast_studio_client import BeastStudioClient
    for (method, path), client_method in EXPECTED_COVERAGE.items():
        assert hasattr(BeastStudioClient, client_method), (
            f"{method} {path} maps to BeastStudioClient.{client_method}, "
            "which doesn't exist")
