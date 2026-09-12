"""Library store: SQLite by default, PostgreSQL + pgvector when a DSN is given.

One schema, two drivers. SQLite is zero-setup for a single machine; Postgres lets
several worker nodes (5090, DGX Sparks) claim review work from one queue with
FOR UPDATE SKIP LOCKED. Thumbnails live in the store so a remote worker never
needs the source filesystem.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np

STAGES = ("embed", "faces", "ocr", "review_fast", "review_deep")
FACE_DIM = 512


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _ddl(pg: bool, embed_dim: int) -> list[str]:
    pk = "BIGSERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
    blob = "BYTEA" if pg else "BLOB"
    vec = (lambda d: f"vector({d})") if pg else (lambda d: "BLOB")
    return [
        f"""CREATE TABLE IF NOT EXISTS assets (
            id {pk}, path TEXT UNIQUE NOT NULL, sha256 TEXT NOT NULL, size BIGINT,
            mtime DOUBLE PRECISION, width INT, height INT, format TEXT, taken_at TEXT,
            exif TEXT, phash TEXT, dhash TEXT, dup_of BIGINT, cluster_id BIGINT,
            added_at TEXT NOT NULL)""",
        "CREATE INDEX IF NOT EXISTS assets_sha ON assets(sha256)",
        "CREATE INDEX IF NOT EXISTS assets_cluster ON assets(cluster_id)",
        f"CREATE TABLE IF NOT EXISTS thumbs (asset_id BIGINT PRIMARY KEY, jpeg {blob} NOT NULL)",
        f"""CREATE TABLE IF NOT EXISTS embeddings (
            asset_id BIGINT NOT NULL, model TEXT NOT NULL, dim INT NOT NULL,
            vec {vec(embed_dim)} NOT NULL, PRIMARY KEY (asset_id, model))""",
        f"""CREATE TABLE IF NOT EXISTS faces (
            id {pk}, asset_id BIGINT NOT NULL, bbox TEXT NOT NULL, score REAL,
            vec {vec(FACE_DIM)} NOT NULL, person_id BIGINT)""",
        "CREATE INDEX IF NOT EXISTS faces_asset ON faces(asset_id)",
        f"CREATE TABLE IF NOT EXISTS persons (id {pk}, label TEXT, centroid {vec(FACE_DIM)}, n INT DEFAULT 0)",
        """CREATE TABLE IF NOT EXISTS ocr (asset_id BIGINT PRIMARY KEY, text TEXT,
            mean_conf REAL, engine TEXT, created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS reviews (asset_id BIGINT NOT NULL, tier TEXT NOT NULL,
            model TEXT, result TEXT NOT NULL, confidence REAL, worker TEXT, ms INT,
            created_at TEXT, PRIMARY KEY (asset_id, tier))""",
        f"""CREATE TABLE IF NOT EXISTS queue (id {pk}, asset_id BIGINT NOT NULL,
            stage TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', worker TEXT,
            claimed_at TEXT, error TEXT, UNIQUE (asset_id, stage))""",
        "CREATE INDEX IF NOT EXISTS queue_pending ON queue(stage, status)",
        f"""CREATE TABLE IF NOT EXISTS proposals (id {pk}, asset_id BIGINT NOT NULL,
            action TEXT NOT NULL, dest TEXT, album TEXT, reason TEXT,
            status TEXT NOT NULL DEFAULT 'pending', created_at TEXT, applied_at TEXT,
            UNIQUE (asset_id, action))""",
        f"CREATE TABLE IF NOT EXISTS ledger (id {pk}, ts TEXT NOT NULL, event TEXT NOT NULL, detail TEXT)",
        """CREATE TABLE IF NOT EXISTS albums (asset_id BIGINT PRIMARY KEY, album TEXT NOT NULL,
            source TEXT NOT NULL, group_id INT)""",
    ]


class Store:
    def __init__(self, target: str | Path, embed_dim: int = 1152):
        self.embed_dim = embed_dim
        self.pg = str(target).startswith("postgres")
        if self.pg:
            import psycopg
            from pgvector.psycopg import register_vector
            self.con = psycopg.connect(str(target), autocommit=False)
            with self.con.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            self.con.commit()
            register_vector(self.con)
        else:
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            self.con = sqlite3.connect(str(target), timeout=60)
            self.con.execute("PRAGMA journal_mode=WAL")
            self.con.execute("PRAGMA busy_timeout=60000")
        for stmt in _ddl(self.pg, embed_dim):
            self._exec(stmt)
        self.con.commit()

    # ---- low-level -------------------------------------------------------
    def _q(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.pg else sql

    def _exec(self, sql: str, params: tuple = ()):
        if self.pg:
            cur = self.con.cursor()
            cur.execute(self._q(sql), params)
            return cur
        return self.con.execute(sql, params)

    def fetchall(self, sql: str, params: tuple = ()) -> list[tuple]:
        return list(self._exec(sql, params).fetchall())

    def fetchone(self, sql: str, params: tuple = ()):
        return self._exec(sql, params).fetchone()

    def execute(self, sql: str, params: tuple = ()) -> None:
        self._exec(sql, params)

    def commit(self) -> None:
        self.con.commit()

    def close(self) -> None:
        self.con.close()

    @contextmanager
    def tx(self):
        try:
            yield self
            self.con.commit()
        except Exception:
            self.con.rollback()
            raise

    def _vec_in(self, vec: np.ndarray):
        arr = np.asarray(vec, dtype=np.float32)
        return arr if self.pg else arr.tobytes()

    def _vec_out(self, raw) -> np.ndarray:
        if self.pg:
            return np.asarray(raw, dtype=np.float32)
        return np.frombuffer(raw, dtype=np.float32)

    # ---- assets ----------------------------------------------------------
    def upsert_asset(self, row: dict) -> int:
        existing = self.fetchone("SELECT id, sha256 FROM assets WHERE path = ?", (row["path"],))
        if existing and existing[1] == row["sha256"]:
            return int(existing[0])
        cols = ("path", "sha256", "size", "mtime", "width", "height", "format",
                "taken_at", "exif", "phash", "dhash")
        vals = tuple(row.get(c) for c in cols)
        if existing:
            sets = ", ".join(f"{c} = ?" for c in cols[1:])
            self.execute(f"UPDATE assets SET {sets}, dup_of = NULL, cluster_id = NULL "
                         "WHERE id = ?", vals[1:] + (existing[0],))
            aid = int(existing[0])
            self.execute("DELETE FROM queue WHERE asset_id = ?", (aid,))
        else:
            placeholders = ", ".join("?" for _ in cols)
            if self.pg:
                aid = self.fetchone(
                    f"INSERT INTO assets ({', '.join(cols)}, added_at) VALUES ({placeholders}, ?) "
                    "RETURNING id", vals + (_now(),))[0]
            else:
                aid = self._exec(
                    f"INSERT INTO assets ({', '.join(cols)}, added_at) VALUES ({placeholders}, ?)",
                    vals + (_now(),)).lastrowid
        for stage in STAGES:
            self.execute("INSERT INTO queue (asset_id, stage, status) VALUES (?, ?, 'pending') "
                         "ON CONFLICT (asset_id, stage) DO NOTHING", (aid, stage))
        return int(aid)

    def put_thumb(self, asset_id: int, jpeg: bytes) -> None:
        self.execute("INSERT INTO thumbs (asset_id, jpeg) VALUES (?, ?) "
                     "ON CONFLICT (asset_id) DO UPDATE SET jpeg = excluded.jpeg",
                     (asset_id, jpeg))

    def get_thumb(self, asset_id: int) -> bytes | None:
        row = self.fetchone("SELECT jpeg FROM thumbs WHERE asset_id = ?", (asset_id,))
        return bytes(row[0]) if row else None

    def asset(self, asset_id: int) -> dict | None:
        row = self.fetchone("SELECT id, path, sha256, size, width, height, format, taken_at, "
                            "phash, dhash, dup_of, cluster_id FROM assets WHERE id = ?", (asset_id,))
        if not row:
            return None
        keys = ("id", "path", "sha256", "size", "width", "height", "format", "taken_at",
                "phash", "dhash", "dup_of", "cluster_id")
        return dict(zip(keys, row))

    def assets(self, representatives_only: bool = False) -> list[dict]:
        where = "WHERE dup_of IS NULL" if representatives_only else ""
        rows = self.fetchall("SELECT id, path, sha256, size, width, height, format, taken_at, "
                             f"phash, dhash, dup_of, cluster_id FROM assets {where} ORDER BY id")
        keys = ("id", "path", "sha256", "size", "width", "height", "format", "taken_at",
                "phash", "dhash", "dup_of", "cluster_id")
        return [dict(zip(keys, r)) for r in rows]

    def set_cluster(self, asset_id: int, cluster_id: int, dup_of: int | None) -> None:
        self.execute("UPDATE assets SET cluster_id = ?, dup_of = ? WHERE id = ?",
                     (cluster_id, dup_of, asset_id))

    # ---- embeddings ------------------------------------------------------
    def put_embedding(self, asset_id: int, model: str, vec: np.ndarray) -> None:
        self.execute("INSERT INTO embeddings (asset_id, model, dim, vec) VALUES (?, ?, ?, ?) "
                     "ON CONFLICT (asset_id, model) DO UPDATE SET vec = excluded.vec, dim = excluded.dim",
                     (asset_id, model, int(len(vec)), self._vec_in(vec)))

    def embeddings(self, model: str, ids: list[int] | None = None) -> tuple[list[int], np.ndarray]:
        sql = "SELECT asset_id, vec FROM embeddings WHERE model = ?"
        rows = self.fetchall(sql + " ORDER BY asset_id", (model,))
        if ids is not None:
            keep = set(ids)
            rows = [r for r in rows if r[0] in keep]
        if not rows:
            return [], np.zeros((0, self.embed_dim), dtype=np.float32)
        return [int(r[0]) for r in rows], np.stack([self._vec_out(r[1]) for r in rows])

    def nearest(self, model: str, query: np.ndarray, k: int, exclude_dups: bool = True) -> list[tuple[int, float]]:
        if self.pg:
            join = "JOIN assets a ON a.id = e.asset_id AND a.dup_of IS NULL" if exclude_dups else ""
            rows = self.fetchall(
                f"SELECT e.asset_id, 1 - (e.vec <=> ?) FROM embeddings e {join} "
                "WHERE e.model = ? ORDER BY e.vec <=> ? LIMIT ?",
                (self._vec_in(query), model, self._vec_in(query), k))
            return [(int(a), float(s)) for a, s in rows]
        ids, mat = self.embeddings(model)
        if exclude_dups:
            dups = {r[0] for r in self.fetchall("SELECT id FROM assets WHERE dup_of IS NOT NULL")}
            keep = [i for i, a in enumerate(ids) if a not in dups]
            ids, mat = [ids[i] for i in keep], mat[keep] if keep else mat[:0]
        if not ids:
            return []
        scores = mat @ np.asarray(query, dtype=np.float32)
        order = np.argsort(-scores)[:k]
        return [(ids[i], float(scores[i])) for i in order]

    # ---- faces -----------------------------------------------------------
    def put_face(self, asset_id: int, bbox: list[float], score: float, vec: np.ndarray,
                 person_id: int | None) -> None:
        self.execute("INSERT INTO faces (asset_id, bbox, score, vec, person_id) VALUES (?, ?, ?, ?, ?)",
                     (asset_id, json.dumps([round(float(v), 1) for v in bbox]), float(score),
                      self._vec_in(vec), person_id))

    def persons(self) -> list[tuple[int, str | None, np.ndarray, int]]:
        return [(int(i), lbl, self._vec_out(c), int(n)) for i, lbl, c, n in
                self.fetchall("SELECT id, label, centroid, n FROM persons ORDER BY id")]

    def new_person(self, centroid: np.ndarray) -> int:
        if self.pg:
            return int(self.fetchone("INSERT INTO persons (centroid, n) VALUES (?, 1) RETURNING id",
                                     (self._vec_in(centroid),))[0])
        return int(self._exec("INSERT INTO persons (centroid, n) VALUES (?, 1)",
                              (self._vec_in(centroid),)).lastrowid)

    def update_person(self, person_id: int, centroid: np.ndarray, n: int) -> None:
        self.execute("UPDATE persons SET centroid = ?, n = ? WHERE id = ?",
                     (self._vec_in(centroid), n, person_id))

    def label_person(self, person_id: int, label: str) -> None:
        self.execute("UPDATE persons SET label = ? WHERE id = ?", (label, person_id))

    def people_in(self, asset_id: int) -> list[int]:
        return [int(r[0]) for r in self.fetchall(
            "SELECT DISTINCT person_id FROM faces WHERE asset_id = ? AND person_id IS NOT NULL",
            (asset_id,))]

    # ---- ocr / reviews ---------------------------------------------------
    def put_ocr(self, asset_id: int, text: str, mean_conf: float, engine: str) -> None:
        self.execute("INSERT INTO ocr (asset_id, text, mean_conf, engine, created_at) VALUES (?, ?, ?, ?, ?) "
                     "ON CONFLICT (asset_id) DO UPDATE SET text = excluded.text, mean_conf = excluded.mean_conf",
                     (asset_id, text, float(mean_conf), engine, _now()))

    def put_review(self, asset_id: int, tier: str, model: str, result: dict, worker: str, ms: int) -> None:
        self.execute("INSERT INTO reviews (asset_id, tier, model, result, confidence, worker, ms, created_at) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (asset_id, tier) DO UPDATE SET "
                     "model = excluded.model, result = excluded.result, confidence = excluded.confidence, "
                     "worker = excluded.worker, ms = excluded.ms, created_at = excluded.created_at",
                     (asset_id, tier, model, json.dumps(result), float(result.get("confidence", 0)),
                      worker, ms, _now()))

    def review(self, asset_id: int, tier: str | None = None) -> dict | None:
        """Best available review: deep wins over fast unless a tier is forced."""
        tiers = [tier] if tier else ["deep", "fast"]
        for t in tiers:
            row = self.fetchone("SELECT result FROM reviews WHERE asset_id = ? AND tier = ?", (asset_id, t))
            if row:
                return json.loads(row[0])
        return None

    # ---- queue -----------------------------------------------------------
    def claim(self, stage: str, worker: str) -> int | None:
        if self.pg:
            row = self.fetchone(
                "UPDATE queue SET status = 'running', worker = ?, claimed_at = ? WHERE id = ("
                "SELECT id FROM queue WHERE stage = ? AND status = 'pending' ORDER BY id "
                "FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING asset_id", (worker, _now(), stage))
        else:
            self.con.execute("BEGIN IMMEDIATE")
            row = self.fetchone(
                "UPDATE queue SET status = 'running', worker = ?, claimed_at = ? WHERE id = ("
                "SELECT id FROM queue WHERE stage = ? AND status = 'pending' ORDER BY id LIMIT 1) "
                "RETURNING asset_id", (worker, _now(), stage))
        self.commit()
        return int(row[0]) if row else None

    def finish(self, asset_id: int, stage: str, status: str = "done", error: str | None = None) -> None:
        self.execute("UPDATE queue SET status = ?, error = ? WHERE asset_id = ? AND stage = ?",
                     (status, error, asset_id, stage))
        self.commit()

    def skip(self, asset_id: int, stage: str, reason: str) -> None:
        self.finish(asset_id, stage, "skipped", reason)

    def requeue(self, stage: str, statuses: tuple[str, ...] = ("running", "error")) -> int:
        marks = ", ".join("?" for _ in statuses)
        cur = self._exec(f"UPDATE queue SET status = 'pending', worker = NULL, error = NULL "
                         f"WHERE stage = ? AND status IN ({marks})", (stage, *statuses))
        self.commit()
        return cur.rowcount

    def queue_counts(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {s: {} for s in STAGES}
        for stage, status, n in self.fetchall(
                "SELECT stage, status, COUNT(*) FROM queue GROUP BY stage, status"):
            out.setdefault(stage, {})[status] = int(n)
        return out

    # ---- albums ----------------------------------------------------------
    def put_album(self, asset_id: int, album: str, source: str, group_id: int | None) -> None:
        self.execute("INSERT INTO albums (asset_id, album, source, group_id) VALUES (?, ?, ?, ?) "
                     "ON CONFLICT (asset_id) DO UPDATE SET album = excluded.album, "
                     "source = excluded.source, group_id = excluded.group_id",
                     (asset_id, album, source, group_id))

    def albums(self) -> dict[int, tuple[str, str]]:
        return {int(a): (name, src) for a, name, src in
                self.fetchall("SELECT asset_id, album, source FROM albums")}

    def clear_albums(self) -> None:
        self.execute("DELETE FROM albums")

    # ---- proposals / ledger ---------------------------------------------
    def put_proposal(self, asset_id: int, action: str, dest: str | None, album: str | None,
                     reason: str) -> None:
        self.execute("INSERT INTO proposals (asset_id, action, dest, album, reason, status, created_at) "
                     "VALUES (?, ?, ?, ?, ?, 'pending', ?) ON CONFLICT (asset_id, action) DO UPDATE SET "
                     "dest = excluded.dest, album = excluded.album, reason = excluded.reason, "
                     "status = CASE WHEN proposals.status = 'applied' THEN 'applied' ELSE 'pending' END",
                     (asset_id, action, dest, album, reason, _now()))

    def proposals(self, status: str | None = None, album: str | None = None) -> list[dict]:
        where, params = [], []
        if status:
            where.append("p.status = ?"); params.append(status)
        if album:
            where.append("p.album = ?"); params.append(album)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        rows = self.fetchall("SELECT p.id, p.asset_id, a.path, p.action, p.dest, p.album, p.reason, "
                             f"p.status FROM proposals p JOIN assets a ON a.id = p.asset_id {clause} "
                             "ORDER BY p.album, p.id", tuple(params))
        keys = ("id", "asset_id", "path", "action", "dest", "album", "reason", "status")
        return [dict(zip(keys, r)) for r in rows]

    def set_proposal_status(self, ids: list[int], status: str) -> int:
        n = 0
        for pid in ids:
            cur = self._exec("UPDATE proposals SET status = ?, applied_at = ? WHERE id = ? "
                             "AND status <> 'applied'",
                             (status, _now() if status == "applied" else None, pid))
            n += cur.rowcount
        return n

    def log(self, event: str, detail: dict) -> None:
        self.execute("INSERT INTO ledger (ts, event, detail) VALUES (?, ?, ?)",
                     (_now(), event, json.dumps(detail, default=str)))

    def counts(self) -> dict[str, int]:
        c = lambda sql: int(self.fetchone(sql)[0])  # noqa: E731
        return {
            "assets": c("SELECT COUNT(*) FROM assets"),
            "duplicates": c("SELECT COUNT(*) FROM assets WHERE dup_of IS NOT NULL"),
            "clusters": c("SELECT COUNT(DISTINCT cluster_id) FROM assets WHERE cluster_id IS NOT NULL"),
            "embeddings": c("SELECT COUNT(*) FROM embeddings"),
            "faces": c("SELECT COUNT(*) FROM faces"),
            "persons": c("SELECT COUNT(*) FROM persons"),
            "ocr": c("SELECT COUNT(*) FROM ocr"),
            "reviews_fast": c("SELECT COUNT(*) FROM reviews WHERE tier = 'fast'"),
            "reviews_deep": c("SELECT COUNT(*) FROM reviews WHERE tier = 'deep'"),
            "albums": c("SELECT COUNT(DISTINCT album) FROM albums"),
            "proposals_pending": c("SELECT COUNT(*) FROM proposals WHERE status = 'pending'"),
            "proposals_applied": c("SELECT COUNT(*) FROM proposals WHERE status = 'applied'"),
        }
