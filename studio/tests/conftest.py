"""Shared test setup: redirect jobs.DB_PATH to a throwaway SQLite file BEFORE
any test module imports server.py, so its module-level jobs.init() /
recover_orphans() never touches the live studio/jobs.db. conftest.py is
imported by pytest ahead of every test module, which makes this the one safe
place to do the redirect (doing it per-module breaks when two modules run in
the same session — only the first import of server initializes the DB).
"""
import sys
import tempfile
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[1]
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import jobs as jobs_mod  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="beast-test-db-"))
jobs_mod.DB_PATH = _TMP / "jobs.db"
