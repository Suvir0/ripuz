"""
Orchestrates: download → picard tag (per album) → move → verify → cleanup.

Pipeline types
  track / album / playlist   - one-shot download, no confirm gate
  discography                - resolve artist albums → confirm gate → download each album
  expand_albums              - resolve playlist → album list → confirm gate → download each
  expand_discographies       - resolve playlist → artist catalogs → confirm gate → download each

All bulk pipelines (discography, expand_*) are split into two phases:
  resolve  – API calls only, builds a plan, sets status awaiting_confirm, returns.
  download – reads plan from DB, downloads album-by-album with disk guard + cancel.

Picard runs once per album directory so MusicBrainz lookup never times out.
Even when Picard fails the files are moved using qobuz-dl's embedded tags.
"""
import json
import logging
import shutil
from pathlib import Path
from typing import Callable, Optional

from app import config, db
from app.qobuz_cli import run_download
from app.qobuz_client import make_client, album_url_from_id
from app.picard import run_picard
from app.mover import move_album
from app.structure import clean_empty_dirs, list_album_dirs, verify_structure, album_already_present
from app.library import scan_untagged_albums
from app.lyrics_library import (
    scan_missing_lyrics,
    file_needs_lyrics,
    _read_track_meta,
    fetch_lrc,
    write_lrc,
)
from app.settings_store import get_token, get_quality, get_prefer_explicit

logger = logging.getLogger(__name__)

LogCallback = Callable[[str], None]

# Estimated MB downloaded per minute of audio, by Qobuz quality tier.
_MB_PER_MIN: dict[int, float] = {27: 50.0, 7: 25.0, 6: 10.0, 5: 2.4}

_BULK_TYPES = {"discography", "expand_albums", "expand_discographies", "explicit_upgrade", "retag_library"}


def _log(job_id: int, msg: str, callback: Optional[LogCallback] = None):
    db.append_job_log(job_id, msg + "\n")
    logger.info("[job %d] %s", job_id, msg)
    if callback:
        callback(msg + "\n")


# ── helpers ───────────────────────────────────────────────────────────────────

def _tag_and_move(job_id: int, album_dirs: list[Path]) -> tuple[int, int]:
    """
    Tag and move an explicit list of album directories (caller provides the diff).
    1. Run Picard to enrich tags in place (best-effort; proceed even on failure).
    2. Move files to MUSIC_DIR using mutagen-read tags.

    Returns (total_moved, total_skipped).
    """
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


def _check_disk(job_id: int, label: str) -> bool:
    """Return True if free space is above DISK_FLOOR_GB, False (and log) otherwise."""
    try:
        free_gb = shutil.disk_usage(config.DOWNLOADS_DIR).free / (1024 ** 3)
    except OSError:
        return True  # can't check — allow it
    if free_gb < config.DISK_FLOOR_GB:
        _log(
            job_id,
            f"[pipeline/{label}] abort: only {free_gb:.1f} GB free on downloads dir "
            f"(floor is {config.DISK_FLOOR_GB} GB — set DISK_FLOOR_GB env var to change)",
        )
        return False
    return True


def _estimate_gb(albums: list[dict], quality: int) -> float:
    mb_per_min = _MB_PER_MIN.get(quality, 30.0)
    total_secs = sum(a.get("duration", 0) for a in albums)
    return round(total_secs / 60.0 * mb_per_min / 1024.0, 1)


def _build_plan(albums: list[dict], quality: int, job_id: int,
                skip_present_check: bool = False) -> dict:
    """
    Filter out albums already present in MUSIC_DIR or claimed by another active job,
    apply the per-job album cap, and return a plan dict ready for JSON serialisation.

    skip_present_check=True bypasses the "already present" filter — used by the
    explicit_upgrade pipeline which wants to re-download even if a clean copy exists.
    """
    claimed = db.claimed_album_ids(job_id)
    to_download: list[dict] = []
    skipped_count = 0
    skipped_duplicate = 0
    for album in albums:
        if not skip_present_check and album_already_present(
            config.MUSIC_DIR,
            album.get("artist", ""),
            album.get("title", ""),
            album.get("tracks_count") or None,
        ):
            skipped_count += 1
        elif str(album.get("id", "")) in claimed:
            skipped_duplicate += 1
        else:
            to_download.append(album)

    capped = False
    cap = config.MAX_ALBUMS_PER_JOB
    if len(to_download) > cap:
        to_download = to_download[:cap]
        capped = True

    return {
        "albums": to_download,
        "skipped_existing": skipped_count,
        "skipped_duplicate": skipped_duplicate,
        "est_gb": _estimate_gb(to_download, quality),
        "quality": quality,
        "capped": capped,
        "cap": cap,
    }


