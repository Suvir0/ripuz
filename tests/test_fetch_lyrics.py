"""
Tests for the fetch-lyrics feature: scan the music library for FLACs that
have no .lrc sidecar, fetch lyrics from LRCLIB, and write them in place.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import respx
import httpx

from app import config, db, jobs, pipeline
from app import lyrics_library
from app.lyrics_library import (
    file_needs_lyrics,
    scan_missing_lyrics,
    fetch_lrc,
    write_lrc,
    _read_track_meta,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_flac(path: Path) -> Path:
    """Create an empty placeholder .flac (discovery globs by suffix, not content)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


_META = {"artist": "Artist", "title": "Song", "album": "Album", "duration": 180}


# ── file_needs_lyrics ──────────────────────────────────────────────────────────

def test_needs_lyrics_when_no_sidecar(tmp_path):
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"")
    assert file_needs_lyrics(flac) is True


def test_does_not_need_lyrics_when_sidecar_exists(tmp_path):
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"")
    (tmp_path / "song.lrc").write_text("[00:00.00] lyrics", encoding="utf-8")
    assert file_needs_lyrics(flac) is False


def test_lrc_must_have_same_stem(tmp_path):
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"")
    (tmp_path / "other.lrc").write_text("[00:00.00] lyrics", encoding="utf-8")
    # a .lrc with a different stem does NOT count
    assert file_needs_lyrics(flac) is True


# ── scan_missing_lyrics ────────────────────────────────────────────────────────

def test_scan_flags_only_files_without_sidecar():
    music = config.MUSIC_DIR
    has_lrc = _make_flac(music / "Artist1" / "Album1" / "has.flac")
    (has_lrc.with_suffix(".lrc")).write_text("[00:00.00] ok", encoding="utf-8")
    missing = _make_flac(music / "Artist2" / "Album2" / "missing.flac")

    scan = scan_missing_lyrics(music)

    assert scan["scanned_files"] == 2
    assert scan["missing_files"] == 1
    assert scan["album_count"] == 1
    assert str(missing) in scan["files"]
    assert str(has_lrc) not in scan["files"]
    assert str(missing.parent) in scan["dirs"]
    assert str(has_lrc.parent) not in scan["dirs"]


def test_scan_empty_music_dir():
    scan = scan_missing_lyrics(config.MUSIC_DIR)
    assert scan == {
        "files": [],
        "dirs": [],
        "scanned_files": 0,
        "missing_files": 0,
        "album_count": 0,
    }


def test_scan_all_have_sidecars():
    music = config.MUSIC_DIR
    flac = _make_flac(music / "A" / "B" / "track.flac")
    flac.with_suffix(".lrc").write_text("[00:00.00] already", encoding="utf-8")

    scan = scan_missing_lyrics(music)

    assert scan["scanned_files"] == 1
    assert scan["missing_files"] == 0
    assert scan["album_count"] == 0


def test_scan_multiple_missing_in_same_album():
    music = config.MUSIC_DIR
    d = music / "Band" / "LP"
    _make_flac(d / "t1.flac")
    _make_flac(d / "t2.flac")

    scan = scan_missing_lyrics(music)

    assert scan["missing_files"] == 2
    assert scan["album_count"] == 1  # same dir counted once


# ── fetch_lrc ──────────────────────────────────────────────────────────────────

@respx.mock
def test_fetch_lrc_returns_synced_from_exact_lookup():
    route = respx.get("https://lrclib.net/api/get").mock(
        return_value=httpx.Response(200, json={
            "syncedLyrics": "[00:01.00] hello",
            "plainLyrics": "hello",
        })
    )
    result = fetch_lrc(_META)
    assert result == "[00:01.00] hello"
    assert route.called


@respx.mock
def test_fetch_lrc_falls_back_to_plain_when_synced_empty():
    respx.get("https://lrclib.net/api/get").mock(
        return_value=httpx.Response(200, json={
            "syncedLyrics": "",
            "plainLyrics": "just plain text",
        })
    )
    result = fetch_lrc(_META)
    assert result == "just plain text"


@respx.mock
def test_fetch_lrc_falls_back_to_plain_when_synced_null():
    respx.get("https://lrclib.net/api/get").mock(
        return_value=httpx.Response(200, json={
            "syncedLyrics": None,
            "plainLyrics": "plain only",
        })
    )
    result = fetch_lrc(_META)
    assert result == "plain only"


@respx.mock
def test_fetch_lrc_search_fallback_on_404():
    respx.get("https://lrclib.net/api/get").mock(
        return_value=httpx.Response(404, json={"message": "not found"})
    )
    respx.get("https://lrclib.net/api/search").mock(
        return_value=httpx.Response(200, json=[
            {
                "syncedLyrics": "[00:01.00] from search",
                "plainLyrics": "from search",
                "duration": 180,  # within ±2s of meta duration
            }
        ])
    )
    result = fetch_lrc(_META)
    assert result == "[00:01.00] from search"


