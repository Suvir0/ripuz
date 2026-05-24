"""
Job queue backed by SQLite + a single background worker thread.
The worker dequeues jobs in FIFO order and runs the appropriate pipeline.
"""
import logging
import threading
import time

from app import db
from app.pipeline import (
    run_playlist_pipeline,
    run_expand_albums_pipeline,
    run_track_pipeline,
    run_album_pipeline,
    run_discography_pipeline,
    run_expand_discographies_pipeline,
)

logger = logging.getLogger(__name__)

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()


def enqueue(job_type: str, url: str) -> int:
    job_id = db.create_job(job_type, url)
    logger.info("Enqueued job #%d type=%s url=%s", job_id, job_type, url)
    return job_id


def _process_job(job: dict):
    job_id = job["id"]
    job_type = job["type"]
    url = job["url"]
    logger.info("Processing job #%d type=%s", job_id, job_type)
    try:
        if job_type == "playlist":
            run_playlist_pipeline(job_id, url)
        elif job_type == "expand_albums":
            run_expand_albums_pipeline(job_id, url)
        elif job_type == "track":
            run_track_pipeline(job_id, url)
        elif job_type == "album":
            run_album_pipeline(job_id, url)
        elif job_type == "discography":
            run_discography_pipeline(job_id, url)
        elif job_type == "expand_discographies":
            run_expand_discographies_pipeline(job_id, url)
        else:
            db.update_job(job_id, status="error")
            db.append_job_log(job_id, f"unknown job type: {job_type}\n")
    except Exception as exc:
        logger.exception("Unhandled error in job #%d", job_id)
        db.update_job(job_id, status="error")
        db.append_job_log(job_id, f"unhandled error: {exc}\n")


def _worker_loop(stop_event: threading.Event, poll_interval: float = 2.0):
    logger.info("Job worker started")
    while not stop_event.is_set():
        try:
            purged = db.purge_stale_jobs()
            if purged:
                logger.warning("Purged %d stale job(s): %s", len(purged), purged)
            queued = db.get_queued_jobs()
            for job in queued:
                if stop_event.is_set():
                    break
                _process_job(job)
        except Exception as exc:
            logger.exception("Worker loop error: %s", exc)
        stop_event.wait(poll_interval)
    logger.info("Job worker stopped")


def start_worker(poll_interval: float = 2.0):
    global _worker_thread, _stop_event
    _stop_event.clear()
    _worker_thread = threading.Thread(
        target=_worker_loop,
        args=(_stop_event, poll_interval),
        daemon=True,
        name="ripuz-worker",
    )
    _worker_thread.start()
    logger.info("Worker thread started")


def stop_worker():
    global _stop_event
    _stop_event.set()
    if _worker_thread:
        _worker_thread.join(timeout=5)