def _store_plan(job_id: int, plan: dict, label: str) -> bool:
    """Persist plan, log summary, set status awaiting_confirm. Returns True if albums remain."""
    count = len(plan["albums"])
    skipped = plan["skipped_existing"]
    dup = plan.get("skipped_duplicate", 0)
    est = plan["est_gb"]
    capped = plan.get("capped", False)
    cap_msg = f" (capped at {plan['cap']})" if capped else ""
    dup_msg = f", {dup} claimed by another job" if dup > 0 else ""
    _log(
        job_id,
        f"[pipeline/{label}] plan ready: {count} album(s) to download{cap_msg}, "
        f"{skipped} already present{dup_msg}, ~{est} GB estimated",
    )
    db.set_job_plan(job_id, json.dumps(plan))
    db.update_job(job_id, status="awaiting_confirm")
    if count == 0:
        _log(job_id, f"[pipeline/{label}] nothing to download — all albums already present")
    return count > 0


def _download_album_list(
    job_id: int,
    albums: list[dict],
    quality: int,
    label: str,
    cancel_check: Callable[[], bool],
    no_db: bool = False,
) -> tuple[int, int, int, bool, bool]:
    """
    Download each album with disk guard + cancel check + incremental tag/move/clean.
    Returns (moved, skipped, failed, was_cancelled, disk_aborted).

    no_db: when True, passes --no-db to qobuz-dl so it ignores its local download
           database (used by explicit_upgrade to force re-download).
    """
    total_moved = total_skipped = total_failed = 0

    for i, album in enumerate(albums, 1):
        if cancel_check():
            _log(job_id, f"[pipeline/{label}] cancelled between albums")
            return total_moved, total_skipped, total_failed, True, False

        if not _check_disk(job_id, label):
            db.update_job(job_id, status="error")
            return total_moved, total_skipped, total_failed, False, True

        url = album["url"]
        artist = album.get("artist", "")
        title = album.get("title", album["id"])
        desc = f"{artist} — {title}" if artist else title
        _log(job_id, f"[pipeline/{label}] ({i}/{len(albums)}) downloading: {desc}")
        db.update_job(job_id, status="downloading")

        before = set(list_album_dirs(config.DOWNLOADS_DIR))

        dl_result = run_download(
            url,
            downloads_dir=config.DOWNLOADS_DIR,
            quality=quality,
            log_callback=lambda l: db.append_job_log(job_id, l),
            job_id=job_id,
            cancel_check=cancel_check,
            no_db=no_db,
        )

        if dl_result.cancelled:
            _log(job_id, f"[pipeline/{label}] download cancelled")
            return total_moved, total_skipped, total_failed, True, False

        if not dl_result.success:
            _log(job_id, f"[pipeline/{label}] download failed: {dl_result.error_message}")
            total_failed += 1
            continue

        # Tag + move only dirs that appeared after this specific download.
        new_dirs = sorted(set(list_album_dirs(config.DOWNLOADS_DIR)) - before)
        moved, skipped = _tag_and_move(job_id, new_dirs)
        total_moved += moved
        total_skipped += skipped
        clean_empty_dirs(config.DOWNLOADS_DIR)

    return total_moved, total_skipped, total_failed, False, False


def _finish_bulk(job_id: int, label: str, moved: int, skipped: int, failed: int,
                 cancelled: bool, disk_aborted: bool) -> bool:
    """Set final status and log for a bulk download. Returns True on clean success."""
    if cancelled:
        db.update_job(job_id, status="cancelled")
        _log(job_id, f"[pipeline/{label}] job cancelled")
        return False
    if disk_aborted:
        return False  # status already set to error by _download_album_list

    stats = verify_structure(config.MUSIC_DIR)
    _log(
        job_id,
        f"[pipeline/{label}] music dir: {stats['flac_count']} FLAC file(s), "
        f"{len(stats['artists'])} artist(s)",
    )
    for issue in stats["issues"]:
        _log(job_id, f"[pipeline/{label}] warning: {issue}")

    if moved == 0:
        _log(job_id, f"[pipeline/{label}] error: no files moved to music dir")
        db.update_job(job_id, status="error")
        return False

    all_ok = failed == 0 and skipped == 0
    status = "done" if all_ok else "done_with_warnings"
    db.update_job(job_id, status=status)
    _log(
        job_id,
        f"[pipeline/{label}] complete (status={status}, moved={moved}, "
        f"skipped={skipped}, failed={failed})",
    )
    return failed == 0


