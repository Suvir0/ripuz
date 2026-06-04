"""
Tests for the retag-library feature: scan the music library for untagged /
not-Picard-matched FLACs and tag them in place with Picard.
"""
import json
from pathlib import Path

import pytest

from app import config, db, jobs, pipeline
from app import library
from app import picard as picard_mod
from app.library import file_needs_tagging, scan_untagged_albums


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_flac(path: Path) -> Path:
    """Create an empty placeholder .flac (discovery globs by suffix, not content)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


_FULL_TAGS = {
    "title": ["Song"],
    "album": ["Album"],
    "artist": ["Artist"],
    "musicbrainz_trackid": ["mbid-123"],
}


# ── file_needs_tagging ──────────────────────────────────────────────────────────

def test_fully_tagged_file_is_skipped():
    assert file_needs_tagging(Path("x.flac"), tags=dict(_FULL_TAGS)) is False


def test_albumartist_and_recordingid_satisfy_groups():
    tags = {
        "title": ["Song"],
        "album": ["Album"],
        "albumartist": ["Artist"],
        "musicbrainz_recordingid": ["rec-1"],
    }
    assert file_needs_tagging(Path("x.flac"), tags=tags) is False


def test_missing_mbid_needs_tagging():
    tags = dict(_FULL_TAGS)
    tags["musicbrainz_trackid"] = [""]  # present but empty
    assert file_needs_tagging(Path("x.flac"), tags=tags) is True


def test_missing_core_tag_needs_tagging():
    tags = {"title": ["Song"], "album": ["Album"], "musicbrainz_trackid": ["x"]}
    assert file_needs_tagging(Path("x.flac"), tags=tags) is True  # no artist


def test_no_tags_at_all_needs_tagging():
    assert file_needs_tagging(Path("x.flac"), tags={}) is True


# ── scan_untagged_albums ────────────────────────────────────────────────────────

def test_scan_flags_only_dirs_with_untagged_files(monkeypatch):
    music = config.MUSIC_DIR
    good = _make_flac(music / "ACDC" / "Back in Black" / "good.flac")
    bad = _make_flac(music / "Foo" / "Bar" / "bad.flac")

    def fake_read(path):
        return dict(_FULL_TAGS) if path.name == "good.flac" else {}

    monkeypatch.setattr(library, "_read_tags", fake_read)

    scan = scan_untagged_albums(music)

    assert scan["scanned_files"] == 2
    assert scan["untagged_files"] == 1
    assert scan["album_count"] == 1
    assert str(bad.parent) in scan["dirs"]
    assert str(good.parent) not in scan["dirs"]


# ── resolve phase ────────────────────────────────────────────────────────────────

def test_resolve_builds_plan_and_awaits_confirm(monkeypatch):
    music = config.MUSIC_DIR
    _make_flac(music / "Good" / "Album" / "g.flac")
    bad = _make_flac(music / "Bad" / "Album" / "b.flac")

    def fake_read(path):
        return dict(_FULL_TAGS) if path.name == "g.flac" else {}

    monkeypatch.setattr(library, "_read_tags", fake_read)

    job_id = db.create_job("retag_library", "library")
    result = pipeline.run_retag_library_resolve(job_id, "library")

    assert result is True
    job = db.get_job(job_id)
    assert job["status"] == "awaiting_confirm"
    plan = json.loads(job["plan"])
    assert plan["album_count"] == 1
    assert str(bad.parent) in plan["dirs"]
    assert plan["untagged_files"] == 1
    assert plan["scanned_files"] == 2


def test_resolve_empty_library_has_nothing_to_do(monkeypatch):
    job_id = db.create_job("retag_library", "library")
    result = pipeline.run_retag_library_resolve(job_id, "library")
    assert result is False
    job = db.get_job(job_id)
    assert job["status"] == "awaiting_confirm"
    assert json.loads(job["plan"])["album_count"] == 0


# ── execute phase ────────────────────────────────────────────────────────────────

def test_execute_runs_picard_per_dir_with_lookup(monkeypatch):
    music = config.MUSIC_DIR
    d1 = music / "A" / "Album1"
    d2 = music / "B" / "Album2"
    _make_flac(d1 / "t.flac")
    _make_flac(d2 / "t.flac")

    seen = []

    def fake_picard(source_dir, log_callback=None, lookup=None, **kw):
        seen.append((source_dir, lookup))
        return picard_mod.PicardResult(success=True)

    monkeypatch.setattr(pipeline, "run_picard", fake_picard)

    job_id = db.create_job("retag_library", "library")
    db.set_job_plan(job_id, json.dumps({"dirs": [str(d1), str(d2)]}))
    db.update_job(job_id, status="confirmed")

    ok = pipeline.run_retag_library_execute(job_id, lambda: False)

    assert ok is True
    assert [s[0] for s in seen] == [d1, d2]
    assert all(s[1] is True for s in seen)  # lookup forced on
    assert db.get_job(job_id)["status"] == "done"


def test_execute_reports_picard_failure_as_warning(monkeypatch):
    music = config.MUSIC_DIR
    d1 = music / "A" / "Album1"
    _make_flac(d1 / "t.flac")

    def fake_picard(source_dir, log_callback=None, lookup=None, **kw):
        return picard_mod.PicardResult(success=False, error_message="boom")

    monkeypatch.setattr(pipeline, "run_picard", fake_picard)

    job_id = db.create_job("retag_library", "library")
    db.set_job_plan(job_id, json.dumps({"dirs": [str(d1)]}))

    ok = pipeline.run_retag_library_execute(job_id, lambda: False)

    assert ok is False
    assert db.get_job(job_id)["status"] == "done_with_warnings"


def test_execute_cancel_before_first_album(monkeypatch):
    called = []
    monkeypatch.setattr(
        pipeline, "run_picard",
        lambda *a, **k: called.append(1) or picard_mod.PicardResult(success=True),
    )
    job_id = db.create_job("retag_library", "library")
    db.set_job_plan(job_id, json.dumps({"dirs": ["/music/A/Album1"]}))
    db.update_job(job_id, status="confirmed")

    ok = pipeline.run_retag_library_execute(job_id, lambda: True)

    assert ok is False
    assert called == []  # Picard never ran
    assert db.get_job(job_id)["status"] == "cancelled"


def test_execute_empty_plan_is_done(monkeypatch):
    job_id = db.create_job("retag_library", "library")
    db.set_job_plan(job_id, json.dumps({"dirs": []}))
    ok = pipeline.run_retag_library_execute(job_id, lambda: False)
    assert ok is True
    assert db.get_job(job_id)["status"] == "done"


# ── worker routing ───────────────────────────────────────────────────────────────

def test_worker_routes_retag_library(monkeypatch):
    calls = []
    monkeypatch.setattr(
        jobs, "run_retag_library_resolve",
        lambda jid, url: calls.append(("resolve", jid, url)),
    )
    monkeypatch.setattr(
        jobs, "run_retag_library_execute",
        lambda jid, cc: calls.append(("execute", jid)),
    )

    jobs._process_job({"id": 7, "type": "retag_library", "url": "library", "status": "queued"})
    jobs._process_job({"id": 7, "type": "retag_library", "url": "library", "status": "confirmed"})

    assert ("resolve", 7, "library") in calls
    assert ("execute", 7) in calls


# ── picard lookup override ───────────────────────────────────────────────────────

def test_build_picard_command_lookup_override(monkeypatch):
    monkeypatch.setattr(picard_mod, "PICARD_LOOKUP", False)
    cmd_on = picard_mod.build_picard_command(Path("/x"), lookup=True)
    cmd_off = picard_mod.build_picard_command(Path("/x"), lookup=False)
    cmd_default = picard_mod.build_picard_command(Path("/x"))

    assert "LOOKUP clustered" in cmd_on
    assert "LOOKUP clustered" not in cmd_off
    assert "LOOKUP clustered" not in cmd_default  # follows global default


# ── API validation ───────────────────────────────────────────────────────────────

async def test_api_create_retag_library_ok():
    from app.main import api_create_job
    res = await api_create_job({"type": "retag_library", "url": "library"})
    assert "job_id" in res


async def test_api_retag_library_rejects_url():
    from app.main import api_create_job
    res = await api_create_job(
        {"type": "retag_library", "url": "https://open.qobuz.com/album/abc123"}
    )
    assert getattr(res, "status_code", 200) == 400
