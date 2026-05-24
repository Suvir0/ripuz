"""
Orchestrates: download → picard tag (per album) → move → verify → cleanup.

Two pipeline types:
  playlist    - qobuz-dl downloads the playlist directly, then each album dir
                is tagged by Picard and moved into MUSIC_DIR.
  expand_albums - QobuzClient resolves all tracks → album IDs, downloads each
                  album individually, then tags and moves each batch.

Picard runs once per album directory (small batch) so that MusicBrainz lookup
never times out on large playlists.  Even when Picard fails for a directory
the files are still moved using qobuz-dl's embedded tags.
"""
import logging
from pathlib import Path
from typing import Callable, Optional

from app import config, db
from app.qobuz_cli import run_download
from app.qobuz_client import make_client, album_url_from_id, artist_url_from_id
from app.picard import run_picard
from app.mover import move_album
from app.structure import clean_empty_dirs, list_album_dirs, verify_structure
from app.settings_store import get_token, get_quality

logger = logging.getLogger(__name__)

LogCallback = Callable[[str], None]


def _log(job_id: int, msg: str, callback: Optional[LogCallback] = None):
    db.append_job_log(job_id, msg + "\n")
    logger.info("[job %d] %s", job_id, msg)
    if callback:
        callback(msg + "\n")


def _tag_and_move(job_id: int) -> tuple[int, int]:
    """
    For every album directory found in DOWNLOADS_DIR:
      1. Run Picard to enrich tags in place (best-effort; proceed even on failure).
      2. Move files to MUSIC_DIR using mutagen-read tags.

    Returns (total_moved, total_skipped).
    """
    album_dirs = list_album_dirs(config.DOWNLOADS_DIR)
    _log(job_id, f"[pipeline] {len(album_dirs)} album dir(s) to tag and move")

    total_moved = 0
    total_skipped = 0

    for i, album_dir in enumerate(album_dirs, 1):
        _log(job_id, f"[pipeline] ({i}/{len(album_dirs)}) tagging: {album_dir.name}")
        db.update_job(job_id, status="tagging")

        picard_result = run_picard(
            source_dir=album_dir,
            log_callback=lambda l: db.append_job_log(job_id, l),
        )
        if not picard_result.success:
            _log(
                job_id,
                f"[pipeline] Picard failed on {album_dir.name}: "
                f"{picard_result.error_message} — moving with existing tags",
            )

        move_result = move_album(album_dir, config.MUSIC_DIR)
        total_moved += len(move_result.moved)
        total_skipped += len(move_result.skipped)
        _log(
            job_id,
            f"[pipeline] moved {len(move_result.moved)} file(s)"
            + (f", skipped {len(move_result.skipped)}" if move_result.skipped else ""),
        )
        for err in move_result.errors:
            _log(job_id, f"[pipeline] move error: {err}")

    return total_moved, total_skipped


def run_playlist_pipeline(job_id: int, playlist_url: str) -> bool:
    """Download a Qobuz playlist then tag+move with Picard. Returns True on success."""
    _log(job_id, f"[pipeline] downloading playlist: {playlist_url}")
    db.update_job(job_id, status="downloading")

    dl_result = run_download(
        playlist_url,
        downloads_dir=config.DOWNLOADS_DIR,
        quality=get_quality(),
        log_callback=lambda l: db.append_job_log(job_id, l),
    )

    if not dl_result.success:
        _log(job_id, f"[pipeline] download failed: {dl_result.error_message}")
        db.update_job(job_id, status="error")
        return False

    _log(job_id, "[pipeline] download done — starting per-album tagging")

    total_moved, total_skipped = _tag_and_move(job_id)

    _log(job_id, "[pipeline] tagging done — verifying structure")
    db.update_job(job_id, status="verifying")

    stats = verify_structure(config.MUSIC_DIR)
    _log(
        job_id,
        f"[pipeline] music dir: {stats['flac_count']} FLAC file(s), "
        f"{len(stats['artists'])} artist(s)",
    )
    for issue in stats["issues"]:
        _log(job_id, f"[pipeline] warning: {issue}")

    clean_empty_dirs(config.DOWNLOADS_DIR)

    if total_moved == 0:
        _log(job_id, "[pipeline] error: no files were moved to music dir")
        db.update_job(job_id, status="error")
        return False

    status = "done" if total_skipped == 0 else "done_with_warnings"
    db.update_job(job_id, status=status)
    _log(job_id, f"[pipeline] complete (moved={total_moved}, skipped={total_skipped})")
    return True


