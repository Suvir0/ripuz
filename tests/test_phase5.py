"""
Phase 5 tests: pipeline, job queue, structure utilities.
qobuz-dl and Picard subprocess calls are mocked throughout.
"""
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from app import db
from app.structure import (
    find_flac_files,
    clean_empty_dirs,
    verify_structure,
)
from app.pipeline import run_playlist_pipeline, run_expand_albums_resolve, run_expand_albums_download
from app.jobs import enqueue, _process_job


# ── structure utilities ────────────────────────────────────────────────────────

def _make_flac(root: Path, artist: str, album: str, title: str) -> Path:
    dest = root / artist / album
    dest.mkdir(parents=True, exist_ok=True)
    f = dest / f"{title}.FLAC"
    f.write_bytes(b"FLAC" + b"\x00" * 100)
    return f


def test_find_flac_files(tmp_path):
    _make_flac(tmp_path, "Drake", "ICEMAN", "What_Did_I_Miss")
    _make_flac(tmp_path, "Drake", "ICEMAN", "Evil_Ways")
    files = find_flac_files(tmp_path)
    assert len(files) == 2


def test_find_flac_files_mixed_case(tmp_path):
    (tmp_path / "a.flac").write_bytes(b"x")
    (tmp_path / "b.FLAC").write_bytes(b"x")
    assert len(find_flac_files(tmp_path)) == 2


def test_clean_empty_dirs(tmp_path):
    empty = tmp_path / "artist" / "album"
    empty.mkdir(parents=True)
    removed = clean_empty_dirs(tmp_path)
    assert not empty.exists()
    assert len(removed) >= 2


def test_clean_empty_dirs_leaves_nonempty(tmp_path):
    nonempty = tmp_path / "artist" / "album"
    nonempty.mkdir(parents=True)
    f = nonempty / "track.FLAC"
    f.write_bytes(b"data")
    clean_empty_dirs(tmp_path)
    assert f.exists()


def test_verify_structure_counts_flacs(tmp_path):
    _make_flac(tmp_path, "Drake", "ICEMAN", "What_Did_I_Miss")
    _make_flac(tmp_path, "Drake", "ICEMAN", "Evil_Ways")
    stats = verify_structure(tmp_path)
    assert stats["flac_count"] == 2


def test_verify_structure_lists_artists(tmp_path):
    _make_flac(tmp_path, "Drake", "ICEMAN", "Track1")
    _make_flac(tmp_path, "Future", "DS2", "Blow_A_Bag")
    stats = verify_structure(tmp_path)
    assert "Drake" in stats["artists"]
    assert "Future" in stats["artists"]


def test_verify_structure_flags_shallow_file(tmp_path):
    # File directly in music_dir (no artist/album depth)
    (tmp_path / "stray.FLAC").write_bytes(b"x")
    stats = verify_structure(tmp_path)
    assert any("depth" in issue for issue in stats["issues"])


def test_verify_structure_no_issues_for_correct_layout(tmp_path):
    _make_flac(tmp_path, "Drake", "ICEMAN", "Track1")
    stats = verify_structure(tmp_path)
    assert stats["issues"] == []


# ── pipeline helpers ───────────────────────────────────────────────────────────

from app.qobuz_cli import DownloadResult
from app.picard import PicardResult
from app.mover import MoveResult


def _ok_download():
    return DownloadResult(success=True)


def _ok_picard():
    return PicardResult(success=True)


def _ok_move(n: int = 1):
    from pathlib import Path
    return MoveResult(moved=[Path(f"/music/a/b/track{i}.FLAC") for i in range(n)])


def _empty_move():
    return MoveResult()


def _fail_download(msg="dl error"):
    return DownloadResult(success=False, error_message=msg)


def _fail_picard(msg="picard error"):
    return PicardResult(success=False, error_message=msg)


def _two_album_dirs(root):
    """Return two fake album dirs (used as list_album_dirs mock)."""
    from pathlib import Path
    d1 = root / "Artist1" / "AlbumA"
    d2 = root / "Artist2" / "AlbumB"
    d1.mkdir(parents=True, exist_ok=True)
    d2.mkdir(parents=True, exist_ok=True)
    return [d1, d2]


