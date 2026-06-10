"""
Fast os.scandir-based library scanner that returns album-level stats without
opening any audio files (no mutagen).  Artist and album names come from the
directory structure (mover guarantees Artist/Album/Title.FLAC layout).

Results are cached in-process for CACHE_TTL_SECONDS to keep repeated tab
switches cheap.  Pass refresh=True (or hit ?refresh=1) to force a rescan.
"""
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.art_library import _ART_NAMES

CACHE_TTL_SECONDS = 300

_cache_lock = threading.Lock()
_cache: dict = {"data": None, "ts": 0.0}

_ART_NAMES_LOWER = {n.lower() for n in _ART_NAMES}


def _walk_album_dir(directory: Path, counts: list, flac_stems: set, lrc_stems: set, depth: int = 0):
    """Recursively accumulate [track_count, size_bytes, has_cover] into counts."""
    if depth > 2:
        return
    try:
        for entry in os.scandir(directory):
            if entry.is_dir(follow_symlinks=False) and not entry.name.startswith("."):
                _walk_album_dir(Path(entry.path), counts, flac_stems, lrc_stems, depth + 1)
            elif entry.is_file(follow_symlinks=False):
                name_lower = entry.name.lower()
                if name_lower.endswith(".flac"):
                    counts[0] += 1
                    try:
                        counts[1] += entry.stat().st_size
                    except OSError:
                        pass
                    flac_stems.add(entry.name.rsplit(".", 1)[0])
                elif name_lower.endswith(".lrc"):
                    lrc_stems.add(entry.name.rsplit(".", 1)[0])
                elif name_lower in _ART_NAMES_LOWER:
                    counts[2] = True
    except (PermissionError, FileNotFoundError):
        pass


def _scan_album_dir(album_dir: Path, artist_name: str, album_name: str) -> dict:
    counts = [0, 0, False]  # [track_count, size_bytes, has_cover]
    flac_stems: set[str] = set()
    lrc_stems: set[str] = set()
    _walk_album_dir(album_dir, counts, flac_stems, lrc_stems)
    return {
        "id": f"{artist_name}/{album_name}",
        "artist": artist_name,
        "album": album_name,
        "track_count": counts[0],
        "size_bytes": counts[1],
        "has_cover": counts[2],
        "missing_lyrics": len(flac_stems - lrc_stems),
    }


def scan_library(music_dir: Path) -> dict:
    """Pure os.scandir walk of music_dir — no mutagen, no file opens."""
    artists = 0
    albums_total = 0
    tracks_total = 0
    total_size = 0
    missing_art = 0
    missing_lyrics = 0
    album_list: list[dict] = []

    try:
        artist_entries = [e for e in os.scandir(music_dir) if e.is_dir() and not e.name.startswith(".")]
    except (PermissionError, FileNotFoundError):
        artist_entries = []

    for artist_entry in sorted(artist_entries, key=lambda e: e.name.lower()):
        artists += 1
        try:
            album_entries = [e for e in os.scandir(artist_entry.path) if e.is_dir() and not e.name.startswith(".")]
        except (PermissionError, FileNotFoundError):
            continue

        for album_entry in sorted(album_entries, key=lambda e: e.name.lower()):
            info = _scan_album_dir(Path(album_entry.path), artist_entry.name, album_entry.name)
            if info["track_count"] == 0:
                continue
            albums_total += 1
            tracks_total += info["track_count"]
            total_size += info["size_bytes"]
            if not info["has_cover"]:
                missing_art += 1
            missing_lyrics += info["missing_lyrics"]
            album_list.append(info)

    return {
        "stats": {
            "artists": artists,
            "albums": albums_total,
            "tracks": tracks_total,
            "total_size_bytes": total_size,
            "missing_art_count": missing_art,
            "missing_lyrics_count": missing_lyrics,
        },
        "albums": album_list,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


def get_library(refresh: bool = False) -> dict:
    """Return cached library data, optionally forcing a rescan."""
    now = time.monotonic()
    with _cache_lock:
        if not refresh and _cache["data"] is not None and (now - _cache["ts"]) < CACHE_TTL_SECONDS:
            result = dict(_cache["data"])
            result["cached"] = True
            return result
    fresh = scan_library(config.MUSIC_DIR)
    with _cache_lock:
        _cache["data"] = fresh
        _cache["ts"] = now
    result = dict(fresh)
    result["cached"] = False
    return result