def _simple_download_pipeline(job_id: int, url: str, label: str) -> bool:
    """Shared pipeline for single-item downloads (track, album, discography)."""
    _log(job_id, f"[pipeline/{label}] downloading: {url}")
    db.update_job(job_id, status="downloading")

    dl_result = run_download(
        url,
        downloads_dir=config.DOWNLOADS_DIR,
        quality=get_quality(),
        log_callback=lambda l: db.append_job_log(job_id, l),
    )

    if not dl_result.success:
        _log(job_id, f"[pipeline/{label}] download failed: {dl_result.error_message}")
        db.update_job(job_id, status="error")
        return False

    _log(job_id, f"[pipeline/{label}] download done — starting per-album tagging")

    total_moved, total_skipped = _tag_and_move(job_id)

    stats = verify_structure(config.MUSIC_DIR)
    _log(
        job_id,
        f"[pipeline/{label}] music dir: {stats['flac_count']} FLAC file(s), "
        f"{len(stats['artists'])} artist(s)",
    )
    for issue in stats["issues"]:
        _log(job_id, f"[pipeline/{label}] warning: {issue}")

    clean_empty_dirs(config.DOWNLOADS_DIR)

    if total_moved == 0:
        _log(job_id, f"[pipeline/{label}] error: no files were moved to music dir")
        db.update_job(job_id, status="error")
        return False

    status = "done" if total_skipped == 0 else "done_with_warnings"
    db.update_job(job_id, status=status)
    _log(job_id, f"[pipeline/{label}] complete (moved={total_moved}, skipped={total_skipped})")
    return True


def run_track_pipeline(job_id: int, track_url: str) -> bool:
    """Download a single Qobuz track, tag, and move."""
    return _simple_download_pipeline(job_id, track_url, "track")


def run_album_pipeline(job_id: int, album_url: str) -> bool:
    """Download a single Qobuz album, tag, and move."""
    return _simple_download_pipeline(job_id, album_url, "album")


def run_discography_pipeline(job_id: int, artist_url: str) -> bool:
    """Download a full artist discography, tag, and move."""
    return _simple_download_pipeline(job_id, artist_url, "discography")