# ── playlist pipeline ──────────────────────────────────────────────────────────

def test_playlist_pipeline_success(tmp_dirs):
    job_id = db.create_job("playlist", "https://play.qobuz.com/playlist/1")
    album_dirs = _two_album_dirs(tmp_dirs / "downloads")
    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 2, "artists": ["Drake"], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        ok = run_playlist_pipeline(job_id, "https://play.qobuz.com/playlist/1")
    assert ok is True
    assert db.get_job(job_id)["status"] == "done"


def test_playlist_pipeline_download_failure():
    job_id = db.create_job("playlist", "https://play.qobuz.com/playlist/2")
    with patch("app.pipeline.run_download", return_value=_fail_download()):
        ok = run_playlist_pipeline(job_id, "https://play.qobuz.com/playlist/2")
    assert ok is False
    assert db.get_job(job_id)["status"] == "error"


def test_playlist_pipeline_picard_failure_still_moves(tmp_dirs):
    """Picard failure is non-fatal; files are moved with existing tags."""
    job_id = db.create_job("playlist", "https://play.qobuz.com/playlist/3")
    album_dirs = _two_album_dirs(tmp_dirs / "downloads")
    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_fail_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 2, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        ok = run_playlist_pipeline(job_id, "https://play.qobuz.com/playlist/3")
    assert ok is True
    assert db.get_job(job_id)["status"] == "done"


def test_playlist_pipeline_no_files_moved_is_error(tmp_dirs):
    """If move_album returns zero moved files, the job is an error."""
    job_id = db.create_job("playlist", "https://play.qobuz.com/playlist/30")
    album_dirs = _two_album_dirs(tmp_dirs / "downloads")
    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_empty_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 0, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        ok = run_playlist_pipeline(job_id, "https://play.qobuz.com/playlist/30")
    assert ok is False
    assert db.get_job(job_id)["status"] == "error"


def test_playlist_pipeline_per_album_picard_calls(tmp_dirs):
    """run_picard is called once per album directory."""
    job_id = db.create_job("playlist", "https://play.qobuz.com/playlist/31")
    album_dirs = _two_album_dirs(tmp_dirs / "downloads")
    picard_calls = []

    def record_picard(source_dir, **kwargs):
        picard_calls.append(source_dir)
        return _ok_picard()

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", side_effect=record_picard), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 2, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        run_playlist_pipeline(job_id, "https://play.qobuz.com/playlist/31")

    assert len(picard_calls) == 2


def test_playlist_pipeline_logs_steps(tmp_dirs):
    job_id = db.create_job("playlist", "https://play.qobuz.com/playlist/4")
    album_dirs = _two_album_dirs(tmp_dirs / "downloads")
    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", return_value=album_dirs), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 0, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        run_playlist_pipeline(job_id, "https://play.qobuz.com/playlist/4")
    log = db.get_job(job_id)["log"]
    assert "downloading" in log.lower()
    assert "tagging" in log.lower()


# ── expand_albums pipeline (two-phase) ────────────────────────────────────────

def _fake_album_plan(ids):
    return [
        {"id": aid, "url": f"https://play.qobuz.com/album/{aid}",
         "title": f"Album {aid}", "artist": "Artist", "tracks_count": 10, "duration": 2400}
        for aid in ids
    ]


def _setup_plan(job_id, albums, quality=27):
    import json
    plan = {"albums": albums, "skipped_existing": 0, "est_gb": 1.0,
            "quality": quality, "capped": False, "cap": 300}
    db.set_job_plan(job_id, json.dumps(plan))
    db.update_job(job_id, status="confirmed")


def _big_disk(path):
    m = MagicMock(); m.free = 500 * 1024**3; return m


def test_expand_albums_resolve_sets_awaiting_confirm():
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("expand_albums", "https://play.qobuz.com/playlist/99")
    mock_client = MagicMock()
    mock_client.playlist_to_album_plan_from_tracks.return_value = _fake_album_plan(["alb1", "alb2"])

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.album_already_present", return_value=False):
        ok = run_expand_albums_resolve(job_id, "https://play.qobuz.com/playlist/99")

    assert ok is True
    assert db.get_job(job_id)["status"] == "awaiting_confirm"


