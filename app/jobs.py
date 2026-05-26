"""
Job queue backed by SQLite + a single background worker thread.
The worker dequeues jobs in FIFO order and runs the appropriate pipeline.

Bulk job lifecycle (discography, expand_albums, expand_discographies):
  queued  → resolve phase (API only, no downloads) → awaiting_confirm
  confirmed → download phase (album-by-album with disk guard + cancel)

Simple jobs (track, album, playlist): queued → one-shot download.

Cancel: call cancel_job(job_id); sets the job to cancelled and terminates
any running subprocess immediately.
"""
import logging
import threading
import time

from app import db
from app.pipeline import (
    run_playlist_pipeline,
    run_track_pipeline,
    run_album_pipeline,
    run_discography_resolve,
    run_discography_download,
    run_expand_albums_resolve,
    run_expand_albums_download,
    run_expand_discographies_resolve,
    run_expand_discographies_download,
)

logger = logging.getLogger(__name__)

_BULK_TYPES = {"discography", "expand_albums", "expand_discographies"}

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()

_cancelled: set[int] = set()
_cancelled_lock = threading.Lock()


def enqueue(job_type: str, url: str) -> int:
    job_id = db.create_job(job_type, url)
    logger.info("Enqueued job #%d type=%s url=%s", job_id, job_type, url)
    return job_id


def cancel_job(job_id: int) -> None:
    """
    Cancel a job: mark it cancelled in DB, register it in the cancelled set so
    the running pipeline loop aborts, and terminate any live subprocess.
    """
    with _cancelled_lock:
        _cancelled.add(job_id)
    db.update_job(job_id, status="cancelled")
    from app.qobuz_cli import terminate_job
    terminate_job(job_id)
    logger.info("Cancel requested for job #%d", job_id)


def _cancel_check(job_id: int) -> bool:
    with _cancelled_lock:
        return job_id in _cancelled


def _process_job(job: dict):
    job_id = job["id"]
    job_type = job["type"]
    url = job["url"]
    status = job["status"]
    logger.info("Processing job #%d type=%s status=%s", job_id, job_type, status)

    cancel_check = lambda: _cancel_check(job_id)

    try:
        if job_type in _BULK_TYPES:
            if status == "queued":
                if job_type == "discography":
                    run_discography_resolve(job_id, url)
                elif job_type == "expand_albums":
                    run_expand_albums_resolve(job_id, url)
                elif job_type == "expand_discographies":
                    run_expand_discographies_resolve(job_id, url)
            elif status == "confirmed":
                if job_type == "discography":
                    run_discography_download(job_id, cancel_check)
                elif job_type == "expand_albums":
                    run_expand_albums_download(job_id, cancel_check)
                elif job_type == "expand_discographies":
                    run_expand_discographies_download(job_id, cancel_check)
        elif job_type == "playlist":
            run_playlist_pipeline(job_id, url, cancel_check)
        elif job_type == "track":
            run_track_pipeline(job_id, url, cancel_check)
        elif job_type == "album":
            run_album_pipeline(job_id, url, cancel_check)
        else:
            db.update_job(job_id, status="error")
            db.append_job_log(job_id, f"unknown job type: {job_type}\n")
    except Exception as exc:
        logger.exception("Unhandled error in job #%d", job_id)
        db.update_job(job_id, status="error")
        db.append_job_log(job_id, f"unhandled error: {exc}\n")
    finally:
        with _cancelled_lock:
            _cancelled.discard(job_id)


def _worker_loop(stop_event: threading.Event, poll_interval: float = 2.0):
    logger.info("Job worker started")
    while not stop_event.is_set():
        try:
            purged = db.purge_stale_jobs()
            if purged:
                logger.warning("Purged %d stale job(s): %s", len(purged), purged)
            runnable = db.get_runnable_jobs()
            for job in runnable:
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
