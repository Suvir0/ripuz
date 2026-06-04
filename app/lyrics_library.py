"""
Scan the existing music library for FLAC files that have no .lrc lyrics sidecar,
then fetch lyrics from LRCLIB and write them alongside the audio file.

A FLAC "needs lyrics" when there is no ``<stem>.lrc`` file next to it.
Re-running the scan is cheap and idempotent: tracks that already received a
sidecar are skipped automatically.

Only FLAC files are considered — the rest of Ripuz is FLAC-only.
Lyrics are fetched from https://lrclib.net (public, no auth required).

Preference order (user-confirmed):
  1. Time-synced lyrics  (``syncedLyrics`` field from LRCLIB)
  2. Plain / unsyced lyrics  (``plainLyrics`` field from LRCLIB) as a fallback

If neither is available the track is skipped (counted as "not found").
"""
import logging
from pathlib import Path
from typing import Optional

import httpx

from app.structure import find_flac_files, list_album_dirs

logger = logging.getLogger(__name__)

_LRCLIB_BASE = "https://lrclib.net"
_USER_AGENT = "ripuz/1.0 (https://github.com/Suvir0/ripuz)"
# Duration tolerance when matching search results (seconds)
_DURATION_TOLERANCE = 2


# ── skip-check ────────────────────────────────────────────────────────────────

def file_needs_lyrics(flac_path: Path) -> bool:
    """Return True when no sibling .lrc sidecar exists for *flac_path*."""
    return not flac_path.with_suffix(".lrc").exists()


# ── library scan ─────────────────────────────────────────────────────────────

def scan_missing_lyrics(music_dir: Path) -> dict:
    """Walk *music_dir* and collect FLACs that have no .lrc sidecar.

    Returns::

        {
            "files":         [str, ...],   # absolute paths of FLACs needing lyrics
            "dirs":          [str, ...],   # unique album dirs that have >=1 such file
            "scanned_files": int,          # total FLACs found
            "missing_files": int,          # == len(files)
            "album_count":   int,          # == len(dirs)
        }
    """
    files: list[str] = []
    dirs_seen: list[str] = []
    scanned = 0
    for album_dir in list_album_dirs(music_dir):
        dir_added = False
        for f in find_flac_files(album_dir):
            scanned += 1
            if file_needs_lyrics(f):
                files.append(str(f))
                if not dir_added:
                    dirs_seen.append(str(album_dir))
                    dir_added = True
    return {
        "files": files,
        "dirs": dirs_seen,
        "scanned_files": scanned,
        "missing_files": len(files),
        "album_count": len(dirs_seen),
    }


# ── tag reading ───────────────────────────────────────────────────────────────

def _read_track_meta(path: Path) -> Optional[dict]:
    """Read artist/title/album/duration from a FLAC.

    Isolated so tests can monkeypatch without real audio fixtures.
    Returns a dict with keys ``artist``, ``title``, ``album``, ``duration``
    (int seconds, 0 if unknown), or ``None`` if the file is unreadable or
    lacks the required artist or title tag.
    """
    try:
        from mutagen.flac import FLAC
        audio = FLAC(path)
    except Exception as exc:
        logger.debug("could not open %s: %s", path, exc)
        return None

    def _first(key: str) -> str:
        vals = audio.get(key)
        return str(vals[0]).strip() if vals else ""

    artist = _first("artist") or _first("albumartist")
    title = _first("title")
    if not artist or not title:
        return None

    try:
        duration = round(audio.info.length)
    except Exception:
        duration = 0

    return {
        "artist": artist,
        "title": title,
        "album": _first("album"),
        "duration": duration,
    }


# ── LRCLIB fetch ──────────────────────────────────────────────────────────────

def _pick_lyrics(data: dict) -> Optional[str]:
    """Prefer syncedLyrics; fall back to plainLyrics."""
    synced = (data.get("syncedLyrics") or "").strip()
    if synced:
        return synced
    plain = (data.get("plainLyrics") or "").strip()
    return plain or None


def fetch_lrc(meta: dict, *, client: Optional[httpx.Client] = None) -> Optional[str]:
    """Query LRCLIB for lyrics and return the .lrc text, or None if not found.

    Strategy:
    1. ``GET /api/get`` with exact artist/title/album/duration.
       Returns synced if available, else plain.
    2. On 404 (or no usable result): ``GET /api/search`` by artist+title,
       pick the first hit whose duration is within ±2 s.

    Accepts an injected *client* so tests can mock via respx.
    """
    own_client = client is None
    if own_client:
        client = httpx.Client(timeout=10)

    try:
        # ── exact lookup ─────────────────────────────────────────────────────
        params: dict = {
            "artist_name": meta["artist"],
            "track_name": meta["title"],
        }
        if meta.get("album"):
            params["album_name"] = meta["album"]
        if meta.get("duration"):
            params["duration"] = meta["duration"]

        resp = client.get(
            f"{_LRCLIB_BASE}/api/get",
            params=params,
            headers={"User-Agent": _USER_AGENT},
        )
        if resp.status_code == 200:
            lrc = _pick_lyrics(resp.json())
            if lrc:
                return lrc

        # ── search fallback ───────────────────────────────────────────────────
        search_params = {
            "artist_name": meta["artist"],
            "track_name": meta["title"],
        }
        resp2 = client.get(
            f"{_LRCLIB_BASE}/api/search",
            params=search_params,
            headers={"User-Agent": _USER_AGENT},
        )
        if resp2.status_code == 200:
            target_dur = meta.get("duration") or 0
            for item in resp2.json():
                if target_dur:
                    item_dur = item.get("duration") or 0
                    if abs(item_dur - target_dur) > _DURATION_TOLERANCE:
                        continue
                lrc = _pick_lyrics(item)
                if lrc:
                    return lrc

    except Exception as exc:
        logger.debug("LRCLIB fetch error for %s - %s: %s", meta.get("artist"), meta.get("title"), exc)
    finally:
        if own_client:
            client.close()

    return None


# ── write sidecar ─────────────────────────────────────────────────────────────

def write_lrc(flac_path: Path, lrc_text: str) -> Path:
    """Write *lrc_text* to ``<flac_path stem>.lrc`` next to the audio file."""
    dest = flac_path.with_suffix(".lrc")
    dest.write_text(lrc_text, encoding="utf-8")
    return dest
