"""
Scan the existing music library for album directories that have no cover art
sidecar, then fetch art from embedded FLAC pictures or the Cover Art Archive.

Priority:
  1. Embedded picture in a FLAC (mutagen FLAC.pictures, prefer type 3 front cover).
     Offline — guaranteed-correct art from the original download.
  2. Cover Art Archive (coverartarchive.org) via the album's musicbrainz_albumid tag.
     Picard writes this tag after a successful MusicBrainz lookup.
  3. Qobuz API — TODO: no reliable per-file Qobuz album-id tag, left for future work.

Art is written as cover.jpg (or cover.png for PNG-mime sources) into the album dir.
cover.jpg matches the filename qobuz-dl already uses, keeping one convention library-wide.
Plex Local Media Assets reads both cover.jpg and folder.jpg; cover.jpg is preferred.
"""
import logging
from pathlib import Path
from typing import Optional

import httpx

from app.structure import find_flac_files, list_album_dirs

logger = logging.getLogger(__name__)

_ART_NAMES = ("cover.jpg", "folder.jpg", "cover.png", "folder.png")
_CAA_BASE = "https://coverartarchive.org"
_USER_AGENT = "ripuz/1.0 (https://github.com/Suvir0/ripuz)"


# ── skip-check ────────────────────────────────────────────────────────────────

def find_cover(album_dir: Path) -> Optional[Path]:
    """Return the first existing cover-art file in album_dir, or None."""
    for name in _ART_NAMES:
        p = album_dir / name
        if p.exists():
            return p
    return None


def album_needs_art(album_dir: Path) -> bool:
    """Return True when no cover art sidecar file exists in album_dir."""
    return find_cover(album_dir) is None


# ── library scan ─────────────────────────────────────────────────────────────

def scan_missing_art(music_dir: Path) -> dict:
    """Walk music_dir and collect album dirs that have no cover art.

    Returns::

        {
            "dirs":            [str, ...],  # absolute paths of album dirs needing art
            "scanned_albums":  int,         # total album dirs found
            "missing_albums":  int,         # == len(dirs)
        }
    """
    dirs: list[str] = []
    scanned = 0
    for album_dir in list_album_dirs(music_dir):
        scanned += 1
        if album_needs_art(album_dir):
            dirs.append(str(album_dir))
    return {
        "dirs": dirs,
        "scanned_albums": scanned,
        "missing_albums": len(dirs),
    }


# ── tag reading ───────────────────────────────────────────────────────────────

def _read_album_mbid(album_dir: Path) -> Optional[str]:
    """Read musicbrainz_albumid from the first readable FLAC in album_dir.

    Isolated so tests can monkeypatch without real audio fixtures.
    """
    try:
        from mutagen.flac import FLAC
        for flac_path in find_flac_files(album_dir):
            try:
                audio = FLAC(flac_path)
                vals = audio.get("musicbrainz_albumid")
                if vals:
                    return str(vals[0]).strip() or None
            except Exception:
                continue
    except Exception as exc:
        logger.debug("could not read MBID from %s: %s", album_dir, exc)
    return None


# ── embedded art extraction ───────────────────────────────────────────────────

def extract_embedded_art(album_dir: Path) -> Optional[tuple[bytes, str]]:
    """Extract the front-cover picture from the first FLAC in album_dir.

    Returns (data_bytes, mime_type) or None if no picture is found.
    Prefers picture type 3 (front cover); falls back to the first picture.
    Isolated for monkeypatching in tests.
    """
    try:
        from mutagen.flac import FLAC
        for flac_path in find_flac_files(album_dir):
            try:
                audio = FLAC(flac_path)
                if not audio.pictures:
                    continue
                # Prefer front cover (type 3), fall back to first picture
                pic = next((p for p in audio.pictures if p.type == 3), audio.pictures[0])
                if pic.data:
                    return (pic.data, pic.mime or "image/jpeg")
            except Exception:
                continue
    except Exception as exc:
        logger.debug("could not extract embedded art from %s: %s", album_dir, exc)
    return None


# ── Cover Art Archive fetch ───────────────────────────────────────────────────

def fetch_caa_art(mbid: str, *, client: Optional[httpx.Client] = None) -> Optional[tuple[bytes, str]]:
    """Fetch front cover from the Cover Art Archive for the given release MBID.

    Tries /release/{mbid}/front-1200 first; falls back to /front.
    Returns (data_bytes, mime_type) or None on any failure.
    Accepts an injected client so tests can mock via respx.
    """
    own_client = client is None
    if own_client:
        client = httpx.Client(timeout=15, follow_redirects=True)

    try:
        for path in (f"/release/{mbid}/front-1200", f"/release/{mbid}/front"):
            try:
                resp = client.get(
                    f"{_CAA_BASE}{path}",
                    headers={"User-Agent": _USER_AGENT},
                )
                if resp.status_code == 200 and resp.content:
                    mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
                    return (resp.content, mime)
            except httpx.HTTPError:
                continue
    except Exception as exc:
        logger.debug("CAA fetch error for MBID %s: %s", mbid, exc)
    finally:
        if own_client:
            client.close()

    return None


# ── write cover ───────────────────────────────────────────────────────────────

def write_cover(album_dir: Path, data: bytes, mime: str) -> Path:
    """Write art data to cover.jpg (or cover.png if mime is image/png) in album_dir."""
    filename = "cover.png" if mime == "image/png" else "cover.jpg"
    dest = album_dir / filename
    dest.write_bytes(data)
    return dest
