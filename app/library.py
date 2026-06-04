"""
Scan the existing music library for files that are untagged or were never
enriched by MusicBrainz Picard, so they can be (re-)tagged in place.

A FLAC "needs tagging" when either:
  * it is missing one of the core tags (title / album / artist|albumartist), or
  * it has no MusicBrainz recording id (``musicbrainz_trackid`` /
    ``musicbrainz_recordingid``) — the marker Picard writes when it matches a
    file against the MusicBrainz database.

Files that already carry full core tags *and* an MBID are considered already
tagged by Picard and are skipped, so re-running the scan is cheap and
idempotent.

Only FLAC files are considered — the rest of Ripuz is FLAC-only.
"""
import logging
from pathlib import Path
from typing import Optional

from app.structure import find_flac_files, list_album_dirs

logger = logging.getLogger(__name__)

# Vorbis-comment keys (lower-cased, as mutagen exposes them) that mark a Picard
# MusicBrainz match. Either one present means Picard has tagged the file.
_MBID_KEYS = ("musicbrainz_trackid", "musicbrainz_recordingid")

# Core tags every properly-tagged file must have. Each tuple is an OR-group:
# any one key in the group satisfies it (e.g. artist OR albumartist).
_CORE_KEYS = (("title",), ("album",), ("artist", "albumartist"))


def _read_tags(path: Path) -> dict:
    """Return a FLAC's Vorbis-comment tags as a plain dict, or {} if unreadable.

    Isolated in its own function so tests can monkeypatch tag reading without
    needing real FLAC audio fixtures.
    """
    try:
        from mutagen.flac import FLAC

        return dict(FLAC(path))
    except Exception as exc:  # corrupt / unreadable / not actually FLAC
        logger.debug("could not read tags from %s: %s", path, exc)
        return {}


def _has(tags: dict, *keys: str) -> bool:
    """True if any of the given keys holds a non-empty value."""
    for k in keys:
        vals = tags.get(k)
        if vals and any(str(v).strip() for v in vals):
            return True
    return False


def file_needs_tagging(path: Path, tags: Optional[dict] = None) -> bool:
    """Return True if the FLAC lacks core tags or a MusicBrainz id.

    Pass ``tags`` to check an already-read tag dict (used by tests); otherwise
    the tags are read from disk.
    """
    if tags is None:
        tags = _read_tags(path)
    if not tags:
        return True  # unreadable or no tags at all
    for group in _CORE_KEYS:
        if not _has(tags, *group):
            return True
    if not _has(tags, *_MBID_KEYS):
        return True
    return False


def scan_untagged_albums(music_dir: Path) -> dict:
    """Walk music_dir and group FLACs needing tagging by their album directory.

    Returns:
        {
            "dirs": [str, ...],     # album dirs with >=1 file needing tagging
            "scanned_files": int,   # total FLACs scanned
            "untagged_files": int,  # FLACs flagged as needing tagging
            "album_count": int,     # == len(dirs)
        }
    """
    dirs: list[str] = []
    scanned = 0
    untagged = 0
    for album_dir in list_album_dirs(music_dir):
        dir_needs = False
        for f in find_flac_files(album_dir):
            scanned += 1
            if file_needs_tagging(f):
                untagged += 1
                dir_needs = True
        if dir_needs:
            dirs.append(str(album_dir))
    return {
        "dirs": dirs,
        "scanned_files": scanned,
        "untagged_files": untagged,
        "album_count": len(dirs),
    }
