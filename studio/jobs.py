"""Durable job store for Beast Studio (P0).

SQLite-backed lifecycle: queued → running → done | failed | cancelled.
Survives server restarts (boot recovery marks orphaned running jobs failed and
reclaims their GPU leases). Provides idempotency keys, cancellation flags,
durable heavy/light GPU leases with resource classes, server-enforced per-job
deadlines, and structured error codes.
"""
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import resource_guard

DB_PATH = Path(__file__).resolve().parent / "jobs.db"
_LOCAL = threading.local()
_WRITE_LOCK = threading.Lock()

# ---- GPU scheduling (durable, SQLite-backed) ----
# Resource classes: 'heavy' (cinema video / 3D — exclusive, nothing else may
# run) and 'light' (image generation — bounded concurrency, blocked entirely
# while a heavy lease is held). One physical RTX 5090 today.
GPU_RESOURCE = "rtx5090"
LIGHT_CONCURRENCY = 2      # fixed default per design review §1 (not VRAM-probed)
LEASE_STALE_S = 30         # heartbeat older than this = crashed holder, reclaim
LEASE_POLL_S = 0.5
EXTERNAL_GPU_GUARD = True

# server-enforced per-job deadlines (seconds, from creation — includes queue
# wait). Exceeding one fails the job with E_TIMEOUT at the next checkpoint or
# lease wait; it never triggers cloud-credit retries.
DEADLINES = {"create": 1800, "refine": 900, "animate": 3600, "3d": 2400,
             "unreal": 1800}
