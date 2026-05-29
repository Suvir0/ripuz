"""
Tests for the stale-job purge feature (feature 6):
  - db.purge_stale_jobs() marks stuck active jobs as error after 12 h
  - Worker loop calls purge on each iteration
"""
import threading
import time
from unittest.mock import patch, MagicMock

import pytest

from app import db
from app.jobs import _worker_loop


# ── helpers ────────────────────────────────────────────────────────────────────

def _age_job(job_id: int, hours: float):
    """Back-date updated_at for a job by the given number of hours."""
    import app.config as cfg
    import sqlite3
    conn = sqlite3.connect(cfg.DB_FILE)
    conn.execute(
        "UPDATE jobs SET updated_at = datetime('now', ?) WHERE id = ?",
        (f"-{hours} hours", job_id),
    )
    conn.commit()
    conn.close()


# ── db.purge_stale_jobs() ──────────────────────────────────────────────────────

def test_purge_returns_empty_when_no_stale_jobs():
    db.create_job("track", "https://play.qobuz.com/track/1")
    purged = db.purge_stale_jobs(cutoff_hours=12)
    assert purged == []


def test_purge_ignores_fresh_active_jobs():
    job_id = db.create_job("track", "https://play.qobuz.com/track/2")
    db.update_job(job_id, status="downloading")
    # updated_at is just now — should not be purged
    purged = db.purge_stale_jobs(cutoff_hours=12)
    assert job_id not in purged
    assert db.get_job(job_id)["status"] == "downloading"


def test_purge_marks_stale_active_job_as_error():
    job_id = db.create_job("track", "https://play.qobuz.com/track/3")
    db.update_job(job_id, status="downloading")
    _age_job(job_id, hours=13)

    purged = db.purge_stale_jobs(cutoff_hours=12)

    assert job_id in purged
    assert db.get_job(job_id)["status"] == "error"


def test_purge_appends_message_to_log():
    job_id = db.create_job("track", "https://play.qobuz.com/track/4")
    db.update_job(job_id, status="tagging")
    _age_job(job_id, hours=13)

    db.purge_stale_jobs(cutoff_hours=12)

    log = db.get_job(job_id)["log"]
    assert "purged" in log.lower()


def test_purge_handles_all_active_statuses():
    active_statuses = ["queued", "resolving", "downloading", "tagging", "verifying"]
    job_ids = []
    for status in active_statuses:
        job_id = db.create_job("track", f"https://play.qobuz.com/track/{status}")
        db.update_job(job_id, status=status)
        _age_job(job_id, hours=13)
        job_ids.append(job_id)

    purged = db.purge_stale_jobs(cutoff_hours=12)

    assert set(job_ids) == set(purged)
    for jid in job_ids:
        assert db.get_job(jid)["status"] == "error"


def test_purge_does_not_touch_done_jobs():
    job_id = db.create_job("track", "https://play.qobuz.com/track/5")
    db.update_job(job_id, status="done")
    _age_job(job_id, hours=13)

    purged = db.purge_stale_jobs(cutoff_hours=12)

    assert job_id not in purged
    assert db.get_job(job_id)["status"] == "done"


def test_purge_does_not_touch_error_jobs():
    job_id = db.create_job("track", "https://play.qobuz.com/track/6")
    db.update_job(job_id, status="error")
    _age_job(job_id, hours=13)

    purged = db.purge_stale_jobs(cutoff_hours=12)

    assert job_id not in purged


def test_purge_does_not_touch_done_with_warnings():
    job_id = db.create_job("track", "https://play.qobuz.com/track/7")
    db.update_job(job_id, status="done_with_warnings")
    _age_job(job_id, hours=13)

    purged = db.purge_stale_jobs(cutoff_hours=12)

    assert job_id not in purged


def test_purge_respects_custom_cutoff():
    job_id = db.create_job("track", "https://play.qobuz.com/track/8")
    db.update_job(job_id, status="downloading")
    _age_job(job_id, hours=2)

    # 2-hour cutoff — should catch it
    purged = db.purge_stale_jobs(cutoff_hours=1)
    assert job_id in purged

    # 12-hour cutoff would not have caught it
    job_id2 = db.create_job("track", "https://play.qobuz.com/track/9")
    db.update_job(job_id2, status="downloading")
    _age_job(job_id2, hours=2)

    purged2 = db.purge_stale_jobs(cutoff_hours=12)
    assert job_id2 not in purged2


def test_purge_returns_all_stale_ids():
    ids = []
    for i in range(3):
        jid = db.create_job("track", f"https://play.qobuz.com/track/multi{i}")
        db.update_job(jid, status="downloading")
        _age_job(jid, hours=13)
        ids.append(jid)

    purged = db.purge_stale_jobs(cutoff_hours=12)

    assert set(ids).issubset(set(purged))


# ── worker loop integration ────────────────────────────────────────────────────

def test_worker_loop_calls_purge_stale_jobs():
    stop = threading.Event()
    purge_calls = []

    def purge_and_stop():
        purge_calls.append(1)
        stop.set()  # stop after first iteration
        return []

    with patch("app.jobs.db.purge_stale_jobs", side_effect=purge_and_stop), \
         patch("app.jobs.db.get_runnable_jobs", return_value=[]):
        _worker_loop(stop, poll_interval=0)

    assert len(purge_calls) >= 1


def test_worker_loop_logs_purged_jobs(caplog):
    """When purge_stale_jobs returns IDs the worker must log a warning for them."""
    import logging
    stop = threading.Event()
    purged_ids = [42, 43]

    def purge_and_stop():
        stop.set()   # stop after this first (and only) iteration
        return purged_ids

    with patch("app.jobs.db.purge_stale_jobs", side_effect=purge_and_stop), \
         patch("app.jobs.db.get_runnable_jobs", return_value=[]):
        with caplog.at_level(logging.WARNING, logger="app.jobs"):
            _worker_loop(stop, poll_interval=0)

    # The worker must emit a warning mentioning the purged IDs.
    assert any("42" in r.message or "43" in r.message for r in caplog.records), (
        f"Expected purge warning in logs, got: {[r.message for r in caplog.records]}"
    )
