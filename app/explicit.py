"""
Helpers for finding explicit versions of clean tracks/albums on Qobuz.

Public surface:
  normalize(s)               — strip qualifiers, lowercase, collapse whitespace
  find_explicit_album(...)   — search for an explicit album to replace a clean track
  find_explicit_track(...)   — search for an explicit track (for prefer-explicit toggle)
"""
import re
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.qobuz_client import QobuzClient

logger = logging.getLogger(__name__)

# Parenthetical qualifiers to strip before comparing titles/artists.
_STRIP_RE = re.compile(
    r"\s*\("
    r"(?:clean|explicit|edited|radio\s+edit|single\s+version|album\s+version"
    r"|feat\.?[^)]*|ft\.?[^)]*|with\s+[^)]*)"
    r"[^)]*\)",
    re.IGNORECASE,
)
# Anything that's not a letter, digit, or whitespace.
_NON_ALPHANUM_RE = re.compile(r"[^\w\s]", re.UNICODE)
_MULTI_SPACE_RE = re.compile(r"\s+")


def normalize(s: str) -> str:
    """
    Normalise a title/artist for fuzzy matching:
      - strip parenthetical qualifiers like (Clean), (Explicit), (feat. …)
      - lowercase
      - remove punctuation
      - collapse whitespace
    """
    s = _STRIP_RE.sub("", s)
    s = s.lower()
    s = _NON_ALPHANUM_RE.sub(" ", s)
    s = _MULTI_SPACE_RE.sub(" ", s).strip()
    return s


def _artist_name(track: dict) -> str:
    """Best artist name from a search-result track dict."""
    album = track.get("album") or {}
    artist = album.get("artist") or track.get("performer") or {}
    return artist.get("name", "")


def _album_artist(track: dict) -> str:
    album = track.get("album") or {}
    artist = album.get("artist") or {}
    return artist.get("name", "")


def find_explicit_album(
    client: "QobuzClient",
    artist: str,
    title: str,
    album_title: str = "",
    duration: Optional[float] = None,
    duration_tol: int = 4,
    search_limit: int = 20,
) -> Optional[dict]:
    """
    Search Qobuz for an explicit version of the given clean track and return its
    album dict (same shape as _album_dict in qobuz_client.py), or None.

    Matching rules (all must pass):
      1. track has parental_warning truthy
      2. normalized track title == normalize(title)
      3. normalized album-artist == normalize(artist)
      4. if duration given: abs(track.duration - duration) <= duration_tol seconds

    Among passing candidates, prefer one whose normalized album title == normalize(album_title).
    If no same-album match, fall back to the first matching candidate (may be a compilation).
    """
    norm_title = normalize(title)
    norm_artist = normalize(artist)
    norm_album = normalize(album_title) if album_title else ""

    try:
        resp = client.search_tracks(f"{artist} {title}", limit=search_limit)
    except Exception as exc:
        logger.warning("search_tracks error for '%s – %s': %s", artist, title, exc)
        return None

    items = (resp or {}).get("tracks", {}).get("items") or []

    same_album_match: Optional[dict] = None
    any_match: Optional[dict] = None

    for t in items:
        if not t.get("parental_warning"):
            continue

        if normalize(t.get("title", "")) != norm_title:
            continue

        if normalize(_album_artist(t)) != norm_artist:
            continue

        if duration is not None:
            t_dur = t.get("duration") or 0
            if abs(t_dur - duration) > duration_tol:
                continue

        # Candidate passes all filters.
        if any_match is None:
            any_match = t

        album = t.get("album") or {}
        if norm_album and normalize(album.get("title", "")) == norm_album:
            same_album_match = t
            break  # ideal match — stop searching

    best = same_album_match or any_match
    if best is None:
        return None

    # Build album dict via the shared helper in qobuz_client.
    from app.qobuz_client import _album_dict
    return _album_dict(best.get("album") or {})


def find_explicit_track(
    client: "QobuzClient",
    artist: str,
    title: str,
    duration: Optional[float] = None,
    duration_tol: int = 4,
    search_limit: int = 20,
) -> Optional[dict]:
    """
    Like find_explicit_album but returns the explicit track dict itself
    (for prefer-explicit track-by-track replacement).
    Returns None if no explicit twin found.
    """
    norm_title = normalize(title)
    norm_artist = normalize(artist)

    try:
        resp = client.search_tracks(f"{artist} {title}", limit=search_limit)
    except Exception as exc:
        logger.warning("search_tracks error for '%s – %s': %s", artist, title, exc)
        return None

    items = (resp or {}).get("tracks", {}).get("items") or []

    for t in items:
        if not t.get("parental_warning"):
            continue
        if normalize(t.get("title", "")) != norm_title:
            continue
        if normalize(_album_artist(t)) != norm_artist:
            continue
        if duration is not None:
            t_dur = t.get("duration") or 0
            if abs(t_dur - duration) > duration_tol:
                continue
        return t

    return None
