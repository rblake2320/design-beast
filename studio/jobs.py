"""Durable job store for Beast Studio (P0).

SQLite-backed lifecycle: queued → running → done | failed | cancelled.
Survives server restarts (boot recovery marks orphaned running jobs failed).
Provides idempotency keys, cancellation flags, a global GPU lease for
heavy jobs, and structured error codes.
"""
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "jobs.db"
_LOCAL = threading.local()
_WRITE_LOCK = threading.Lock()

# one heavy GPU job at a time (cinema video / 3D); image gen NIMs queue internally
GPU_HEAVY = threading.Semaphore(1)

TERMINAL = ("done", "failed", "cancelled")

# structured error codes
E_VALIDATION = "VALIDATION"
E_BACKEND_DOWN = "BACKEND_DOWN"
E_CENSORED = "CENSORED_BLANK"
E_JUDGE_REJECTED = "JUDGE_REJECTED"
E_TIMEOUT = "TIMEOUT"
E_CANCELLED = "CANCELLED"
E_ENGINE = "ENGINE_ERROR"
E_INTERNAL = "INTERNAL"


def _db() -> sqlite3.Connection:
    if not hasattr(_LOCAL, "conn"):
        _LOCAL.conn = sqlite3.connect(DB_PATH, timeout=30)
        _LOCAL.conn.row_factory = sqlite3.Row
        _LOCAL.conn.execute("PRAGMA journal_mode=WAL")
    return _LOCAL.conn


def init():
    with _WRITE_LOCK:
        _db().executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            model TEXT,
            brief TEXT,
            phase TEXT NOT NULL DEFAULT 'queued',
            error TEXT,
            error_code TEXT,
            cancel_requested INTEGER DEFAULT 0,
            idempotency_key TEXT UNIQUE,
            params TEXT,
            result TEXT,
            created REAL, started REAL, finished REAL
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_phase ON jobs(phase);
        """)
        _db().commit()
    recover_orphans()


def recover_orphans():
    """Jobs left 'running'/'queued' by a dead server process → failed, honestly."""
    with _WRITE_LOCK:
        _db().execute(
            "UPDATE jobs SET phase='failed', error='server restarted mid-job — retry it', "
            "error_code=?, finished=? WHERE phase IN ('running','queued')",
            (E_INTERNAL, time.time()))
        _db().commit()


def create(kind: str, model: str, brief: str, params: dict,
           idempotency_key: str = None) -> tuple[str, bool]:
    """Returns (job_id, created). If the idempotency key exists, returns the
    existing job id with created=False."""
    if idempotency_key:
        row = _db().execute("SELECT id FROM jobs WHERE idempotency_key=?",
                            (idempotency_key,)).fetchone()
        if row:
            return row["id"], False
    jid = f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    with _WRITE_LOCK:
        _db().execute(
            "INSERT INTO jobs (id, kind, model, brief, params, idempotency_key, created) "
            "VALUES (?,?,?,?,?,?,?)",
            (jid, kind, model, brief[:500], json.dumps(params), idempotency_key,
             time.time()))
        _db().commit()
    return jid, True


def set_phase(jid: str, phase: str, error: str = None, error_code: str = None,
              result: dict = None):
    with _WRITE_LOCK:
        cols, vals = ["phase=?"], [phase]
        if phase == "running":
            cols.append("started=?"); vals.append(time.time())
        if phase in TERMINAL:
            cols.append("finished=?"); vals.append(time.time())
        if error is not None:
            cols += ["error=?", "error_code=?"]; vals += [error[:500], error_code]
        if result is not None:
            cols.append("result=?"); vals.append(json.dumps(result))
        vals.append(jid)
        _db().execute(f"UPDATE jobs SET {', '.join(cols)} WHERE id=?", vals)
        _db().commit()


def get(jid: str) -> dict | None:
    row = _db().execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    for k in ("params", "result"):
        d[k] = json.loads(d[k]) if d[k] else None
    return d


def request_cancel(jid: str) -> bool:
    with _WRITE_LOCK:
        cur = _db().execute(
            "UPDATE jobs SET cancel_requested=1 WHERE id=? AND phase NOT IN "
            "('done','failed','cancelled')", (jid,))
        # cancel a queued job immediately; running jobs notice at their next checkpoint
        _db().execute(
            "UPDATE jobs SET phase='cancelled', error='cancelled by request', "
            "error_code=?, finished=? WHERE id=? AND phase='queued'",
            (E_CANCELLED, time.time(), jid))
        _db().commit()
        return cur.rowcount > 0


def cancelled(jid: str) -> bool:
    row = _db().execute("SELECT cancel_requested FROM jobs WHERE id=?", (jid,)).fetchone()
    return bool(row and row["cancel_requested"])


def checkpoint(jid: str):
    """Workers call this between stages; raises to abort if cancel was requested."""
    if cancelled(jid):
        set_phase(jid, "cancelled", "cancelled at stage checkpoint", E_CANCELLED)
        raise JobCancelled(jid)


class JobCancelled(Exception):
    pass


def recent(limit: int = 30) -> list[dict]:
    rows = _db().execute(
        "SELECT id, kind, model, brief, phase, error_code, created FROM jobs "
        "ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
