"""
Tests for the fetch-art feature: scan the music library for album dirs that
have no cover art sidecar, extract from embedded FLAC pictures or fetch from
the Cover Art Archive, and write cover.jpg in place.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import respx
import httpx

from app import config, db, jobs, pipeline
from app import art_library
from app.art_library import (
    find_cover,
    album_needs_art,
    scan_missing_art,
    fetch_caa_art,
    write_cover,
    _read_album_mbid,
    extract_embedded_art,
    _ART_NAMES,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_flac(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def _make_cover(album_dir: Path, name: str = "cover.jpg", content: bytes = b"jpg") -> Path:
    album_dir.mkdir(parents=True, exist_ok=True)
    p = album_dir / name
    p.write_bytes(content)
    return p


# ── find_cover / album_needs_art ─────────────────────────────────────────────

def test_find_cover_returns_none_when_missing(tmp_path):
    assert find_cover(tmp_path) is None


@pytest.mark.parametrize("name", _ART_NAMES)
def test_find_cover_detects_each_art_name(tmp_path, name):
    (tmp_path / name).write_bytes(b"x")
    assert find_cover(tmp_path) == tmp_path / name


def test_album_needs_art_true_when_missing(tmp_path):
    assert album_needs_art(tmp_path) is True


def test_album_needs_art_false_when_present(tmp_path):
    (tmp_path / "cover.jpg").write_bytes(b"x")
    assert album_needs_art(tmp_path) is False


# ── scan_missing_art ─────────────────────────────────────────────────────────

def test_scan_flags_only_albums_without_art():
    music = config.MUSIC_DIR
    # Album with art
    has_art_dir = music / "Artist1" / "Album1"
    _make_flac(has_art_dir / "track.flac")
    (has_art_dir / "cover.jpg").write_bytes(b"jpg")
    # Album without art
    no_art_dir = music / "Artist2" / "Album2"
    _make_flac(no_art_dir / "track.flac")

    scan = scan_missing_art(music)

    assert scan["scanned_albums"] == 2
    assert scan["missing_albums"] == 1
    assert str(no_art_dir) in scan["dirs"]
    assert str(has_art_dir) not in scan["dirs"]


def test_scan_empty_music_dir():
    scan = scan_missing_art(config.MUSIC_DIR)
    assert scan == {"dirs": [], "scanned_albums": 0, "missing_albums": 0}


# ── fetch_caa_art ─────────────────────────────────────────────────────────────

@respx.mock
def test_fetch_caa_art_success_on_front_1200():
    respx.get("https://coverartarchive.org/release/abc-123/front-1200").mock(
        return_value=httpx.Response(200, content=b"jpegdata", headers={"Content-Type": "image/jpeg"})
    )
    with httpx.Client(follow_redirects=True) as client:
        result = fetch_caa_art("abc-123", client=client)
    assert result is not None
    data, mime = result
    assert data == b"jpegdata"
    assert mime == "image/jpeg"


@respx.mock
def test_fetch_caa_art_falls_back_to_front():
    respx.get("https://coverartarchive.org/release/abc-123/front-1200").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://coverartarchive.org/release/abc-123/front").mock(
        return_value=httpx.Response(200, content=b"fallback", headers={"Content-Type": "image/jpeg"})
    )
    with httpx.Client(follow_redirects=True) as client:
        result = fetch_caa_art("abc-123", client=client)
    assert result is not None
    assert result[0] == b"fallback"


@respx.mock
def test_fetch_caa_art_returns_none_on_all_404():
    respx.get("https://coverartarchive.org/release/abc-123/front-1200").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://coverartarchive.org/release/abc-123/front").mock(
        return_value=httpx.Response(404)
    )
    with httpx.Client(follow_redirects=True) as client:
        result = fetch_caa_art("abc-123", client=client)
    assert result is None


@respx.mock
def test_fetch_caa_art_returns_none_on_network_error():
    respx.get("https://coverartarchive.org/release/abc-123/front-1200").mock(
        side_effect=httpx.ConnectError("refused")
    )
    respx.get("https://coverartarchive.org/release/abc-123/front").mock(
        side_effect=httpx.ConnectError("refused")
    )
    with httpx.Client(follow_redirects=True) as client:
        result = fetch_caa_art("abc-123", client=client)
    assert result is None


# ── write_cover ───────────────────────────────────────────────────────────────

def test_write_cover_jpeg(tmp_path):
    dest = write_cover(tmp_path, b"jpegdata", "image/jpeg")
    assert dest == tmp_path / "cover.jpg"
    assert dest.read_bytes() == b"jpegdata"


def test_write_cover_png(tmp_path):
    dest = write_cover(tmp_path, b"pngdata", "image/png")
    assert dest == tmp_path / "cover.png"
    assert dest.read_bytes() == b"pngdata"


# ── resolve phase ─────────────────────────────────────────────────────────────

def test_resolve_creates_plan_awaiting_confirm():
    music = config.MUSIC_DIR
    no_art_dir = music / "Artist" / "Album"
    _make_flac(no_art_dir / "track.flac")

    job_id = db.create_job("fetch_art", "library")
    pipeline.run_fetch_art_resolve(job_id)

    job = db.get_job(job_id)
    assert job["status"] == "awaiting_confirm"
    plan = json.loads(job["plan"])
    assert plan["missing_albums"] == 1
    assert plan["scanned_albums"] == 1
    assert str(no_art_dir) in plan["dirs"]


def test_resolve_empty_library_returns_false():
    job_id = db.create_job("fetch_art", "library")
    result = pipeline.run_fetch_art_resolve(job_id)
    assert result is False
    job = db.get_job(job_id)
    # awaiting_confirm even when empty (user can still confirm a no-op)
    assert job["status"] == "awaiting_confirm"


# ── execute phase ─────────────────────────────────────────────────────────────

def _setup_execute_job(dirs):
    job_id = db.create_job("fetch_art", "library")
    plan = {"dirs": [str(d) for d in dirs], "scanned_albums": len(dirs), "missing_albums": len(dirs)}
    db.set_job_plan(job_id, json.dumps(plan))
    db.update_job(job_id, status="confirmed")
    return job_id


def test_execute_uses_embedded_art_first(tmp_path):
    album_dir = tmp_path / "Artist" / "Album"
    _make_flac(album_dir / "track.flac")
    job_id = _setup_execute_job([album_dir])

    with patch.object(pipeline, "extract_embedded_art", return_value=(b"imgdata", "image/jpeg")):
        with patch.object(pipeline, "fetch_caa_art") as mock_caa:
            pipeline.run_fetch_art_execute(job_id, lambda: False)
            mock_caa.assert_not_called()

    assert (album_dir / "cover.jpg").exists()
    assert db.get_job(job_id)["status"] == "done"


def test_execute_falls_back_to_caa_when_no_embedded(tmp_path):
    album_dir = tmp_path / "Artist" / "Album"
    _make_flac(album_dir / "track.flac")
    job_id = _setup_execute_job([album_dir])

    with patch.object(pipeline, "extract_embedded_art", return_value=None):
        with patch.object(pipeline, "_read_album_mbid", return_value="mbid-1"):
            with patch.object(pipeline, "fetch_caa_art", return_value=(b"caaimg", "image/jpeg")):
                pipeline.run_fetch_art_execute(job_id, lambda: False)

    assert (album_dir / "cover.jpg").exists()
    assert db.get_job(job_id)["status"] == "done"


def test_execute_done_with_warnings_when_no_art_found(tmp_path):
    album_dir = tmp_path / "Artist" / "Album"
    _make_flac(album_dir / "track.flac")
    job_id = _setup_execute_job([album_dir])

    with patch.object(pipeline, "extract_embedded_art", return_value=None):
        with patch.object(pipeline, "_read_album_mbid", return_value=None):
            pipeline.run_fetch_art_execute(job_id, lambda: False)

    assert db.get_job(job_id)["status"] == "done_with_warnings"
    assert not (album_dir / "cover.jpg").exists()


def test_execute_skips_already_has_cover(tmp_path):
    album_dir = tmp_path / "Artist" / "Album"
    _make_flac(album_dir / "track.flac")
    (album_dir / "cover.jpg").write_bytes(b"existing")
    job_id = _setup_execute_job([album_dir])

    with patch.object(pipeline, "extract_embedded_art") as mock_embed:
        pipeline.run_fetch_art_execute(job_id, lambda: False)
        mock_embed.assert_not_called()

    assert db.get_job(job_id)["status"] == "done"


def test_execute_cancel_stops_processing(tmp_path):
    album_dir = tmp_path / "Artist" / "Album"
    _make_flac(album_dir / "track.flac")
    job_id = _setup_execute_job([album_dir])

    pipeline.run_fetch_art_execute(job_id, lambda: True)

    assert db.get_job(job_id)["status"] == "cancelled"


def test_execute_skips_missing_dir(tmp_path):
    gone_dir = tmp_path / "Gone" / "Album"
    # Do not create the directory
    job_id = _setup_execute_job([gone_dir])

    with patch.object(pipeline, "extract_embedded_art", return_value=None):
        with patch.object(pipeline, "_read_album_mbid", return_value=None):
            pipeline.run_fetch_art_execute(job_id, lambda: False)

    # Nothing found but no crash; all dirs were missing → 0 not_found logged for missing
    job = db.get_job(job_id)
    assert job["status"] == "done"


def test_execute_empty_plan_returns_done():
    job_id = _setup_execute_job([])
    pipeline.run_fetch_art_execute(job_id, lambda: False)
    assert db.get_job(job_id)["status"] == "done"


# ── worker routing + API validation ──────────────────────────────────────────

def test_worker_routes_fetch_art(monkeypatch):
    calls = []
    monkeypatch.setattr(jobs, "run_fetch_art_resolve", lambda jid, url: calls.append(("resolve", jid, url)))
    monkeypatch.setattr(jobs, "run_fetch_art_execute", lambda jid, cc: calls.append(("execute", jid)))

    jobs._process_job({"id": 7, "type": "fetch_art", "url": "library", "status": "queued"})
    jobs._process_job({"id": 7, "type": "fetch_art", "url": "library", "status": "confirmed"})

    assert ("resolve", 7, "library") in calls
    assert ("execute", 7) in calls


def test_api_rejects_fetch_art_with_non_library_url(client):
    r = client.post("/api/jobs", json={"type": "fetch_art", "url": "https://play.qobuz.com/album/123"})
    assert r.status_code == 400
    assert "library" in r.json()["error"]


def test_api_accepts_fetch_art_with_library_url(client):
    r = client.post("/api/jobs", json={"type": "fetch_art", "url": "library"})
    assert r.status_code == 200
    assert "job_id" in r.json()


# ── shared client fixture ─────────────────────────────────────────────────────

@pytest.fixture()
def client(tmp_dirs):
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    import importlib, app.config as cfg, app.db as db_mod
    db_mod.init_db(cfg.DB_FILE)
    with patch("app.jobs.start_worker"), patch("app.jobs.stop_worker"):
        import app.main as main_mod
        importlib.reload(main_mod)
        with TestClient(main_mod.app, raise_server_exceptions=True) as c:
            yield c
