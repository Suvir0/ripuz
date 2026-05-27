"""
Tests for cross-job album deduplication.

When a bulk job resolves its plan, albums already claimed by other non-terminal
jobs (by Qobuz album id) are excluded from its download list and counted as
skipped_duplicate. Terminal jobs (done/error/cancelled) do not block new jobs.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from app import db
from app.pipeline import run_discography_resolve


# ── db.claimed_album_ids ───────────────────────────────────────────────────────

def _plan_json(*album_ids):
    albums = [{"id": aid, "url": f"https://play.qobuz.com/album/{aid}",
               "title": f"Album {aid}", "artist": "A",
               "tracks_count": 10, "duration": 2400}
              for aid in album_ids]
    return json.dumps({"albums": albums, "skipped_existing": 0,
                       "est_gb": 1.0, "quality": 27, "capped": False, "cap": 300})


def test_claimed_returns_empty_when_no_other_jobs():
    job_id = db.create_job("discography", "https://play.qobuz.com/artist/1")
    claimed = db.claimed_album_ids(job_id)
    assert claimed == set()


def test_claimed_returns_albums_from_active_job():
    job_a = db.create_job("discography", "https://play.qobuz.com/artist/2")
    db.set_job_plan(job_a, _plan_json("alb1", "alb2"))
    db.update_job(job_a, status="awaiting_confirm")

    job_b = db.create_job("discography", "https://play.qobuz.com/artist/3")
    claimed = db.claimed_album_ids(job_b)
    assert "alb1" in claimed
    assert "alb2" in claimed


def test_claimed_excludes_terminal_done():
    job_a = db.create_job("discography", "https://play.qobuz.com/artist/4")
    db.set_job_plan(job_a, _plan_json("done_alb"))
    db.update_job(job_a, status="done")

    job_b = db.create_job("discography", "https://play.qobuz.com/artist/5")
    claimed = db.claimed_album_ids(job_b)
    assert "done_alb" not in claimed


def test_claimed_excludes_terminal_error():
    job_a = db.create_job("discography", "https://play.qobuz.com/artist/6")
    db.set_job_plan(job_a, _plan_json("err_alb"))
    db.update_job(job_a, status="error")

    job_b = db.create_job("discography", "https://play.qobuz.com/artist/7")
    claimed = db.claimed_album_ids(job_b)
    assert "err_alb" not in claimed


def test_claimed_excludes_terminal_cancelled():
    job_a = db.create_job("discography", "https://play.qobuz.com/artist/8")
    db.set_job_plan(job_a, _plan_json("cxl_alb"))
    db.update_job(job_a, status="cancelled")

    job_b = db.create_job("discography", "https://play.qobuz.com/artist/9")
    claimed = db.claimed_album_ids(job_b)
    assert "cxl_alb" not in claimed


def test_claimed_excludes_own_job_id():
    job_id = db.create_job("discography", "https://play.qobuz.com/artist/10")
    db.set_job_plan(job_id, _plan_json("own_alb"))
    db.update_job(job_id, status="awaiting_confirm")

    claimed = db.claimed_album_ids(job_id)
    assert "own_alb" not in claimed


def test_claimed_handles_empty_plan_gracefully():
    job_a = db.create_job("discography", "https://play.qobuz.com/artist/11")
    # No plan set — plan column is empty string
    db.update_job(job_a, status="awaiting_confirm")

    job_b = db.create_job("discography", "https://play.qobuz.com/artist/12")
    claimed = db.claimed_album_ids(job_b)
    assert claimed == set()


# ── _build_plan dedup via resolve ──────────────────────────────────────────────

def test_resolve_skips_albums_claimed_by_active_job():
    """Albums in another active job's plan must be excluded, counted as skipped_duplicate."""
    import app.settings_store as ss
    ss.save_settings("fake_token")

    # Job A claims "alb1" and "alb2" (awaiting_confirm)
    job_a = db.create_job("discography", "https://play.qobuz.com/artist/20")
    db.set_job_plan(job_a, _plan_json("alb1", "alb2"))
    db.update_job(job_a, status="awaiting_confirm")

    # Job B tries to resolve a discography containing alb1, alb2, alb3
    job_b = db.create_job("discography", "https://play.qobuz.com/artist/21")
    mock_client = MagicMock()
    mock_client.discography_to_album_plan.return_value = [
        {"id": "alb1", "url": "https://play.qobuz.com/album/alb1",
         "title": "Album 1", "artist": "A", "tracks_count": 10, "duration": 2400},
        {"id": "alb2", "url": "https://play.qobuz.com/album/alb2",
         "title": "Album 2", "artist": "A", "tracks_count": 10, "duration": 2400},
        {"id": "alb3", "url": "https://play.qobuz.com/album/alb3",
         "title": "Album 3", "artist": "A", "tracks_count": 10, "duration": 2400},
    ]

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.album_already_present", return_value=False):
        run_discography_resolve(job_b, "https://play.qobuz.com/artist/21")

    plan = json.loads(db.get_job(job_b)["plan"])
    album_ids = [a["id"] for a in plan["albums"]]
    assert "alb1" not in album_ids, "alb1 is claimed by job_a and must be excluded"
    assert "alb2" not in album_ids, "alb2 is claimed by job_a and must be excluded"
    assert "alb3" in album_ids, "alb3 is unclaimed and must be included"
    assert plan["skipped_duplicate"] == 2


