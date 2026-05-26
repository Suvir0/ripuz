"""
Tests for the single-track download feature:
  - run_track_pipeline()
  - _process_job() routing
  - API endpoint acceptance
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app import db
from app.pipeline import run_track_pipeline
from app.jobs import _process_job
from app.qobuz_cli import DownloadResult
from app.picard import PicardResult
from app.mover import MoveResult


# ── helpers ────────────────────────────────────────────────────────────────────

def _ok_download():
    return DownloadResult(success=True)


def _fail_download(msg="dl error"):
    return DownloadResult(success=False, error_message=msg)


def _ok_picard():
    return PicardResult(success=True)


def _fail_picard(msg="picard error"):
    return PicardResult(success=False, error_message=msg)


def _ok_move(n: int = 1):
    return MoveResult(moved=[Path(f"/music/Artist/Album/track{i}.FLAC") for i in range(n)])


def _empty_move():
    return MoveResult()


def _one_album_dir(root: Path):
    d = root / "Artist" / "Album"
    d.mkdir(parents=True, exist_ok=True)
    return [d]


# ── run_track_pipeline() ───────────────────────────────────────────────────────

def test_track_pipeline_success(tmp_dirs):
    job_id = db.create_job("track", "https://play.qobuz.com/track/123456")
    album_dirs = _one_album_dir(tmp_dirs / "downloads")

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 1, "artists": ["Artist"], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        ok = run_track_pipeline(job_id, "https://play.qobuz.com/track/123456")

    assert ok is True
    assert db.get_job(job_id)["status"] == "done"


def test_track_pipeline_download_failure():
    job_id = db.create_job("track", "https://play.qobuz.com/track/111")
    with patch("app.pipeline.run_download", return_value=_fail_download("geo-blocked")):
        ok = run_track_pipeline(job_id, "https://play.qobuz.com/track/111")

    assert ok is False
    assert db.get_job(job_id)["status"] == "error"


def test_track_pipeline_picard_failure_still_moves(tmp_dirs):
    job_id = db.create_job("track", "https://play.qobuz.com/track/222")
    album_dirs = _one_album_dir(tmp_dirs / "downloads")

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_fail_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 1, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        ok = run_track_pipeline(job_id, "https://play.qobuz.com/track/222")

    assert ok is True
    assert db.get_job(job_id)["status"] == "done"


def test_track_pipeline_no_files_moved_is_error(tmp_dirs):
    job_id = db.create_job("track", "https://play.qobuz.com/track/333")
    album_dirs = _one_album_dir(tmp_dirs / "downloads")

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_empty_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 0, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        ok = run_track_pipeline(job_id, "https://play.qobuz.com/track/333")

    assert ok is False
    assert db.get_job(job_id)["status"] == "error"


def test_track_pipeline_logs_downloading_and_tagging(tmp_dirs):
    job_id = db.create_job("track", "https://play.qobuz.com/track/444")
    album_dirs = _one_album_dir(tmp_dirs / "downloads")

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 1, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        run_track_pipeline(job_id, "https://play.qobuz.com/track/444")

    log = db.get_job(job_id)["log"]
    assert "downloading" in log.lower()
    assert "tagging" in log.lower()


def test_track_pipeline_calls_picard_once(tmp_dirs):
    job_id = db.create_job("track", "https://play.qobuz.com/track/555")
    album_dirs = _one_album_dir(tmp_dirs / "downloads")
    picard_calls = []

    def record_picard(source_dir, **kwargs):
        picard_calls.append(source_dir)
        return _ok_picard()

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", side_effect=record_picard), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 1, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        run_track_pipeline(job_id, "https://play.qobuz.com/track/555")

    assert len(picard_calls) == 1


def test_track_pipeline_downloads_track_url(tmp_dirs):
    track_url = "https://play.qobuz.com/track/987654"
    job_id = db.create_job("track", track_url)
    album_dirs = _one_album_dir(tmp_dirs / "downloads")
    captured_urls = []

    def record_download(url, **kwargs):
        captured_urls.append(url)
        return _ok_download()

    with patch("app.pipeline.run_download", side_effect=record_download), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 1, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        run_track_pipeline(job_id, track_url)

    assert captured_urls == [track_url]


def test_track_pipeline_skipped_file_is_done_with_warnings(tmp_dirs):
    job_id = db.create_job("track", "https://play.qobuz.com/track/666")
    album_dirs = _one_album_dir(tmp_dirs / "downloads")
    skipped_move = MoveResult(
        moved=[Path("/music/Artist/Album/track0.FLAC")],
        skipped=[Path("/music/Artist/Album/track1.FLAC")],
    )

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=skipped_move), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 1, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        ok = run_track_pipeline(job_id, "https://play.qobuz.com/track/666")

    assert ok is True
    assert db.get_job(job_id)["status"] == "done_with_warnings"


# ── _process_job() routing ─────────────────────────────────────────────────────

def test_process_job_routes_track():
    from unittest.mock import ANY
    job_id = db.create_job("track", "https://play.qobuz.com/track/abc")
    job = db.get_job(job_id)
    with patch("app.jobs.run_track_pipeline", return_value=True) as mock_fn:
        _process_job(job)
    mock_fn.assert_called_once_with(job_id, "https://play.qobuz.com/track/abc", ANY)


# ── API endpoint ───────────────────────────────────────────────────────────────

def test_api_create_track_job():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/jobs",
        json={"type": "track", "url": "https://play.qobuz.com/track/api_test"},
    )
    assert resp.status_code == 200
    assert "job_id" in resp.json()


def test_api_track_job_requires_url():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/jobs", json={"type": "track", "url": ""})
    assert resp.status_code == 400