@respx.mock
def test_fetch_lrc_search_skips_wrong_duration():
    respx.get("https://lrclib.net/api/get").mock(
        return_value=httpx.Response(404, json={})
    )
    respx.get("https://lrclib.net/api/search").mock(
        return_value=httpx.Response(200, json=[
            {
                # duration is 30 s off — should be skipped
                "syncedLyrics": "[00:01.00] wrong",
                "plainLyrics": "wrong",
                "duration": 210,
            }
        ])
    )
    result = fetch_lrc(_META)
    assert result is None


@respx.mock
def test_fetch_lrc_returns_none_when_nothing_found():
    respx.get("https://lrclib.net/api/get").mock(
        return_value=httpx.Response(404, json={})
    )
    respx.get("https://lrclib.net/api/search").mock(
        return_value=httpx.Response(200, json=[])
    )
    result = fetch_lrc(_META)
    assert result is None


@respx.mock
def test_fetch_lrc_returns_none_on_network_error():
    respx.get("https://lrclib.net/api/get").mock(side_effect=httpx.ConnectError("down"))
    result = fetch_lrc(_META)
    assert result is None


# ── write_lrc ──────────────────────────────────────────────────────────────────

def test_write_lrc_creates_sidecar(tmp_path):
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"")
    dest = write_lrc(flac, "[00:01.00] hello")
    assert dest == flac.with_suffix(".lrc")
    assert dest.read_text(encoding="utf-8") == "[00:01.00] hello"


# ── resolve phase ─────────────────────────────────────────────────────────────

def test_resolve_builds_plan_and_awaits_confirm():
    music = config.MUSIC_DIR
    has_lrc = _make_flac(music / "A" / "Album" / "has.flac")
    has_lrc.with_suffix(".lrc").write_text("[00:00.00] ok", encoding="utf-8")
    missing = _make_flac(music / "B" / "Album" / "missing.flac")

    job_id = db.create_job("fetch_lyrics", "library")
    result = pipeline.run_fetch_lyrics_resolve(job_id, "library")

    assert result is True
    job = db.get_job(job_id)
    assert job["status"] == "awaiting_confirm"
    plan = json.loads(job["plan"])
    assert plan["missing_files"] == 1
    assert plan["scanned_files"] == 2
    assert plan["album_count"] == 1
    assert str(missing) in plan["files"]
    assert str(has_lrc) not in plan["files"]


def test_resolve_empty_library_nothing_to_do():
    job_id = db.create_job("fetch_lyrics", "library")
    result = pipeline.run_fetch_lyrics_resolve(job_id, "library")
    assert result is False
    job = db.get_job(job_id)
    assert job["status"] == "awaiting_confirm"
    assert json.loads(job["plan"])["missing_files"] == 0


# ── execute phase ─────────────────────────────────────────────────────────────

def test_execute_writes_lrc_for_each_file(monkeypatch, tmp_path):
    flac1 = tmp_path / "t1.flac"
    flac2 = tmp_path / "t2.flac"
    flac1.write_bytes(b"")
    flac2.write_bytes(b"")

    monkeypatch.setattr(pipeline, "_read_track_meta", lambda p: dict(_META, title=p.stem))
    monkeypatch.setattr(pipeline, "fetch_lrc", lambda meta, **kw: f"[00:00.00] {meta['title']}")

    job_id = db.create_job("fetch_lyrics", "library")
    db.set_job_plan(job_id, json.dumps({
        "files": [str(flac1), str(flac2)],
        "missing_files": 2,
    }))
    db.update_job(job_id, status="confirmed")

    ok = pipeline.run_fetch_lyrics_execute(job_id, lambda: False)

    assert ok is True
    assert db.get_job(job_id)["status"] == "done"
    assert flac1.with_suffix(".lrc").exists()
    assert flac2.with_suffix(".lrc").exists()
    assert flac1.with_suffix(".lrc").read_text() == "[00:00.00] t1"
    assert flac2.with_suffix(".lrc").read_text() == "[00:00.00] t2"