def test_resolve_does_not_skip_done_job_albums():
    """Albums in a done job's plan are NOT blocked — they may need re-downloading."""
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_a = db.create_job("discography", "https://play.qobuz.com/artist/30")
    db.set_job_plan(job_a, _plan_json("prev_alb"))
    db.update_job(job_a, status="done")

    job_b = db.create_job("discography", "https://play.qobuz.com/artist/31")
    mock_client = MagicMock()
    mock_client.discography_to_album_plan.return_value = [
        {"id": "prev_alb", "url": "https://play.qobuz.com/album/prev_alb",
         "title": "Prev Album", "artist": "A", "tracks_count": 5, "duration": 1200},
    ]

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.album_already_present", return_value=False):
        run_discography_resolve(job_b, "https://play.qobuz.com/artist/31")

    plan = json.loads(db.get_job(job_b)["plan"])
    album_ids = [a["id"] for a in plan["albums"]]
    assert "prev_alb" in album_ids
    assert plan.get("skipped_duplicate", 0) == 0


def test_resolve_plan_log_includes_duplicate_count():
    """When duplicates exist, the plan summary log must mention how many were skipped."""
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_a = db.create_job("discography", "https://play.qobuz.com/artist/40")
    db.set_job_plan(job_a, _plan_json("dup_alb"))
    db.update_job(job_a, status="awaiting_confirm")

    job_b = db.create_job("discography", "https://play.qobuz.com/artist/41")
    mock_client = MagicMock()
    mock_client.discography_to_album_plan.return_value = [
        {"id": "dup_alb", "url": "https://play.qobuz.com/album/dup_alb",
         "title": "Dup Album", "artist": "A", "tracks_count": 5, "duration": 1200},
        {"id": "unique_alb", "url": "https://play.qobuz.com/album/unique_alb",
         "title": "Unique Album", "artist": "A", "tracks_count": 5, "duration": 1200},
    ]

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.album_already_present", return_value=False):
        run_discography_resolve(job_b, "https://play.qobuz.com/artist/41")

    log = db.get_job(job_b)["log"]
    assert "claimed" in log.lower(), f"Log should mention claimed albums: {log}"


def test_resolve_no_duplicate_count_in_log_when_zero():
    """When there are no duplicates, the log must NOT mention 'claimed'."""
    import app.settings_store as ss
    ss.save_settings("fake_token")

    job_id = db.create_job("discography", "https://play.qobuz.com/artist/50")
    mock_client = MagicMock()
    mock_client.discography_to_album_plan.return_value = [
        {"id": "solo_alb", "url": "https://play.qobuz.com/album/solo_alb",
         "title": "Solo Album", "artist": "A", "tracks_count": 5, "duration": 1200},
    ]

    with patch("app.pipeline.make_client", return_value=mock_client), \
         patch("app.pipeline.album_already_present", return_value=False):
        run_discography_resolve(job_id, "https://play.qobuz.com/artist/50")

    log = db.get_job(job_id)["log"]
    assert "claimed" not in log.lower(), f"Log must not mention 'claimed' when count is zero: {log}"