# ── simple (one-shot) pipelines ───────────────────────────────────────────────

def _simple_download_pipeline(
    job_id: int,
    url: str,
    label: str,
    cancel_check: Callable[[], bool],
) -> bool:
    token = get_token()
    if not token:
        _log(job_id, f"[pipeline/{label}] error: no Qobuz token configured")
        db.update_job(job_id, status="error")
        return False

    if not _check_disk(job_id, label):
        db.update_job(job_id, status="error")
        return False

    _log(job_id, f"[pipeline/{label}] downloading: {url}")
    db.update_job(job_id, status="downloading")

    before = set(list_album_dirs(config.DOWNLOADS_DIR))

    dl_result = run_download(
        url,
        downloads_dir=config.DOWNLOADS_DIR,
        quality=get_quality(),
        log_callback=lambda l: db.append_job_log(job_id, l),
        job_id=job_id,
        cancel_check=cancel_check,
    )

    if dl_result.cancelled:
        _log(job_id, f"[pipeline/{label}] download cancelled")
        db.update_job(job_id, status="cancelled")
        return False

    if not dl_result.success:
        _log(job_id, f"[pipeline/{label}] download failed: {dl_result.error_message}")
        db.update_job(job_id, status="error")
        return False

    _log(job_id, f"[pipeline/{label}] download done — starting per-album tagging")

    new_dirs = sorted(set(list_album_dirs(config.DOWNLOADS_DIR)) - before)
    total_moved, total_skipped = _tag_and_move(job_id, new_dirs)

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


