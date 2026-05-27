"""
Tests for the expand_discographies two-phase pipeline:
  - QobuzClient.playlist_to_artist_ids()        — unchanged, keep existing tests
  - QobuzClient.playlist_to_album_plan()        — new: resolves full catalogs
  - run_expand_discographies_resolve()           — API phase, sets awaiting_confirm
  - run_expand_discographies_download()          — download phase, album-by-album
  - _process_job() routing
  - API endpoint acceptance
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app import db
from app.qobuz_client import QobuzClient
from app.pipeline import run_expand_discographies_resolve, run_expand_discographies_download
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


def _fake_albums(count=2):
    return [
        {
            "id": f"alb{i}",
            "url": f"https://play.qobuz.com/album/alb{i}",
            "title": f"Album {i}",
            "artist": f"Artist{i}",
            "tracks_count": 10,
            "duration": 2400,
        }
        for i in range(count)
    ]


def _setup_plan(job_id, albums, quality=27):
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


def _big_disk(path):
    m = MagicMock(); m.free = 500 * 1024**3; return m


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


# ── Section B: resolve phase ───────────────────────────────────────────────────

def test_resolve_sets_awaiting_confirm():
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/10")
    mock_client = MagicMock()
    mock_client.playlist_to_album_plan.return_value = _fake_albums(3)

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.album_already_present", return_value=False):
        ok = run_expand_discographies_resolve(job_id, "https://play.qobuz.com/playlist/10")

    assert ok is True
    job = db.get_job(job_id)
    assert job["status"] == "awaiting_confirm"
    plan = json.loads(job["plan"])
    assert len(plan["albums"]) == 3


def test_resolve_skips_existing_albums():
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/11")
    mock_client = MagicMock()
    mock_client.playlist_to_album_plan.return_value = _fake_albums(4)

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.album_already_present", return_value=True):
        ok = run_expand_discographies_resolve(job_id, "https://play.qobuz.com/playlist/11")

    assert ok is False
    plan = json.loads(db.get_job(job_id)["plan"])
    assert len(plan["albums"]) == 0
    assert plan["skipped_existing"] == 4


def test_resolve_no_token():
    import app.settings_store as ss
    ss.save_settings("")

    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/13")
    ok = run_expand_discographies_resolve(job_id, "https://play.qobuz.com/playlist/13")
    assert ok is False
    assert db.get_job(job_id)["status"] == "error"


def test_resolve_client_exception():
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/14")
    mock_client = MagicMock()
    mock_client.playlist_to_album_plan.side_effect = RuntimeError("network timeout")

    with patch("app.pipeline.make_client", return_value=mock_client):
        ok = run_expand_discographies_resolve(job_id, "https://play.qobuz.com/playlist/14")

    assert ok is False
    assert db.get_job(job_id)["status"] == "error"


def test_resolve_logs_album_count():
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/16")
    mock_client = MagicMock()
    mock_client.playlist_to_album_plan.return_value = _fake_albums(3)

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.album_already_present", return_value=False):
        run_expand_discographies_resolve(job_id, "https://play.qobuz.com/playlist/16")

    log = db.get_job(job_id)["log"]
    assert "3" in log


# ── Section C: download phase ──────────────────────────────────────────────────

def test_download_success(tmp_dirs):
    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/20")
    albums = _fake_albums(2)
    album_dirs = _two_album_dirs(tmp_dirs / "downloads")
    _setup_plan(job_id, albums)

    dirs_iter = iter([[], [album_dirs[0]], [], [album_dirs[1]]])

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", side_effect=lambda _: next(dirs_iter)), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 2, "artists": ["a"], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"), \
         patch("app.pipeline.shutil.disk_usage", side_effect=_big_disk):
        ok = run_expand_discographies_download(job_id, lambda: False)

    assert ok is True
    assert db.get_job(job_id)["status"] == "done"


def test_download_continues_after_one_failure(tmp_dirs):
    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/21")
    albums = _fake_albums(3)
    album_dirs = [tmp_dirs / "downloads" / f"d{i}" for i in range(3)]
    for d in album_dirs:
        d.mkdir(parents=True, exist_ok=True)
    _setup_plan(job_id, albums)

    call_count = [0]
    def maybe_fail(url, **kwargs):
        call_count[0] += 1
        if call_count[0] == 2:
            return _fail_download("geo-blocked")
        return _ok_download()

    # album0 ok: [], [d0]; album1 fails: []; album2 ok: [], [d2]
    dirs_iter = iter([[], [album_dirs[0]], [], [], [album_dirs[2]]])

    with patch("app.pipeline.run_download", side_effect=maybe_fail), \
         patch("app.pipeline.list_album_dirs", side_effect=lambda _: next(dirs_iter, [])), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 2, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"), \
         patch("app.pipeline.shutil.disk_usage", side_effect=_big_disk):
        ok = run_expand_discographies_download(job_id, lambda: False)

    assert ok is False
    assert db.get_job(job_id)["status"] == "done_with_warnings"


def test_download_no_files_moved_is_error(tmp_dirs):
    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/22")
    albums = _fake_albums(1)
    album_dirs = _two_album_dirs(tmp_dirs / "downloads")
    _setup_plan(job_id, albums)

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", side_effect=[[], album_dirs]), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_empty_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 0, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"), \
         patch("app.pipeline.shutil.disk_usage", side_effect=_big_disk):
        ok = run_expand_discographies_download(job_id, lambda: False)

    assert ok is False
    assert db.get_job(job_id)["status"] == "error"


def test_download_cancelled(tmp_dirs):
    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/23")
    albums = _fake_albums(2)
    _setup_plan(job_id, albums)

    with patch("app.pipeline.run_download", return_value=_cancelled_download()), \
         patch("app.pipeline.list_album_dirs", return_value=[]), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 0, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"), \
         patch("app.pipeline.shutil.disk_usage", side_effect=_big_disk):
        ok = run_expand_discographies_download(job_id, lambda: True)

    assert ok is False
    assert db.get_job(job_id)["status"] == "cancelled"


def test_download_disk_guard_aborts():
    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/24")
    albums = _fake_albums(1)
    _setup_plan(job_id, albums)

    def low_disk(path):
        m = MagicMock(); m.free = 1 * 1024**3; return m

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.shutil.disk_usage", side_effect=low_disk):
        ok = run_expand_discographies_download(job_id, lambda: False)

    assert ok is False
    assert db.get_job(job_id)["status"] == "error"


def test_download_empty_plan_is_done():
    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/25")
    _setup_plan(job_id, [])

    ok = run_expand_discographies_download(job_id, lambda: False)

    assert ok is True
    assert db.get_job(job_id)["status"] == "done"


def test_download_downloads_each_album(tmp_dirs):
    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/26")
    albums = _fake_albums(3)
    album_dirs = [tmp_dirs / "downloads" / f"d{i}" for i in range(3)]
    for d in album_dirs:
        d.mkdir(parents=True, exist_ok=True)
    _setup_plan(job_id, albums)

    download_urls = []
    dirs_iter = iter([item for d in album_dirs for item in ([], [d])])

    def record(url, **kwargs):
        download_urls.append(url)
        return _ok_download()

    with patch("app.pipeline.run_download", side_effect=record), \
         patch("app.pipeline.list_album_dirs", side_effect=lambda _: next(dirs_iter)), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 3, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"), \
         patch("app.pipeline.shutil.disk_usage", side_effect=_big_disk):
        run_expand_discographies_download(job_id, lambda: False)

    assert len(download_urls) == 3
    assert all("play.qobuz.com/album/" in u for u in download_urls)


def test_download_single_artist_done(tmp_dirs):
    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/27")
    albums = _fake_albums(1)
    album_dirs = _two_album_dirs(tmp_dirs / "downloads")
    _setup_plan(job_id, albums)

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", side_effect=[[], album_dirs]), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move(2)), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 2, "artists": ["solo"], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"), \
         patch("app.pipeline.shutil.disk_usage", side_effect=_big_disk):
        ok = run_expand_discographies_download(job_id, lambda: False)

    assert ok is True
    assert db.get_job(job_id)["status"] == "done"


# ── Section D: routing and API ─────────────────────────────────────────────────

def test_process_job_routes_expand_discographies():
    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/x")
    job = db.get_job(job_id)
    with patch("app.jobs.run_expand_discographies_resolve", return_value=True) as mock_fn:
        _process_job(job)
    mock_fn.assert_called_once_with(job_id, "https://play.qobuz.com/playlist/x")


def test_process_job_routes_expand_discographies_confirmed():
    from unittest.mock import ANY
    job_id = db.create_job("expand_discographies", "https://play.qobuz.com/playlist/x2")
    db.update_job(job_id, status="confirmed")
    job = db.get_job(job_id)
    with patch("app.jobs.run_expand_discographies_download", return_value=True) as mock_fn:
        _process_job(job)
    mock_fn.assert_called_once_with(job_id, ANY)


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


# ── Section E: playlist_to_album_plan filters ─────────────────────────────────

def _raw_album(album_id, title, artist_name, artist_id):
    return {
        "id": album_id,
        "title": title,
        "artist": {"id": artist_id, "name": artist_name},
        "tracks_count": 5,
        "duration": 1200,
    }


def _playlist_track(album_artist_id, track_id="t1"):
    return {"id": track_id, "album": {"artist": {"id": album_artist_id}}}


def test_album_plan_excludes_infrequent_artists():
    """Artists appearing as album-artist only once should not have their catalogs expanded."""
    import app.config as cfg
    client = QobuzClient("fake_token")
    # artist "main" appears 3 times, artist "feat" appears once
    tracks = [
        _playlist_track("main", "t1"),
        _playlist_track("main", "t2"),
        _playlist_track("main", "t3"),
        _playlist_track("feat", "t4"),
    ]
    main_albums = [_raw_album("alb1", "Real Album", "Main Artist", "main")]
    feat_albums = [_raw_album("alb2", "Feature Album", "Feat Artist", "feat")]

    def fake_get_artist_albums(artist_id):
        return main_albums if artist_id == "main" else feat_albums

    with patch.object(client, "get_playlist_tracks", return_value=tracks), \
         patch.object(client, "get_artist_albums", side_effect=fake_get_artist_albums), \
         patch.object(cfg, "EXPAND_MIN_ARTIST_TRACKS", 2), \
         patch.object(cfg, "EXPAND_JUNK_PATTERNS", ""):
        result = client.playlist_to_album_plan("https://play.qobuz.com/playlist/1")

    ids = [a["id"] for a in result]
    assert "alb1" in ids
    assert "alb2" not in ids  # "feat" only appeared once — catalog not expanded


def test_album_plan_min_tracks_one_includes_all():
    """Setting threshold to 1 restores original behaviour (expand all artists)."""
    import app.config as cfg
    client = QobuzClient("fake_token")
    tracks = [
        _playlist_track("main", "t1"),
        _playlist_track("feat", "t2"),
    ]
    main_albums = [_raw_album("alb1", "Main Album", "Main", "main")]
    feat_albums = [_raw_album("alb2", "Feat Album", "Feat", "feat")]

    def fake_get_artist_albums(artist_id):
        return main_albums if artist_id == "main" else feat_albums

    with patch.object(client, "get_playlist_tracks", return_value=tracks), \
         patch.object(client, "get_artist_albums", side_effect=fake_get_artist_albums), \
         patch.object(cfg, "EXPAND_MIN_ARTIST_TRACKS", 1), \
         patch.object(cfg, "EXPAND_JUNK_PATTERNS", ""):
        result = client.playlist_to_album_plan("https://play.qobuz.com/playlist/1")

    ids = [a["id"] for a in result]
    assert "alb1" in ids
    assert "alb2" in ids


def test_album_plan_junk_filter_drops_matching_albums():
    """Albums whose artist+title matches EXPAND_JUNK_PATTERNS are excluded."""
    import app.config as cfg
    client = QobuzClient("fake_token")
    tracks = [_playlist_track("artist1", "t1"), _playlist_track("artist1", "t2")]
    raw_albums = [
        _raw_album("legit", "Good Album", "Real Artist", "artist1"),
        _raw_album("junk1", "Good Album (Karaoke Version)", "Karaoke Studio", "artist1"),
        _raw_album("junk2", "Nightcore Mix", "NightcoreChan", "artist1"),
        _raw_album("junk3", "Originally Performed by Drake", "Tribute Band", "artist1"),
    ]

    with patch.object(client, "get_playlist_tracks", return_value=tracks), \
         patch.object(client, "get_artist_albums", return_value=raw_albums), \
         patch.object(cfg, "EXPAND_MIN_ARTIST_TRACKS", 1), \
         patch.object(cfg, "EXPAND_JUNK_PATTERNS", r"karaoke|nightcore|originally performed by"):
        result = client.playlist_to_album_plan("https://play.qobuz.com/playlist/1")

    ids = [a["id"] for a in result]
    assert "legit" in ids
    assert "junk1" not in ids
    assert "junk2" not in ids
    assert "junk3" not in ids


def test_album_plan_empty_junk_patterns_keeps_all():
    """Empty EXPAND_JUNK_PATTERNS disables junk filtering."""
    import app.config as cfg
    client = QobuzClient("fake_token")
    tracks = [_playlist_track("artist1", "t1"), _playlist_track("artist1", "t2")]
    raw_albums = [
        _raw_album("alb1", "Karaoke Hits", "Karaoke Inc", "artist1"),
        _raw_album("alb2", "Real Music", "Real Artist", "artist1"),
    ]

    with patch.object(client, "get_playlist_tracks", return_value=tracks), \
         patch.object(client, "get_artist_albums", return_value=raw_albums), \
         patch.object(cfg, "EXPAND_MIN_ARTIST_TRACKS", 1), \
         patch.object(cfg, "EXPAND_JUNK_PATTERNS", ""):
        result = client.playlist_to_album_plan("https://play.qobuz.com/playlist/1")

    ids = [a["id"] for a in result]
    assert "alb1" in ids
    assert "alb2" in ids


def test_album_plan_deduplicates_albums_across_artists():
    """Same album shared by two qualifying artists appears only once."""
    import app.config as cfg
    client = QobuzClient("fake_token")
    tracks = [
        _playlist_track("artist1", "t1"),
        _playlist_track("artist1", "t2"),
        _playlist_track("artist2", "t3"),
        _playlist_track("artist2", "t4"),
    ]
    shared_album = _raw_album("shared", "Collab Album", "Artist1", "artist1")

    with patch.object(client, "get_playlist_tracks", return_value=tracks), \
         patch.object(client, "get_artist_albums", return_value=[shared_album]), \
         patch.object(cfg, "EXPAND_MIN_ARTIST_TRACKS", 2), \
         patch.object(cfg, "EXPAND_JUNK_PATTERNS", ""):
        result = client.playlist_to_album_plan("https://play.qobuz.com/playlist/1")

    assert len([a for a in result if a["id"] == "shared"]) == 1
