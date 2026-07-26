"""Unit tests for the bench runner protocol — no server, no GPU, no generation.

    cd design-beast && python -m pytest bench/tests/test_run_bench.py -q
"""
import importlib.util
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
REPO = BENCH.parent


def _load():
    spec = importlib.util.spec_from_file_location("run_bench", BENCH / "run_bench.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rb = _load()


def test_protocol_is_four_controlled_candidates():
    entry = {"id": "x", "category": "c", "brief": "b", "prompt": "p",
             "variation": "brief-specific variation"}
    v = rb.build_variations(entry)
    assert len(v) == rb.EXPECTED_CANDIDATES == 4
    # first candidate is the base prompt UNCHANGED (empty variation) — this is
    # exactly what the old single-candidate runner never did
    assert v[0] == ""
    assert v[1] == "brief-specific variation"
    assert v[2:] == rb.CONTROL_VARIATIONS
    assert len(rb.CONTROL_VARIATIONS) == 2


def test_every_brief_in_suite_yields_four_variations():
    suite = json.loads((BENCH / "briefs.json").read_text(encoding="utf-8"))
    briefs = suite["image_briefs"]
    assert suite["version"] == "0.2"
    assert len(briefs) == 50
    assert len({b["id"] for b in briefs}) == 50
    assert set(b["category"] for b in briefs) == {
        "product", "character", "environment", "ui", "game_asset", "typography",
    }
    for b in briefs:
        assert all(b.get(k, "").strip() for k in
                   ("id", "category", "brief", "prompt", "variation"))
        assert len(rb.build_variations(b)) == 4


def test_primary_candidates_excludes_auto_improved():
    cands = [{"i": 1}, {"i": 2}, {"i": 3}, {"i": 4}, {"i": 91}, {"i": 92}]
    primary = rb.primary_candidates(cands)
    assert [c["i"] for c in primary] == [1, 2, 3, 4]
    # a single-candidate result (the pre-2026-07-26 shape) must NOT validate
    assert len(rb.primary_candidates([{"i": 1}])) != rb.EXPECTED_CANDIDATES


def test_unique_path_never_overwrites(tmp_path):
    p = tmp_path / "20260101_000000_model.json"
    assert rb.unique_path(p) == p
    p.write_text("old result — must be preserved")
    assert rb.unique_path(p).name == "20260101_000000_model_1.json"
    (tmp_path / "20260101_000000_model_1.json").write_text("x")
    assert rb.unique_path(p).name == "20260101_000000_model_2.json"
    assert p.read_text() == "old result — must be preserved"


def test_old_v01_results_are_preserved():
    """The four pre-correction result files stay in the repo, unmodified shape."""
    old = sorted((BENCH / "results").glob("20260725_*.json")) + \
        sorted((BENCH / "results").glob("20260726_060905_*.json"))
    assert len(old) >= 4
    for f in old:
        data = json.loads(f.read_text(encoding="utf-8"))
        assert "protocol" not in data, f"{f.name} is v0.1 and must stay untouched"


def test_jobs_db_is_gitignored():
    for name in ("studio/jobs.db", "studio/jobs.db-shm", "studio/jobs.db-wal",
                 "studio/jobs.db-journal"):
        r = subprocess.run(["git", "check-ignore", "-q", name], cwd=REPO)
        assert r.returncode == 0, f"{name} is not gitignored"


def test_jobs_db_not_tracked():
    r = subprocess.run(["git", "ls-files", "--", "studio/jobs.db*"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.stdout.strip() == "", f"still tracked: {r.stdout}"