def run_expand_discographies_pipeline(job_id: int, playlist_url: str) -> bool:
    """
    For every track in the playlist, find its artist on Qobuz, deduplicate,
    then download each artist's full discography, tag, and move.
    """
    _log(job_id, f"[pipeline/expand-disco] resolving artists from playlist: {playlist_url}")
    db.update_job(job_id, status="resolving")

    token = get_token()
    if not token:
        _log(job_id, "[pipeline/expand-disco] error: no Qobuz token configured")
        db.update_job(job_id, status="error")
        return False

    client = make_client(token)

    try:
        artist_ids = client.playlist_to_artist_ids(playlist_url)
    except Exception as exc:
        _log(job_id, f"[pipeline/expand-disco] failed to resolve artists: {exc}")
        db.update_job(job_id, status="error")
        return False

    _log(job_id, f"[pipeline/expand-disco] {len(artist_ids)} unique artist(s) to download")

    quality = get_quality()
    dl_ok = True
    for idx, artist_id in enumerate(artist_ids, 1):
        url = artist_url_from_id(artist_id)
        _log(job_id, f"[pipeline/expand-disco] ({idx}/{len(artist_ids)}) downloading {url}")
        db.update_job(job_id, status="downloading")

        dl_result = run_download(
            url,
            downloads_dir=config.DOWNLOADS_DIR,
            quality=quality,
            log_callback=lambda l: db.append_job_log(job_id, l),
        )
        if not dl_result.success:
            _log(
                job_id,
                f"[pipeline/expand-disco] artist {artist_id} download failed: "
                f"{dl_result.error_message}",
            )
            dl_ok = False

    _log(job_id, "[pipeline/expand-disco] all downloads done — starting per-album tagging")

    total_moved, total_skipped = _tag_and_move(job_id)

    stats = verify_structure(config.MUSIC_DIR)
    _log(
        job_id,
        f"[pipeline/expand-disco] music dir: {stats['flac_count']} FLAC file(s), "
        f"{len(stats['artists'])} artist(s)",
    )

    clean_empty_dirs(config.DOWNLOADS_DIR)

    if total_moved == 0:
        _log(job_id, "[pipeline/expand-disco] error: no files were moved to music dir")
        db.update_job(job_id, status="error")
        return False

    all_ok = dl_ok and total_skipped == 0
    final_status = "done" if all_ok else "done_with_warnings"
    db.update_job(job_id, status=final_status)
    _log(
        job_id,
        f"[pipeline/expand-disco] complete (status={final_status}, "
        f"moved={total_moved}, skipped={total_skipped})",
    )
    return dl_ok


def run_expand_albums_pipeline(job_id: int, playlist_url: str) -> bool:
    """
    For every song in the playlist, find its album on Qobuz, deduplicate, then
    download each full album, tag, and move.
    """
    _log(job_id, f"[pipeline/expand] resolving albums from playlist: {playlist_url}")
    db.update_job(job_id, status="resolving")

    token = get_token()
    if not token:
        _log(job_id, "[pipeline/expand] error: no Qobuz token configured")
        db.update_job(job_id, status="error")
        return False

    client = make_client(token)

    try:
        album_ids = client.playlist_to_album_ids(playlist_url)
    except Exception as exc:
        _log(job_id, f"[pipeline/expand] failed to resolve albums: {exc}")
        db.update_job(job_id, status="error")
        return False

    _log(job_id, f"[pipeline/expand] {len(album_ids)} unique album(s) to download")

    quality = get_quality()
    dl_ok = True
    for idx, album_id in enumerate(album_ids, 1):
        album_url = album_url_from_id(album_id)
        _log(job_id, f"[pipeline/expand] ({idx}/{len(album_ids)}) downloading {album_url}")
        db.update_job(job_id, status="downloading")

        dl_result = run_download(
            album_url,
            downloads_dir=config.DOWNLOADS_DIR,
            quality=quality,
            log_callback=lambda l: db.append_job_log(job_id, l),
        )
        if not dl_result.success:
            _log(
                job_id,
                f"[pipeline/expand] album {album_id} download failed: "
                f"{dl_result.error_message}",
            )
            dl_ok = False

    _log(job_id, "[pipeline/expand] all downloads done — starting per-album tagging")

    total_moved, total_skipped = _tag_and_move(job_id)

    stats = verify_structure(config.MUSIC_DIR)
    _log(
        job_id,
        f"[pipeline/expand] music dir: {stats['flac_count']} FLAC file(s), "
        f"{len(stats['artists'])} artist(s)",
    )

    clean_empty_dirs(config.DOWNLOADS_DIR)

    if total_moved == 0:
        _log(job_id, "[pipeline/expand] error: no files were moved to music dir")
        db.update_job(job_id, status="error")
        return False

    all_ok = dl_ok and total_skipped == 0
    final_status = "done" if all_ok else "done_with_warnings"
    db.update_job(job_id, status=final_status)
    _log(
        job_id,
        f"[pipeline/expand] complete (status={final_status}, "
        f"moved={total_moved}, skipped={total_skipped})",
    )
    return dl_ok