def test_expand_albums_download_success(tmp_dirs):
    job_id = db.create_job("expand_albums", "https://play.qobuz.com/playlist/100")
    albums = _fake_album_plan(["alb_a", "alb_b"])
    album_dirs = _two_album_dirs(tmp_dirs / "downloads")
    _setup_plan(job_id, albums)

    dirs_iter = iter([[d] for d in album_dirs])

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs", side_effect=lambda _: next(dirs_iter)), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 2, "artists": ["Artist"], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"), \
         patch("app.pipeline.shutil.disk_usage", side_effect=_big_disk):
        ok = run_expand_albums_download(job_id, lambda: False)

    assert ok is True
    assert db.get_job(job_id)["status"] == "done"


def test_expand_albums_download_continues_after_one_failure(tmp_dirs):
    job_id = db.create_job("expand_albums", "https://play.qobuz.com/playlist/101")
    albums = _fake_album_plan(["good1", "bad1", "good2"])
    album_dirs = [tmp_dirs / "downloads" / f"d{i}" for i in range(3)]
    for d in album_dirs:
        d.mkdir(parents=True, exist_ok=True)
    _setup_plan(job_id, albums)

    dirs_iter = iter([[d] for d in album_dirs])

    def download_by_url(url, **kwargs):
        if "bad1" in url:
            return _fail_download("geo-blocked")
        return _ok_download()

    with patch("app.pipeline.run_download", side_effect=download_by_url), \
         patch("app.pipeline.list_album_dirs", side_effect=lambda _: next(dirs_iter, [])), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={"flac_count": 2, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"), \
         patch("app.pipeline.shutil.disk_usage", side_effect=_big_disk):
        ok = run_expand_albums_download(job_id, lambda: False)

    assert ok is False
    assert db.get_job(job_id)["status"] == "done_with_warnings"


def test_expand_albums_resolve_no_token():
    import app.settings_store as ss
    ss.save_settings("")

    job_id = db.create_job("expand_albums", "https://play.qobuz.com/playlist/102")
    ok = run_expand_albums_resolve(job_id, "https://play.qobuz.com/playlist/102")
    assert ok is False
    assert db.get_job(job_id)["status"] == "error"


# ── job queue enqueue ──────────────────────────────────────────────────────────

def test_enqueue_creates_queued_job():
    job_id = enqueue("playlist", "https://play.qobuz.com/playlist/9")
    job = db.get_job(job_id)
    assert job["status"] == "queued"
    assert job["type"] == "playlist"


def test_process_job_routes_playlist():
    from unittest.mock import ANY
    job_id = db.create_job("playlist", "https://play.qobuz.com/playlist/x")
    job = db.get_job(job_id)
    with patch("app.jobs.run_playlist_pipeline", return_value=True) as mock_pl:
        _process_job(job)
    mock_pl.assert_called_once_with(job_id, "https://play.qobuz.com/playlist/x", ANY)


def test_process_job_routes_expand_albums():
    job_id = db.create_job("expand_albums", "https://play.qobuz.com/playlist/y")
    job = db.get_job(job_id)
    with patch("app.jobs.run_expand_albums_resolve", return_value=True) as mock_ea:
        _process_job(job)
    mock_ea.assert_called_once_with(job_id, "https://play.qobuz.com/playlist/y")


def test_process_job_unknown_type():
    job_id = db.create_job("unknown_type", "https://example.com")
    job = db.get_job(job_id)
    _process_job(job)
    assert db.get_job(job_id)["status"] == "error"


def test_process_job_exception_sets_error():
    job_id = db.create_job("playlist", "https://play.qobuz.com/playlist/z")
    job = db.get_job(job_id)
    with patch("app.jobs.run_playlist_pipeline", side_effect=RuntimeError("boom")):
        _process_job(job)
    assert db.get_job(job_id)["status"] == "error"
    assert "boom" in db.get_job(job_id)["log"]