DEFAULT_DEADLINE_S = 1800

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
            progress TEXT,
            created REAL, started REAL, finished REAL
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_phase ON jobs(phase);
        CREATE TABLE IF NOT EXISTS gpu_leases (
            resource TEXT NOT NULL,
            holder TEXT NOT NULL,        -- job_id or job_id:slot
            job_id TEXT NOT NULL,
            kind TEXT NOT NULL,          -- 'heavy' | 'light'
            acquired REAL NOT NULL,
            heartbeat REAL NOT NULL,
            PRIMARY KEY (resource, holder)
        );
        """)
        _migrate()
        _db().commit()
    recover_orphans()


def _migrate():
    """Idempotent schema migration for DBs created before a column existed.
    Caller holds _WRITE_LOCK."""
    cols = {r["name"] for r in _db().execute("PRAGMA table_info(jobs)")}
    if "progress" not in cols:
        _db().execute("ALTER TABLE jobs ADD COLUMN progress TEXT")
    if "deadline" not in cols:
        _db().execute("ALTER TABLE jobs ADD COLUMN deadline REAL")


def recover_orphans():
    """Jobs left 'running'/'queued' by a dead server process → failed, honestly.
    Their GPU leases are reclaimed with them — on boot no worker threads exist,
    so every lease row is an orphan by definition (single-server design)."""
    with _WRITE_LOCK:
        _db().execute(
            "UPDATE jobs SET phase='failed', error='server restarted mid-job — retry it', "
            "error_code=?, finished=? WHERE phase IN ('running','queued')",
            (E_INTERNAL, time.time()))
        _db().execute("DELETE FROM gpu_leases")
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
    now = time.time()
    with _WRITE_LOCK:
        _db().execute(
            "INSERT INTO jobs (id, kind, model, brief, params, idempotency_key, "
            "created, deadline) VALUES (?,?,?,?,?,?,?,?)",
            (jid, kind, model, brief[:500], json.dumps(params), idempotency_key,
             now, now + DEADLINES.get(kind, DEFAULT_DEADLINE_S)))
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
        # terminal monotonicity: a terminal row's outcome is immutable
        guard = " AND phase NOT IN ('done','failed','cancelled')" \
            if phase in TERMINAL else ""
        _db().execute(f"UPDATE jobs SET {', '.join(cols)} WHERE id=?{guard}", vals)
        _db().commit()


def get(jid: str) -> dict | None:
    row = _db().execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    for k in ("params", "result", "progress"):
        d[k] = json.loads(d[k]) if d[k] else None
    return d


def update_progress(jid: str, **updates) -> dict:
    """THE single authoritative writer of mutable job state. Merges `updates`
    into the row's progress JSON and mirrors coarse lifecycle (running/done/
    failed/cancelled + timestamps, error codes, result) into the row columns —
    one lock, one transaction, no second store. Returns the merged snapshot.
    status.json on disk is a derived export written by the server AFTER this,
    never read back."""
    with _WRITE_LOCK:
        row = _db().execute(
            "SELECT progress, phase, cancel_requested FROM jobs WHERE id=?",
            (jid,)).fetchone()
        snap = json.loads(row["progress"]) if row and row["progress"] else {}
        snap.update(updates)
        if row is None:  # no such job — nothing durable to write to
            return snap
        # TERMINAL MONOTONICITY: once the row is done/failed/cancelled, later
        # worker writes may add diagnostics to progress but can never change
        # the outcome — the terminal phase is immutable.
        if row["phase"] in TERMINAL:
            snap["phase"] = row["phase"]
            _db().execute("UPDATE jobs SET progress=? WHERE id=?",
                          (json.dumps(snap), jid))
            _db().commit()
            return snap
        phase = updates.get("phase")
        # a racing 'done' loses to a cancel request that already landed.
        # POLICY: 'failed' is deliberately NOT converted — a genuine failure
        # that raced a cancel keeps its failure identity and error detail
        # (more informative than 'cancelled'; interrupt-caused errors are
        # already classified as cancelled by the backends' own cancel checks).
        if phase == "done" and row["cancel_requested"]:
            phase = "cancelled"
            snap["phase"] = "cancelled"
            snap.setdefault("error", "cancelled by request")
        cols, vals = ["progress=?"], [json.dumps(snap)]
        if phase in ("generating", "judging", "improving", "grading") \
                and row["phase"] == "queued":
            cols += ["phase=?", "started=?"]
            vals += ["running", time.time()]
        elif phase == "done":
            result = {k: v for k, v in snap.items()
                      if k in ("final", "winner", "ue_asset", "video", "glb",
                               "upscaled")}
            cols += ["phase=?", "finished=?", "result=?"]
            vals += ["done", time.time(), json.dumps(result)]
        elif phase == "failed":
            err = snap.get("error") or "unknown"
            code = snap.get("error_code") or (
                E_CENSORED if "blank frame" in err else
                E_JUDGE_REJECTED if "rejected by judge" in err else
                E_BACKEND_DOWN if "not answering" in err else E_ENGINE)
            cols += ["phase=?", "finished=?", "error=?", "error_code=?"]
            vals += ["failed", time.time(), err[:500], code]
        elif phase == "cancelled":
            cols += ["phase=?", "finished=?", "error=?", "error_code=?"]
            vals += ["cancelled", time.time(),
                     (snap.get("error") or "cancelled by request")[:500],
                     E_CANCELLED]
        vals.append(jid)
        _db().execute(f"UPDATE jobs SET {', '.join(cols)} WHERE id=?", vals)
        _db().commit()
    return snap


def get_status(jid: str) -> dict | None:
    """Authoritative merged status view: the progress snapshot overlaid with
    the row's coarse truth. A terminal row phase (done/failed/cancelled) always
    wins over a stale sub-phase — this is what makes restart recovery visible
    to clients without any status.json involvement."""
    j = get(jid)
    if not j:
        return None
    s = dict(j["progress"] or {})
    s.setdefault("id", jid)
    s.setdefault("kind", j["kind"])
    if j["brief"]:
        s.setdefault("brief", j["brief"])
    s["error_code"] = j["error_code"]
    if j["phase"] in TERMINAL:
        # the row's terminal phase AND error win UNCONDITIONALLY — even over a
        # different terminal phase or a later straggler error written into
        # mutable progress (a terminal outcome is immutable, error included)
        s["phase"] = j["phase"]
        if j["error"]:
            s["error"] = j["error"]
    return s


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


def deadline_exceeded(jid: str) -> bool:
    """True when the job's server-enforced deadline has passed and the job has
    not already reached a terminal phase."""
    row = _db().execute("SELECT deadline, phase FROM jobs WHERE id=?",
                        (jid,)).fetchone()
    return bool(row and row["deadline"] and time.time() > row["deadline"]
                and row["phase"] not in TERMINAL)


def checkpoint(jid: str):
    """Workers call this between stages; raises to abort on cancellation or an
    exceeded deadline (cancel checked first — a cancel is the user's word)."""
    if cancelled(jid):
        set_phase(jid, "cancelled", "cancelled at stage checkpoint", E_CANCELLED)
        raise JobCancelled(jid)
    if deadline_exceeded(jid):
        set_phase(jid, "failed",
                  "exceeded the server-enforced deadline for this job kind — "
                  "retry it (no cloud fallback was attempted)", E_TIMEOUT)
        raise JobTimeout(jid)


class JobCancelled(Exception):
    pass


class JobTimeout(Exception):
    pass


# ---- durable GPU leases ----------------------------------------------------

def _try_acquire_gpu(holder: str, jid: str, kind: str,
                     resource: str = GPU_RESOURCE) -> bool:
    """One atomic grant attempt. heavy = exclusive (no lease of any kind may
    exist); light = no heavy lease AND fewer than LIGHT_CONCURRENCY lights.

    The reap + count + insert runs inside ONE `BEGIN IMMEDIATE` transaction:
    IMMEDIATE takes SQLite's write lock up front, so a second server PROCESS
    (not just a second thread — _WRITE_LOCK only covers threads) cannot read
    "resource free" from a WAL snapshot while we are granting, and grant a
    conflicting lease. On lock contention we return False and let the caller's
    poll loop retry."""
    if EXTERNAL_GPU_GUARD:
        workload = "studio_heavy" if kind == "heavy" else "studio_light"
        if not resource_guard.admission(workload)["admitted"]:
            return False
    now = time.time()
    with _WRITE_LOCK:
        con = _db()
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute("DELETE FROM gpu_leases WHERE heartbeat < ?",
                        (now - LEASE_STALE_S,))
            rows = con.execute(
                "SELECT kind, COUNT(*) AS n FROM gpu_leases WHERE resource=? "
                "GROUP BY kind", (resource,)).fetchall()
            counts = {r["kind"]: r["n"] for r in rows}
            grant = (not counts) if kind == "heavy" else (
                counts.get("heavy", 0) == 0
                and counts.get("light", 0) < LIGHT_CONCURRENCY)
            if grant:
                con.execute(
                    "INSERT OR REPLACE INTO gpu_leases "
                    "(resource, holder, job_id, kind, acquired, heartbeat) "
                    "VALUES (?,?,?,?,?,?)", (resource, holder, jid, kind, now, now))
            con.commit()
            return grant
        except sqlite3.OperationalError:
            con.rollback()   # another process holds the write lock — not granted
            return False
        except Exception:
            con.rollback()
            raise


def release_gpu(holder: str, resource: str = GPU_RESOURCE):
    with _WRITE_LOCK:
        _db().execute("DELETE FROM gpu_leases WHERE resource=? AND holder=?",
                      (resource, holder))
        _db().commit()


def gpu_heartbeat(holder: str, resource: str = GPU_RESOURCE):
    with _WRITE_LOCK:
        _db().execute(
            "UPDATE gpu_leases SET heartbeat=? WHERE resource=? AND holder=?",
            (time.time(), resource, holder))
        _db().commit()


def gpu_leases(resource: str = GPU_RESOURCE) -> list[dict]:
    rows = _db().execute(
        "SELECT holder, job_id, kind, acquired, heartbeat FROM gpu_leases "
        "WHERE resource=?", (resource,)).fetchall()
    return [dict(r) for r in rows]


@contextmanager
def gpu_lease(jid: str, kind: str, slot: str = "", resource: str = GPU_RESOURCE):
    """Blocking, cancellation- and deadline-aware GPU lease. Raises
    JobCancelled / JobTimeout from the wait loop (via checkpoint) instead of
    holding a doomed job in the queue. A background heartbeat keeps the lease
    fresh so a crashed holder is reclaimed after LEASE_STALE_S by any waiter
    or by boot recovery."""
    holder = f"{jid}:{slot}" if slot else jid
    while True:
        checkpoint(jid)  # cancel/deadline observed while WAITING, not just running
        if _try_acquire_gpu(holder, jid, kind, resource):
            break
        time.sleep(LEASE_POLL_S)
    stop = threading.Event()

    def _beat():
        while not stop.wait(LEASE_STALE_S / 6):
            gpu_heartbeat(holder, resource)

    beat = threading.Thread(target=_beat, daemon=True)
    beat.start()
    try:
        yield
    finally:
        stop.set()
        release_gpu(holder, resource)


@contextmanager
def gpu_lease_nowait(holder: str, kind: str,
                     resource: str = GPU_RESOURCE):
    """Atomically acquire a lease or yield False without waiting.

    Used by manual backend controls: a panel click must either own the GPU
    before mutating containers or return busy. The heartbeat prevents a long
    cold backend warmup from being mistaken for a stale holder.
    """
    if not _try_acquire_gpu(holder, holder, kind, resource):
        yield False
        return
    stop = threading.Event()

    def _beat():
        while not stop.wait(LEASE_STALE_S / 6):
            gpu_heartbeat(holder, resource)

    beat = threading.Thread(target=_beat, daemon=True)
    beat.start()
    try:
        yield True
    finally:
        stop.set()
        release_gpu(holder, resource)


def recent(limit: int = 30) -> list[dict]:
    rows = _db().execute(
        "SELECT id, kind, model, brief, phase, error_code, created FROM jobs "
        "ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
