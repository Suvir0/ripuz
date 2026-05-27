"""
Regression tests for tagging scope fix.

Before the fix, _tag_and_move scanned the entire shared DOWNLOADS_DIR, so orphan
dirs from prior runs were re-tagged on every album download.

After the fix, _download_album_list computes the before/after diff and only passes
newly-appeared dirs to _tag_and_move. Orphans are ignored.
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app import db
from app.pipeline import run_discography_download, run_album_pipeline
from app.qobuz_cli import DownloadResult
from app.picard import PicardResult
from app.mover import MoveResult


def _ok_download():
    return DownloadResult(success=True)


def _ok_picard():
    return PicardResult(success=True)


def _ok_move(n=1):
    return MoveResult(moved=[Path(f"/music/a/b/track{i}.FLAC") for i in range(n)])


def _big_disk(path):
    from unittest.mock import MagicMock
    m = MagicMock()
    m.free = 500 * 1024 ** 3
    return m


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


def test_bulk_tagging_ignores_orphan_dirs(tmp_dirs):
    """
    Orphan dirs already in DOWNLOADS_DIR before a download must NOT be tagged.
    Only the dir that appeared after the download should be tagged.
    """
    job_id = db.create_job("discography", "https://play.qobuz.com/artist/scope")
    albums = [
        {"id": "new1", "url": "https://play.qobuz.com/album/new1",
         "title": "New Album", "artist": "Artist", "tracks_count": 1, "duration": 600}
    ]
    _setup_plan(job_id, albums)

    orphan1 = tmp_dirs / "downloads" / "Orphan" / "OldAlbum1"
    orphan2 = tmp_dirs / "downloads" / "Orphan" / "OldAlbum2"
    for d in (orphan1, orphan2):
        d.mkdir(parents=True, exist_ok=True)

    new_dir = tmp_dirs / "downloads" / "Artist" / "New Album"
    new_dir.mkdir(parents=True, exist_ok=True)

    picard_calls = []

    def record_picard(source_dir, **kwargs):
        picard_calls.append(source_dir)
        return _ok_picard()

    # list_album_dirs: before download = orphans, after download = orphans + new_dir
    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs",
               side_effect=[[orphan1, orphan2], [orphan1, orphan2, new_dir]]), \
         patch("app.pipeline.run_picard", side_effect=record_picard), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure",
               return_value={"flac_count": 1, "artists": ["Artist"], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"), \
         patch("app.pipeline.shutil.disk_usage", side_effect=_big_disk):
        ok = run_discography_download(job_id, lambda: False)

    assert ok is True
    assert len(picard_calls) == 1, (
        f"Expected Picard called once (for new_dir only), got {len(picard_calls)}: {picard_calls}"
    )
    assert picard_calls[0] == new_dir


def test_bulk_skip_when_already_downloaded(tmp_dirs):
    """
    If qobuz-dl skips a download (no new dir created), _tag_and_move should not
    be called with any dirs (before == after).
    """
    job_id = db.create_job("discography", "https://play.qobuz.com/artist/skip")
    albums = [
        {"id": "alb1", "url": "https://play.qobuz.com/album/alb1",
         "title": "Album 1", "artist": "Artist", "tracks_count": 1, "duration": 600}
    ]
    _setup_plan(job_id, albums)

    existing_dir = tmp_dirs / "downloads" / "Artist" / "Album 1"
    existing_dir.mkdir(parents=True, exist_ok=True)

    picard_calls = []

    def record_picard(source_dir, **kwargs):
        picard_calls.append(source_dir)
        return _ok_picard()

    # Both before and after return the same dir (qobuz-dl skipped, no new dir created)
    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs",
               side_effect=[[existing_dir], [existing_dir]]), \
         patch("app.pipeline.run_picard", side_effect=record_picard), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure",
               return_value={"flac_count": 1, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"), \
         patch("app.pipeline.shutil.disk_usage", side_effect=_big_disk):
        run_discography_download(job_id, lambda: False)

    assert picard_calls == [], (
        f"Expected no Picard calls (qobuz-dl skipped), got {picard_calls}"
    )


def test_simple_pipeline_tagging_ignores_orphans(tmp_dirs):
    """
    Same scoping guarantee for simple (one-shot) pipelines: only newly-appeared
    dirs get tagged, not pre-existing orphans.
    """
    job_id = db.create_job("album", "https://play.qobuz.com/album/new")

    orphan = tmp_dirs / "downloads" / "Orphan" / "Leftover"
    orphan.mkdir(parents=True, exist_ok=True)

    new_dir = tmp_dirs / "downloads" / "Artist" / "Fresh"
    new_dir.mkdir(parents=True, exist_ok=True)

    picard_calls = []

    def record_picard(source_dir, **kwargs):
        picard_calls.append(source_dir)
        return _ok_picard()

    with patch("app.pipeline.run_download", return_value=_ok_download()), \
         patch("app.pipeline.list_album_dirs",
               side_effect=[[orphan], [orphan, new_dir]]), \
         patch("app.pipeline.run_picard", side_effect=record_picard), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure",
               return_value={"flac_count": 1, "artists": [], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        ok = run_album_pipeline(job_id, "https://play.qobuz.com/album/new")

    assert ok is True
    assert len(picard_calls) == 1
    assert picard_calls[0] == new_dir
