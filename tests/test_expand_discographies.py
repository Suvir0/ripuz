"""
Tests for the expand_discographies feature:
  - QobuzClient.playlist_to_artist_ids()
  - run_expand_discographies_pipeline()
  - _process_job() routing
  - API endpoint acceptance
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app import db
from app.qobuz_client import QobuzClient
from app.pipeline import run_expand_discographies_pipeline
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


def _ok_move(n: int = 1):
    return MoveResult(moved=[Path(f"/music/a/b/track{i}.FLAC") for i in range(n)])


def _empty_move():
    return MoveResult()


def _two_album_dirs(root: Path):
    d1 = root / "Artist1" / "AlbumA"
    d2 = root / "Artist2" / "AlbumB"
    d1.mkdir(parents=True, exist_ok=True)
    d2.mkdir(parents=True, exist_ok=True)
    return [d1, d2]


def _track(performer_id=None, album_artist_id=None, track_id="t1"):
    track = {"id": track_id, "album": {}}
    if performer_id is not None:
        track["performer"] = {"id": performer_id}
    if album_artist_id is not None:
        track["album"] = {"artist": {"id": album_artist_id}}
    return track


# ── Section A: QobuzClient.playlist_to_artist_ids() ───────────────────────────

def test_playlist_to_artist_ids_uses_performer_id():
    client = QobuzClient("fake_token")
    tracks = [_track(performer_id="111", track_id="t1")]
    with patch.object(client, "get_playlist_tracks", return_value=tracks):
        ids = client.playlist_to_artist_ids("https://play.qobuz.com/playlist/1")
    assert ids == ["111"]


def test_playlist_to_artist_ids_falls_back_to_album_artist():
    client = QobuzClient("fake_token")
    tracks = [_track(album_artist_id="222", track_id="t1")]
    with patch.object(client, "get_playlist_tracks", return_value=tracks):
        ids = client.playlist_to_artist_ids("https://play.qobuz.com/playlist/1")
    assert ids == ["222"]


def test_playlist_to_artist_ids_deduplicates():
    client = QobuzClient("fake_token")
    tracks = [
        _track(performer_id="333", track_id="t1"),
        _track(performer_id="333", track_id="t2"),
    ]
    with patch.object(client, "get_playlist_tracks", return_value=tracks):
        ids = client.playlist_to_artist_ids("https://play.qobuz.com/playlist/1")
    assert ids == ["333"]


def test_playlist_to_artist_ids_multiple_artists():
    client = QobuzClient("fake_token")
    tracks = [
        _track(performer_id="aaa", track_id="t1"),
        _track(performer_id="bbb", track_id="t2"),
        _track(performer_id="ccc", track_id="t3"),
    ]
    with patch.object(client, "get_playlist_tracks", return_value=tracks):
        ids = client.playlist_to_artist_ids("https://play.qobuz.com/playlist/1")
    assert ids == ["aaa", "bbb", "ccc"]


def test_playlist_to_artist_ids_empty_playlist():
    client = QobuzClient("fake_token")
    with patch.object(client, "get_playlist_tracks", return_value=[]):
        ids = client.playlist_to_artist_ids("https://play.qobuz.com/playlist/1")
    assert ids == []


def test_playlist_to_artist_ids_skips_tracks_without_artist():
    client = QobuzClient("fake_token")
    # Track with no performer and no album artist
    tracks = [{"id": "t1", "album": {}, "title": "orphan track"}]
    with patch.object(client, "get_playlist_tracks", return_value=tracks):
        ids = client.playlist_to_artist_ids("https://play.qobuz.com/playlist/1")
    assert ids == []


def test_playlist_to_artist_ids_preserves_insertion_order():
    client = QobuzClient("fake_token")
    tracks = [
        _track(performer_id="z99", track_id="t1"),
        _track(performer_id="a01", track_id="t2"),
        _track(performer_id="m50", track_id="t3"),
    ]
    with patch.object(client, "get_playlist_tracks", return_value=tracks):
        ids = client.playlist_to_artist_ids("https://play.qobuz.com/playlist/1")
    assert ids == ["z99", "a01", "m50"]


# ── Section B: run_expand_discographies_pipeline() ────────────────────────────

def test_expand_discographies_success(tmp_dirs):
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/10")
    mock_client = MagicMock()
    mock_client.playlist_to_artist_ids.return_value = ["artist1", "artist2"]
    album_dirs = _two_album_dirs(tmp_dirs / "downloads")

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 2, "artists": ["artist1", "artist2"], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        ok = run_expand_discographies_pipeline(job_id, "https://play.qobuz.com/playlist/10")

    assert ok is True
    assert db.get_job(job_id)["status"] == "done"


def test_expand_discographies_downloads_each_artist(tmp_dirs):
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/11")
    mock_client = MagicMock()
    mock_client.playlist_to_artist_ids.return_value = ["a1", "a2", "a3"]
    album_dirs = _two_album_dirs(tmp_dirs / "downloads")
    download_calls = []

    def record_download(url, **kwargs):
        download_calls.append(url)
        return _ok_download()

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.run_download", side_effect=record_download), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 3, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        run_expand_discographies_pipeline(job_id, "https://play.qobuz.com/playlist/11")

    assert len(download_calls) == 3
    assert all("play.qobuz.com/artist/" in u for u in download_calls)


def test_expand_discographies_continues_after_one_failure(tmp_dirs):
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/12")
    mock_client = MagicMock()
    mock_client.playlist_to_artist_ids.return_value = ["good1", "bad1", "good2"]
    album_dirs = _two_album_dirs(tmp_dirs / "downloads")

    def download_by_url(url, **kwargs):
        if "bad1" in url:
            return _fail_download("geo-blocked")
        return _ok_download()

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.run_download", side_effect=download_by_url), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 2, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        ok = run_expand_discographies_pipeline(job_id, "https://play.qobuz.com/playlist/12")

    assert ok is False
    assert db.get_job(job_id)["status"] == "done_with_warnings"


def test_expand_discographies_no_token():
    import app.settings_store as ss
    ss.save_settings("")

    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/13")
    ok = run_expand_discographies_pipeline(job_id, "https://play.qobuz.com/playlist/13")
    assert ok is False
    assert db.get_job(job_id)["status"] == "error"


def test_expand_discographies_client_exception():
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/14")
    mock_client = MagicMock()
    mock_client.playlist_to_artist_ids.side_effect = RuntimeError("network timeout")

    with patch("app.pipeline.make_client", return_value=mock_client):
        ok = run_expand_discographies_pipeline(job_id, "https://play.qobuz.com/playlist/14")

    assert ok is False
    assert db.get_job(job_id)["status"] == "error"


def test_expand_discographies_no_files_moved(tmp_dirs):
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/15")
    mock_client = MagicMock()
    mock_client.playlist_to_artist_ids.return_value = ["a1"]
    album_dirs = _two_album_dirs(tmp_dirs / "downloads")

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_empty_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 0, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        ok = run_expand_discographies_pipeline(job_id, "https://play.qobuz.com/playlist/15")

    assert ok is False
    assert db.get_job(job_id)["status"] == "error"


def test_expand_discographies_logs_artist_count(tmp_dirs):
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/16")
    mock_client = MagicMock()
    mock_client.playlist_to_artist_ids.return_value = ["a1", "a2", "a3"]
    album_dirs = _two_album_dirs(tmp_dirs / "downloads")

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 3, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        run_expand_discographies_pipeline(job_id, "https://play.qobuz.com/playlist/16")

    log = db.get_job(job_id)["log"]
    assert "3" in log


def test_expand_discographies_single_artist_done(tmp_dirs):
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/17")
    mock_client = MagicMock()
    mock_client.playlist_to_artist_ids.return_value = ["solo_artist"]
    album_dirs = _two_album_dirs(tmp_dirs / "downloads")

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move(2)), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 2, "artists": ["solo_artist"], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        ok = run_expand_discographies_pipeline(job_id, "https://play.qobuz.com/playlist/17")

    assert ok is True
    assert db.get_job(job_id)["status"] == "done"


def test_expand_discographies_all_artists_fail(tmp_dirs):
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/18")
    mock_client = MagicMock()
    mock_client.playlist_to_artist_ids.return_value = ["bad1", "bad2"]
    album_dirs = _two_album_dirs(tmp_dirs / "downloads")

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.run_download", return_value=_fail_download("unavailable")), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 0, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        ok = run_expand_discographies_pipeline(job_id, "https://play.qobuz.com/playlist/18")

    assert ok is False


# ── Section C: routing and API ─────────────────────────────────────────────────

def test_process_job_routes_expand_discographies():
    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/x")
    job = db.get_job(job_id)
    with patch("app.jobs.run_expand_discographies_pipeline", return_value=True) as mock_fn:
        _process_job(job)
    mock_fn.assert_called_once_with(job_id, "https://play.qobuz.com/playlist/x")


def test_api_create_job_expand_discographies():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/jobs",
        json={"type": "expand_discographies", "url": "https://play.qobuz.com/playlist/api_test"},
    )
    assert resp.status_code == 200
    assert "job_id" in resp.json()


def test_api_rejects_invalid_job_type():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/jobs",
        json={"type": "not_a_real_type", "url": "https://play.qobuz.com/playlist/1"},
    )
    assert resp.status_code == 400