def test_execute_skips_file_that_already_has_sidecar(monkeypatch, tmp_path):
    flac = tmp_path / "track.flac"
    flac.write_bytes(b"")
    lrc = flac.with_suffix(".lrc")
    lrc.write_text("[00:00.00] already", encoding="utf-8")

    fetch_calls = []
    monkeypatch.setattr(pipeline, "_read_track_meta", lambda p: dict(_META))
    monkeypatch.setattr(
        pipeline, "fetch_lrc",
        lambda meta, **kw: fetch_calls.append(1) or "[00:00.00] new"
    )

    job_id = db.create_job("fetch_lyrics", "library")
    db.set_job_plan(job_id, json.dumps({"files": [str(flac)], "missing_files": 1}))
    db.update_job(job_id, status="confirmed")

    ok = pipeline.run_fetch_lyrics_execute(job_id, lambda: False)

    assert ok is True
    assert fetch_calls == []  # fetch was never called
    assert lrc.read_text() == "[00:00.00] already"  # original unchanged


def test_execute_records_warning_when_no_lyrics_found(monkeypatch, tmp_path):
    flac = tmp_path / "track.flac"
    flac.write_bytes(b"")

    monkeypatch.setattr(pipeline, "_read_track_meta", lambda p: dict(_META))
    monkeypatch.setattr(pipeline, "fetch_lrc", lambda meta, **kw: None)

    job_id = db.create_job("fetch_lyrics", "library")
    db.set_job_plan(job_id, json.dumps({"files": [str(flac)], "missing_files": 1}))
    db.update_job(job_id, status="confirmed")

    ok = pipeline.run_fetch_lyrics_execute(job_id, lambda: False)

    assert ok is True  # not found is a warning, not a hard failure
    assert db.get_job(job_id)["status"] == "done_with_warnings"
    assert not flac.with_suffix(".lrc").exists()


def test_execute_cancel_aborts_before_first_file(monkeypatch, tmp_path):
    flac = tmp_path / "track.flac"
    flac.write_bytes(b"")

    fetch_calls = []
    monkeypatch.setattr(pipeline, "_read_track_meta", lambda p: dict(_META))
    monkeypatch.setattr(
        pipeline, "fetch_lrc",
        lambda meta, **kw: fetch_calls.append(1) or "[00:00.00] x"
    )

    job_id = db.create_job("fetch_lyrics", "library")
    db.set_job_plan(job_id, json.dumps({"files": [str(flac)], "missing_files": 1}))
    db.update_job(job_id, status="confirmed")

    ok = pipeline.run_fetch_lyrics_execute(job_id, lambda: True)

    assert ok is False
    assert fetch_calls == []
    assert db.get_job(job_id)["status"] == "cancelled"


def test_execute_empty_plan_is_done():
    job_id = db.create_job("fetch_lyrics", "library")
    db.set_job_plan(job_id, json.dumps({"files": [], "missing_files": 0}))
    ok = pipeline.run_fetch_lyrics_execute(job_id, lambda: False)
    assert ok is True
    assert db.get_job(job_id)["status"] == "done"


def test_execute_skips_nonexistent_file(monkeypatch, tmp_path):
    """Files deleted between resolve and execute are silently skipped."""
    gone = tmp_path / "gone.flac"  # never created

    monkeypatch.setattr(pipeline, "_read_track_meta", lambda p: dict(_META))
    monkeypatch.setattr(pipeline, "fetch_lrc", lambda meta, **kw: "[00:00.00] x")

    job_id = db.create_job("fetch_lyrics", "library")
    db.set_job_plan(job_id, json.dumps({"files": [str(gone)], "missing_files": 1}))
    db.update_job(job_id, status="confirmed")

    ok = pipeline.run_fetch_lyrics_execute(job_id, lambda: False)

    assert ok is True
    assert db.get_job(job_id)["status"] == "done"


# ── worker routing ─────────────────────────────────────────────────────────────

def test_worker_routes_fetch_lyrics(monkeypatch):
    calls = []
    monkeypatch.setattr(
        jobs, "run_fetch_lyrics_resolve",
        lambda jid, url: calls.append(("resolve", jid, url)),
    )
    monkeypatch.setattr(
        jobs, "run_fetch_lyrics_execute",
        lambda jid, cc: calls.append(("execute", jid)),
    )

    jobs._process_job({"id": 9, "type": "fetch_lyrics", "url": "library", "status": "queued"})
    jobs._process_job({"id": 9, "type": "fetch_lyrics", "url": "library", "status": "confirmed"})

    assert ("resolve", 9, "library") in calls
    assert ("execute", 9) in calls


# ── API validation ─────────────────────────────────────────────────────────────

async def test_api_create_fetch_lyrics_ok():
    from app.main import api_create_job
    res = await api_create_job({"type": "fetch_lyrics", "url": "library"})
    assert "job_id" in res


async def test_api_fetch_lyrics_rejects_url():
    from app.main import api_create_job
    res = await api_create_job(
        {"type": "fetch_lyrics", "url": "https://open.qobuz.com/album/abc123"}
    )
    assert getattr(res, "status_code", 200) == 400
