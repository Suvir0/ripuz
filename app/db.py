"""
SQLite schema and helpers.
Three tables: jobs, settings, album_cache.
"""
import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path


_DB_PATH: Path | None = None


def init_db(db_path: Path) -> None:
    global _DB_PATH
    _DB_PATH = db_path
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            type        TEXT NOT NULL,
            url         TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'queued',
            log         TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS album_cache (
            track_id  TEXT PRIMARY KEY,
            album_id  TEXT NOT NULL,
            album_url TEXT NOT NULL
        );
        """)
        # Migrate: add plan column if missing (safe for existing DBs).
        cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        if "plan" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN plan TEXT NOT NULL DEFAULT ''")


@contextmanager
def _conn():
    if _DB_PATH is None:
        raise RuntimeError("db not initialised; call init_db() first")
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ── settings ──────────────────────────────────────────────────────────────────

def get_setting(key: str, default: str | None = None) -> str | None:
    with _conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_all_settings() -> dict:
    with _conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


# ── jobs ───────────────────────────────────────────────────────────────────────

def create_job(job_type: str, url: str) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO jobs(type, url, status) VALUES(?,?,'queued')",
            (job_type, url),
        )
        return cur.lastrowid


def get_job(job_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return dict(row) if row else None


def list_jobs(limit: int = 100) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def update_job(job_id: int, **fields) -> None:
    allowed = {"status", "log"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [job_id]
    with _conn() as conn:
        conn.execute(
            f"UPDATE jobs SET {set_clause}, updated_at=datetime('now') WHERE id=?",
            values,
        )


def set_job_plan(job_id: int, plan_json: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE jobs SET plan=?, updated_at=datetime('now') WHERE id=?",
            (plan_json, job_id),
        )


def append_job_log(job_id: int, text: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE jobs SET log = log || ?, updated_at=datetime('now') WHERE id=?",
            (text, job_id),
        )


def get_queued_jobs() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status='queued' ORDER BY id ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_runnable_jobs() -> list[dict]:
    """Return jobs the worker should process: queued (resolve phase) or confirmed (download phase)."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status IN ('queued','confirmed') ORDER BY id ASC"
        ).fetchall()
    return [dict(r) for r in rows]


# ── stale job purge ───────────────────────────────────────────────────────────

# awaiting_confirm is intentionally excluded — it waits for human action, not a timeout.
_ACTIVE_STATUSES = ("queued", "resolving", "confirmed", "downloading", "tagging", "verifying", "cancelling")


def purge_stale_jobs(cutoff_hours: int = 12) -> list[int]:
    """
    Mark active jobs whose updated_at is older than cutoff_hours as 'error'.
    Returns the list of affected job IDs.
    """
    placeholders = ",".join("?" * len(_ACTIVE_STATUSES))
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT id FROM jobs WHERE status IN ({placeholders}) "
            f"AND updated_at < datetime('now', ?)",
            (*_ACTIVE_STATUSES, f"-{cutoff_hours} hours"),
        ).fetchall()
        ids = [r["id"] for r in rows]
        if ids:
            id_placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"UPDATE jobs SET status='error', updated_at=datetime('now'), "
                f"log = log || ? WHERE id IN ({id_placeholders})",
                (f"[purged] job stalled for >{cutoff_hours}h with no status change\n", *ids),
            )
    return ids


# ── album_cache ────────────────────────────────────────────────────────────────

def cache_track_album(track_id: str, album_id: str, album_url: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO album_cache(track_id, album_id, album_url) VALUES(?,?,?) "
            "ON CONFLICT(track_id) DO NOTHING",
            (track_id, album_id, album_url),
        )


def get_cached_album(track_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM album_cache WHERE track_id=?", (track_id,)
        ).fetchone()
    return dict(row) if row else None
