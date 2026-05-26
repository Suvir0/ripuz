"""
Tests for the two-phase single-artist discography pipeline:
  - run_discography_resolve()   — API only, sets awaiting_confirm + stores plan
  - run_discography_download()  — downloads album list with disk guard + cancel
  - _process_job() routing
  - API endpoint acceptance
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app import db
from app.pipeline import run_discography_resolve, run_discography_download
from app.jobs import _process_job
from app.qobuz_cli import DownloadResult
from app.picard import PicardResult
from app.mover import MoveResult


# ── helpers ────────────────────────────────────────────────────────────────────

def _ok_download():
    return DownloadResult(success=True)


def _fail_download(msg="dl error"):
    return DownloadResult(success=False, error_message=msg)


def _cancelled_download():
    return DownloadResult(success=False, cancelled=True)


def _ok_picard():
    return PicardResult(success=True)


def _fail_picard(msg="picard error"):
    return PicardResult(success=False, error_message=msg)


def _ok_move(n: int = 1):
    return MoveResult(moved=[Path(f"/music/Artist/Album/track{i}.FLAC") for i in range(n)])


def _empty_move():
    return MoveResult()


def _album_dirs(root: Path, count: int = 2):
    dirs = []
    for i in range(count):
        d = root / "Artist" / f"Album{i}"
        d.mkdir(parents=True, exist_ok=True)
        dirs.append(d)
    return dirs


def _fake_albums(count=2):
    return [
        {
            "id": f"album{i}",
            "url": f"https://play.qobuz.com/album/album{i}",
            "title": f"Album {i}",
            "artist": "Artist",
            "tracks_count": 10,
            "duration": 2400,
        }
        for i in range(count)
    ]


def _setup_plan(job_id, albums, quality=27):
    """Write a plan directly into the DB (simulates the resolve phase)."""
    plan = {
        "albums": albums,
        "skipped_existing": 0,
        "est_gb": 1.0,
        "quality": quality,
        "capped": False,
        "cap": 300,
    }
    db.set_job_plan(job_id, json.dumps(plan))
    db.update_job(job_id, status="confirmed")


# ── resolve phase ──────────────────────────────────────────────────────────────

def test_resolve_sets_awaiting_confirm():
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("discography", "https://play.qobuz.com/artist/123")
    mock_client = MagicMock()
    mock_client.discography_to_album_plan.return_value = _fake_albums(3)

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.album_already_present", return_value=False):
        ok = run_discography_resolve(job_id, "https://play.qobuz.com/artist/123")

    assert ok is True
    job = db.get_job(job_id)
    assert job["status"] == "awaiting_confirm"
    plan = json.loads(job["plan"])
    assert len(plan["albums"]) == 3


def test_resolve_skips_existing_albums():
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("discography", "https://play.qobuz.com/artist/124")
    mock_client = MagicMock()
    mock_client.discography_to_album_plan.return_value = _fake_albums(4)

    # All albums already present
    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.album_already_present", return_value=True):
        ok = run_discography_resolve(job_id, "https://play.qobuz.com/artist/124")

    assert ok is False
    plan = json.loads(db.get_job(job_id)["plan"])
    assert len(plan["albums"]) == 0
    assert plan["skipped_existing"] == 4


def test_resolve_no_token():
    import app.settings_store as ss
    ss.save_settings("")

    job_id = db.create_job("discography", "https://play.qobuz.com/artist/125")
    ok = run_discography_resolve(job_id, "https://play.qobuz.com/artist/125")

    assert ok is False
    assert db.get_job(job_id)["status"] == "error"


def test_resolve_client_exception():
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("discography", "https://play.qobuz.com/artist/126")
    mock_client = MagicMock()
    mock_client.discography_to_album_plan.side_effect = RuntimeError("network error")

    with patch("app.pipeline.make_client", return_value=mock_client):
        ok = run_discography_resolve(job_id, "https://play.qobuz.com/artist/126")

    assert ok is False
    assert db.get_job(job_id)["status"] == "error"


def test_resolve_logs_album_count():
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("discography", "https://play.qobuz.com/artist/127")
    mock_client = MagicMock()
    mock_client.discography_to_album_plan.return_value = _fake_albums(5)

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.album_already_present", return_value=False):
        run_discography_resolve(job_id, "https://play.qobuz.com/artist/127")

    log = db.get_job(job_id)["log"]
    assert "5" in log


# ── download phase ─────────────────────────────────────────────────────────────

def _big_disk(path):
    from unittest.mock import MagicMock as MM
    m = MM(); m.free = 500 * 1024**3; return m


def test_download_success(tmp_dirs):
    job_id = db.create_job("discography", "https://play.qobuz.com/artist/200")
    albums = _fake_albums(2)
    album_dirs = _album_dirs(tmp_dirs / "downloads", count=2)
    _setup_plan(job_id, albums)

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 2, "artists": ["Artist"], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"), \
         patch("app.pipeline.shutil.disk_usage", side_effect=_big_disk):
        ok = run_discography_download(job_id, lambda: False)

    assert ok is True
    assert db.get_job(job_id)["status"] == "done"


def test_download_failure_marks_done_with_warnings(tmp_dirs):
    job_id = db.create_job("discography", "https://play.qobuz.com/artist/201")
    albums = _fake_albums(2)
    album_dirs = _album_dirs(tmp_dirs / "downloads", count=2)
    _setup_plan(job_id, albums)

    def fail_one(url, **kwargs):
        if "album0" in url:
            return _fail_download("geo-blocked")
        return _ok_download()

    with patch("app.pipeline.run_download", side_effect=fail_one), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 1, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"), \
         patch("app.pipeline.shutil.disk_usage", side_effect=_big_disk):
        ok = run_discography_download(job_id, lambda: False)

    assert ok is False
    assert db.get_job(job_id)["status"] == "done_with_warnings"


def test_download_picard_failure_still_moves(tmp_dirs):
    job_id = db.create_job("discography", "https://play.qobuz.com/artist/202")
    albums = _fake_albums(1)
    album_dirs = _album_dirs(tmp_dirs / "downloads", count=1)
    _setup_plan(job_id, albums)

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_fail_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 1, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"), \
         patch("app.pipeline.shutil.disk_usage", side_effect=_big_disk):
        ok = run_discography_download(job_id, lambda: False)

    assert ok is True
    assert db.get_job(job_id)["status"] == "done"


def test_download_no_files_moved_is_error(tmp_dirs):
    job_id = db.create_job("discography", "https://play.qobuz.com/artist/203")
    albums = _fake_albums(1)
    album_dirs = _album_dirs(tmp_dirs / "downloads", count=1)
    _setup_plan(job_id, albums)

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_empty_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 0, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"), \
         patch("app.pipeline.shutil.disk_usage", side_effect=_big_disk):
        ok = run_discography_download(job_id, lambda: False)

    assert ok is False
    assert db.get_job(job_id)["status"] == "error"


def test_download_cancelled_mid_run(tmp_dirs):
    job_id = db.create_job("discography", "https://play.qobuz.com/artist/204")
    albums = _fake_albums(2)
    album_dirs = _album_dirs(tmp_dirs / "downloads", count=1)
    _setup_plan(job_id, albums)

    cancelled_after = [False]
    call_count = [0]

    def cancel_after_one(url, **kwargs):
        call_count[0] += 1
        if call_count[0] >= 1:
            cancelled_after[0] = True
        return _cancelled_download()

    with patch("app.pipeline.run_download", side_effect=cancel_after_one), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 0, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"), \
         patch("app.pipeline.shutil.disk_usage", side_effect=_big_disk):
        ok = run_discography_download(job_id, lambda: cancelled_after[0])

    assert ok is False
    assert db.get_job(job_id)["status"] == "cancelled"


def test_download_disk_guard_aborts(tmp_dirs):
    job_id = db.create_job("discography", "https://play.qobuz.com/artist/205")
    albums = _fake_albums(1)
    _setup_plan(job_id, albums)

    def low_disk(path):
        from unittest.mock import MagicMock as MM
        m = MM(); m.free = 1 * 1024**3; return m  # 1 GB < floor

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.shutil.disk_usage", side_effect=low_disk):
        ok = run_discography_download(job_id, lambda: False)

    assert ok is False
    assert db.get_job(job_id)["status"] == "error"


def test_download_empty_plan_is_done():
    job_id = db.create_job("discography", "https://play.qobuz.com/artist/206")
    _setup_plan(job_id, [])

    ok = run_discography_download(job_id, lambda: False)

    assert ok is True
    assert db.get_job(job_id)["status"] == "done"


def test_download_picard_called_per_album(tmp_dirs):
    # In the incremental flow, _tag_and_move runs once per album download.
    # list_album_dirs is called once per album and should return 1 dir each time.
    job_id = db.create_job("discography", "https://play.qobuz.com/artist/207")
    albums = _fake_albums(3)
    album_dirs = _album_dirs(tmp_dirs / "downloads", count=3)
    _setup_plan(job_id, albums)

    picard_calls = []
    # Each call to list_album_dirs returns a single dir (simulating incremental drain).
    dirs_iter = iter([[d] for d in album_dirs])

    def record_picard(source_dir, **kwargs):
        picard_calls.append(source_dir)
        return _ok_picard()

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", side_effect=lambda _: next(dirs_iter)), \
         patch("app.pipeline.run_picard", side_effect=record_picard), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 3, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"), \
         patch("app.pipeline.shutil.disk_usage", side_effect=_big_disk):
        run_discography_download(job_id, lambda: False)

    assert len(picard_calls) == 3


# ── _process_job() routing ─────────────────────────────────────────────────────

def test_process_job_routes_discography():
    job_id = db.create_job("discography", "https://play.qobuz.com/artist/abc")
    job = db.get_job(job_id)
    with patch("app.jobs.run_discography_resolve", return_value=True) as mock_fn:
        _process_job(job)
    mock_fn.assert_called_once_with(job_id, "https://play.qobuz.com/artist/abc")


def test_process_job_routes_discography_confirmed():
    from unittest.mock import ANY
    job_id = db.create_job("discography", "https://play.qobuz.com/artist/abc2")
    db.update_job(job_id, status="confirmed")
    job = db.get_job(job_id)
    with patch("app.jobs.run_discography_download", return_value=True) as mock_fn:
        _process_job(job)
    mock_fn.assert_called_once_with(job_id, ANY)


# ── API endpoint ───────────────────────────────────────────────────────────────

def test_api_create_discography_job():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/jobs",
        json={"type": "discography", "url": "https://play.qobuz.com/artist/api_test"},
    )
    assert resp.status_code == 200
    assert "job_id" in resp.json()


def test_api_discography_job_requires_url():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/jobs", json={"type": "discography", "url": ""})
    assert resp.status_code == 400