def run_playlist_pipeline(
    job_id: int,
    playlist_url: str,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> bool:
    """Download a Qobuz playlist then tag+move with Picard. Returns True on success.

    When the prefer-explicit setting is on, each clean track is replaced by its
    explicit twin (one qobuz-dl subprocess per track) before downloading.
    When off (default), a single efficient qobuz-dl call downloads the whole playlist.
    """
    if cancel_check is None:
        cancel_check = lambda: False

    if not get_prefer_explicit():
        return _simple_download_pipeline(job_id, playlist_url, "playlist", cancel_check)

    # Prefer-explicit path: resolve individual track URLs, download one at a time.
    _log(job_id, "[pipeline/playlist] prefer-explicit ON — resolving track URLs")
    token = get_token()
    if not token:
        _log(job_id, "[pipeline/playlist] error: no Qobuz token configured")
        db.update_job(job_id, status="error")
        return False

    client = make_client(token)
    try:
        track_urls = client.playlist_to_explicit_track_urls(playlist_url)
    except Exception as exc:
        _log(job_id, f"[pipeline/playlist] failed to resolve explicit track URLs: {exc}")
        db.update_job(job_id, status="error")
        return False

    _log(job_id, f"[pipeline/playlist] downloading {len(track_urls)} track(s) individually")

    quality = get_quality()
    total_moved = 0
    total_skipped = 0
    total_failed = 0

    for i, url in enumerate(track_urls, 1):
        if cancel_check():
            _log(job_id, "[pipeline/playlist] cancelled")
            db.update_job(job_id, status="cancelled")
            return False

        if not _check_disk(job_id, "playlist"):
            db.update_job(job_id, status="error")
            return False

        _log(job_id, f"[pipeline/playlist] ({i}/{len(track_urls)}) {url}")
        db.update_job(job_id, status="downloading")
        before = set(list_album_dirs(config.DOWNLOADS_DIR))

        dl_result = run_download(
            url,
            downloads_dir=config.DOWNLOADS_DIR,
            quality=quality,
            log_callback=lambda l: db.append_job_log(job_id, l),
            job_id=job_id,
            cancel_check=cancel_check,
        )

        if dl_result.cancelled:
            _log(job_id, "[pipeline/playlist] cancelled during download")
            db.update_job(job_id, status="cancelled")
            return False

        if not dl_result.success:
            _log(job_id, f"[pipeline/playlist] track download failed: {dl_result.error_message}")
            total_failed += 1
            continue

        new_dirs = sorted(set(list_album_dirs(config.DOWNLOADS_DIR)) - before)
        moved, skipped = _tag_and_move(job_id, new_dirs)
        total_moved += moved
        total_skipped += skipped
        clean_empty_dirs(config.DOWNLOADS_DIR)

    stats = verify_structure(config.MUSIC_DIR)
    _log(
        job_id,
        f"[pipeline/playlist] music dir: {stats['flac_count']} FLAC file(s), "
        f"{len(stats['artists'])} artist(s)",
    )
    for issue in stats["issues"]:
        _log(job_id, f"[pipeline/playlist] warning: {issue}")

    if total_moved == 0:
        _log(job_id, "[pipeline/playlist] error: no files were moved to music dir")
        db.update_job(job_id, status="error")
        return False

    all_ok = total_failed == 0 and total_skipped == 0
    status = "done" if all_ok else "done_with_warnings"
    db.update_job(job_id, status=status)
    _log(
        job_id,
        f"[pipeline/playlist] complete (status={status}, moved={total_moved}, "
        f"skipped={total_skipped}, failed={total_failed})",
    )
    return total_failed == 0


def run_track_pipeline(
    job_id: int,
    track_url: str,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> bool:
    if cancel_check is None:
        cancel_check = lambda: False
    return _simple_download_pipeline(job_id, track_url, "track", cancel_check)


def run_album_pipeline(
    job_id: int,
    album_url: str,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> bool:
    if cancel_check is None:
        cancel_check = lambda: False
    return _simple_download_pipeline(job_id, album_url, "album", cancel_check)


# ── bulk pipelines — resolve phase ────────────────────────────────────────────

def run_discography_resolve(job_id: int, artist_url: str) -> bool:
    """Resolve artist albums, build plan, set awaiting_confirm."""
    _log(job_id, f"[pipeline/discography] resolving albums for: {artist_url}")
    db.update_job(job_id, status="resolving")

    token = get_token()
    if not token:
        _log(job_id, "[pipeline/discography] error: no Qobuz token configured")
        db.update_job(job_id, status="error")
        return False

    client = make_client(token)
    try:
        albums = client.discography_to_album_plan(artist_url)
    except Exception as exc:
        _log(job_id, f"[pipeline/discography] failed to resolve albums: {exc}")
        db.update_job(job_id, status="error")
        return False

    _log(job_id, f"[pipeline/discography] found {len(albums)} album(s) on Qobuz")
    plan = _build_plan(albums, get_quality(), job_id)
    return _store_plan(job_id, plan, "discography")


def run_expand_albums_resolve(job_id: int, playlist_url: str) -> bool:
    """Resolve playlist → album list, build plan, set awaiting_confirm."""
    _log(job_id, f"[pipeline/expand] resolving albums from playlist: {playlist_url}")
    db.update_job(job_id, status="resolving")

    token = get_token()
    if not token:
        _log(job_id, "[pipeline/expand] error: no Qobuz token configured")
        db.update_job(job_id, status="error")
        return False

    client = make_client(token)
    try:
        albums = client.playlist_to_album_plan_from_tracks(playlist_url)
    except Exception as exc:
        _log(job_id, f"[pipeline/expand] failed to resolve albums: {exc}")
        db.update_job(job_id, status="error")
        return False

    _log(job_id, f"[pipeline/expand] found {len(albums)} unique album(s) in playlist")
    plan = _build_plan(albums, get_quality(), job_id)
    return _store_plan(job_id, plan, "expand")


def run_expand_discographies_resolve(job_id: int, playlist_url: str) -> bool:
    """Resolve playlist → per-artist catalogs → album list, build plan, set awaiting_confirm."""
    _log(job_id, f"[pipeline/expand-disco] resolving artist catalogs from playlist: {playlist_url}")
    db.update_job(job_id, status="resolving")

    token = get_token()
    if not token:
        _log(job_id, "[pipeline/expand-disco] error: no Qobuz token configured")
        db.update_job(job_id, status="error")
        return False

    client = make_client(token)
    try:
        albums = client.playlist_to_album_plan(playlist_url)
    except Exception as exc:
        _log(job_id, f"[pipeline/expand-disco] failed to resolve artists: {exc}")
        db.update_job(job_id, status="error")
        return False

    _log(job_id, f"[pipeline/expand-disco] found {len(albums)} unique album(s) across all artists")
    plan = _build_plan(albums, get_quality(), job_id)
    return _store_plan(job_id, plan, "expand-disco")


# ── bulk pipelines — download phase ──────────────────────────────────────────

def _run_bulk_download(
    job_id: int,
    label: str,
    cancel_check: Callable[[], bool],
    no_db: bool = False,
) -> bool:
    """Shared download phase: read plan from DB, run _download_album_list.

    no_db: when True, passes --no-db to qobuz-dl (explicit_upgrade only).
    """
    job = db.get_job(job_id)
    if not job:
        return False
    plan = json.loads(job.get("plan") or "{}")
    albums = plan.get("albums", [])
    quality = plan.get("quality") or get_quality()

    if not albums:
        _log(job_id, f"[pipeline/{label}] no albums in plan — nothing to download")
        db.update_job(job_id, status="done")
        return True

    _log(job_id, f"[pipeline/{label}] starting download of {len(albums)} album(s)")

    moved, skipped, failed, cancelled, disk_aborted = _download_album_list(
        job_id, albums, quality, label, cancel_check, no_db=no_db
    )
    return _finish_bulk(job_id, label, moved, skipped, failed, cancelled, disk_aborted)


def run_discography_download(job_id: int, cancel_check: Callable[[], bool]) -> bool:
    return _run_bulk_download(job_id, "discography", cancel_check)


def run_expand_albums_download(job_id: int, cancel_check: Callable[[], bool]) -> bool:
    return _run_bulk_download(job_id, "expand", cancel_check)


def run_expand_discographies_download(job_id: int, cancel_check: Callable[[], bool]) -> bool:
    return _run_bulk_download(job_id, "expand-disco", cancel_check)


# ── explicit-upgrade pipelines ────────────────────────────────────────────────

def run_explicit_upgrade_resolve(job_id: int, source: str) -> bool:
    """
    Resolve phase for explicit_upgrade jobs.

    source is either:
      - a Qobuz playlist URL  → scan that playlist for clean tracks
      - the sentinel "library" → scan the local /music directory for clean FLACs

    Builds a plan of explicit-album replacements and sets status awaiting_confirm.
    The plan log includes a report of no-match tracks and title-mismatch warnings.
    """
    label = "explicit"
    _log(job_id, f"[pipeline/{label}] resolving — source: {source!r}")
    db.update_job(job_id, status="resolving")

    token = get_token()
    if not token:
        _log(job_id, f"[pipeline/{label}] error: no Qobuz token configured")
        db.update_job(job_id, status="error")
        return False

    client = make_client(token)

    try:
        if source == "library":
            albums, report = client.library_to_explicit_album_plan(config.MUSIC_DIR)
        else:
            albums, report = client.playlist_to_explicit_album_plan(source)
    except Exception as exc:
        _log(job_id, f"[pipeline/{label}] failed to resolve explicit albums: {exc}")
        db.update_job(job_id, status="error")
        return False

    _log(job_id, f"[pipeline/{label}] found {len(albums)} explicit album(s) to download")

    if report:
        _log(job_id, f"[pipeline/{label}] --- report ({len(report)} item(s)) ---")
        for line in report:
            _log(job_id, f"[pipeline/{label}]   {line}")
        _log(job_id, f"[pipeline/{label}] --- end report ---")

    # skip_present_check=True: we want to download even if a clean copy already exists.
    plan = _build_plan(albums, get_quality(), job_id, skip_present_check=True)
    return _store_plan(job_id, plan, label)


def run_explicit_upgrade_download(job_id: int, cancel_check: Callable[[], bool]) -> bool:
    """Download phase for explicit_upgrade jobs (delegates to shared bulk downloader).

    Always passes no_db=True so qobuz-dl ignores its local download database and
    re-fetches albums even if they were previously downloaded (e.g. as a clean copy).
    """
    return _run_bulk_download(job_id, "explicit", cancel_check, no_db=True)


# ── retag-library pipelines ───────────────────────────────────────────────────

def run_retag_library_resolve(job_id: int, source: str = "library") -> bool:
    """
    Resolve phase for retag_library jobs.

    Scans MUSIC_DIR for FLACs that are untagged or were never matched by Picard
    (see app/library.py), builds a plan of the album directories that need
    tagging, and sets status awaiting_confirm. No Qobuz token is required —
    this job never downloads anything.

    Returns True if any album dir needs tagging.
    """
    label = "retag"
    _log(job_id, f"[pipeline/{label}] scanning music library: {config.MUSIC_DIR}")
    db.update_job(job_id, status="resolving")

    try:
        scan = scan_untagged_albums(config.MUSIC_DIR)
    except Exception as exc:
        _log(job_id, f"[pipeline/{label}] library scan failed: {exc}")
        db.update_job(job_id, status="error")
        return False

    plan = {
        "dirs": scan["dirs"],
        "scanned_files": scan["scanned_files"],
        "untagged_files": scan["untagged_files"],
        "album_count": scan["album_count"],
    }
    db.set_job_plan(job_id, json.dumps(plan))
    db.update_job(job_id, status="awaiting_confirm")
    _log(
        job_id,
        f"[pipeline/{label}] plan ready: {scan['album_count']} album dir(s) need tagging "
        f"({scan['untagged_files']} of {scan['scanned_files']} file(s) untagged or "
        f"not matched by Picard)",
    )
    if scan["album_count"] == 0:
        _log(job_id, f"[pipeline/{label}] nothing to do — library already fully tagged")
    return scan["album_count"] > 0


def run_retag_library_execute(job_id: int, cancel_check: Callable[[], bool]) -> bool:
    """
    Execute phase for retag_library jobs.

    Runs Picard (with MusicBrainz lookup forced on) once per flagged album dir,
    tagging files in place. The files are already in MUSIC_DIR in the
    Artist/Album/Title layout, so they are NOT moved — Picard only enriches the
    embedded tags. Returns True when every album tagged cleanly.
    """
    label = "retag"
    job = db.get_job(job_id)
    if not job:
        return False
    plan = json.loads(job.get("plan") or "{}")
    dirs = [Path(p) for p in plan.get("dirs", [])]

    if not dirs:
        _log(job_id, f"[pipeline/{label}] no album dirs in plan — nothing to tag")
        db.update_job(job_id, status="done")
        return True

    _log(job_id, f"[pipeline/{label}] tagging {len(dirs)} album dir(s) with Picard")

    tagged = 0
    failed = 0
    for i, album_dir in enumerate(dirs, 1):
        if cancel_check():
            _log(job_id, f"[pipeline/{label}] cancelled between albums")
            db.update_job(job_id, status="cancelled")
            return False
        if not album_dir.exists():
            _log(job_id, f"[pipeline/{label}] ({i}/{len(dirs)}) skip — dir gone: {album_dir}")
            continue

        _log(job_id, f"[pipeline/{label}] ({i}/{len(dirs)}) tagging: {album_dir.name}")
        db.update_job(job_id, status="tagging")
        result = run_picard(
            source_dir=album_dir,
            log_callback=lambda l: db.append_job_log(job_id, l),
            lookup=True,
        )
        if result.success:
            tagged += 1
        else:
            failed += 1
            _log(
                job_id,
                f"[pipeline/{label}] Picard failed on {album_dir.name}: "
                f"{result.error_message}",
            )

    db.update_job(job_id, status="verifying")
    stats = verify_structure(config.MUSIC_DIR)
    _log(
        job_id,
        f"[pipeline/{label}] music dir: {stats['flac_count']} FLAC file(s), "
        f"{len(stats['artists'])} artist(s)",
    )

    status = "done" if failed == 0 else "done_with_warnings"
    db.update_job(job_id, status=status)
    _log(
        job_id,
        f"[pipeline/{label}] complete (status={status}, tagged={tagged}, failed={failed})",
    )
    return failed == 0


# ── fetch-lyrics pipelines ────────────────────────────────────────────────────

def run_fetch_lyrics_resolve(job_id: int, source: str = "library") -> bool:
    """
    Resolve phase for fetch_lyrics jobs.

    Scans MUSIC_DIR for FLACs that have no .lrc sidecar, builds a plan of
    files that need lyrics, and sets status awaiting_confirm.  No Qobuz
    token is required — this job never downloads audio.

    Returns True if any files are missing lyrics.
    """
    label = "fetch_lyrics"
    _log(job_id, f"[pipeline/{label}] scanning music library: {config.MUSIC_DIR}")
    db.update_job(job_id, status="resolving")

    try:
        scan = scan_missing_lyrics(config.MUSIC_DIR)
    except Exception as exc:
        _log(job_id, f"[pipeline/{label}] library scan failed: {exc}")
        db.update_job(job_id, status="error")
        return False

    plan = {
        "files": scan["files"],
        "dirs": scan["dirs"],
        "scanned_files": scan["scanned_files"],
        "missing_files": scan["missing_files"],
        "album_count": scan["album_count"],
    }
    db.set_job_plan(job_id, json.dumps(plan))
    db.update_job(job_id, status="awaiting_confirm")
    _log(
        job_id,
        f"[pipeline/{label}] plan ready: {scan['missing_files']} of {scan['scanned_files']} "
        f"file(s) missing lyrics across {scan['album_count']} album dir(s)",
    )
    if scan["missing_files"] == 0:
        _log(job_id, f"[pipeline/{label}] nothing to do — all tracks already have lyrics")
    return scan["missing_files"] > 0


def run_fetch_lyrics_execute(job_id: int, cancel_check: Callable[[], bool]) -> bool:
    """
    Execute phase for fetch_lyrics jobs.

    For each FLAC in the plan, re-checks that the .lrc is still missing
    (idempotent), reads the track's tags, queries LRCLIB, and writes the
    sidecar in place.  Files are never moved.

    Returns True when every file either received lyrics or was skipped as
    already-present; returns True even when some tracks couldn't be found on
    LRCLIB (those are counted as warnings → done_with_warnings).
    """
    label = "fetch_lyrics"
    job = db.get_job(job_id)
    if not job:
        return False
    plan = json.loads(job.get("plan") or "{}")
    files = [Path(p) for p in plan.get("files", [])]

    if not files:
        _log(job_id, f"[pipeline/{label}] no files in plan — nothing to fetch")
        db.update_job(job_id, status="done")
        return True

    _log(job_id, f"[pipeline/{label}] fetching lyrics for {len(files)} file(s)")

    fetched = 0
    not_found = 0
    skipped = 0
    for i, flac_path in enumerate(files, 1):
        if cancel_check():
            _log(job_id, f"[pipeline/{label}] cancelled between files")
            db.update_job(job_id, status="cancelled")
            return False

        if not flac_path.exists():
            _log(job_id, f"[pipeline/{label}] ({i}/{len(files)}) skip — file gone: {flac_path.name}")
            continue

        # Idempotency: another run may have already written this sidecar.
        if not file_needs_lyrics(flac_path):
            skipped += 1
            continue

        meta = _read_track_meta(flac_path)
        if meta is None:
            _log(
                job_id,
                f"[pipeline/{label}] ({i}/{len(files)}) skip — could not read tags: {flac_path.name}",
            )
            continue

        db.update_job(job_id, status="downloading")
        lrc_text = fetch_lrc(meta)
        if lrc_text:
            write_lrc(flac_path, lrc_text)
            fetched += 1
            _log(
                job_id,
                f"[pipeline/{label}] ({i}/{len(files)}) fetched: {flac_path.name}",
            )
        else:
            not_found += 1
            _log(
                job_id,
                f"[pipeline/{label}] ({i}/{len(files)}) not found on LRCLIB: "
                f"{meta['artist']} — {meta['title']}",
            )

    status = "done" if not_found == 0 else "done_with_warnings"
    db.update_job(job_id, status=status)
    _log(
        job_id,
        f"[pipeline/{label}] complete (status={status}, fetched={fetched}, "
        f"not_found={not_found}, skipped_present={skipped})",
    )
    return True


# ── legacy aliases (kept so existing tests that import these names still work) ─

def run_discography_pipeline(job_id: int, artist_url: str) -> bool:
    """Deprecated: use run_discography_resolve / run_discography_download."""
    run_discography_resolve(job_id, artist_url)
    return False  # caller must confirm via API


def run_expand_albums_pipeline(job_id: int, playlist_url: str) -> bool:
    """Deprecated: use run_expand_albums_resolve / run_expand_albums_download."""
    run_expand_albums_resolve(job_id, playlist_url)
    return False


def run_expand_discographies_pipeline(job_id: int, playlist_url: str) -> bool:
    """Deprecated: use run_expand_discographies_resolve / run_expand_discographies_download."""
    run_expand_discographies_resolve(job_id, playlist_url)
    return False
