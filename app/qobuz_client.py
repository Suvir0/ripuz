"""
Thin wrapper around qobuz_dl.qopy.Client for playlist/track/album lookup.
Only used by the expand-albums pipeline path; actual downloading is done by
qobuz-dl CLI subprocess in qobuz_cli.py.
"""
import logging
import re
from typing import Optional

from app import db

logger = logging.getLogger(__name__)

_QOBUZ_URL_RE = re.compile(r"^https?://(?:[\w-]+\.)*qobuz\.com/", re.IGNORECASE)
_QOBUZ_PATH_RE = re.compile(r"(?:playlist|album|track|artist)/([A-Za-z0-9]+)")
_QOBUZ_RAW_ID_RE = re.compile(r"^[A-Za-z0-9]{6,20}$")

# Fallback app_id used if Bundle scraping fails (well-known public value)
_FALLBACK_APP_ID = "950096963"


def is_valid_qobuz_input(value: str) -> bool:
    """Return True if value is a Qobuz URL or a raw Qobuz id."""
    value = value.strip()
    if not value:
        return False
    if _QOBUZ_URL_RE.match(value):
        return bool(_QOBUZ_PATH_RE.search(value))
    return bool(_QOBUZ_RAW_ID_RE.match(value))


def _extract_id(url_or_id: str) -> str:
    """Pull the numeric/alphanumeric ID out of a Qobuz URL or raw ID."""
    value = url_or_id.strip()
    if not value:
        raise ValueError("empty qobuz input")
    if _QOBUZ_URL_RE.match(value):
        m = _QOBUZ_PATH_RE.search(value)
        if not m:
            raise ValueError("invalid qobuz url")
        return m.group(1)
    if _QOBUZ_RAW_ID_RE.match(value):
        return value
    raise ValueError("invalid qobuz id")


class QobuzClient:
    def __init__(self, token: str):
        self._token = token
        self._client = None  # lazy-initialised

    # ── internal ──────────────────────────────────────────────────────────────

    def _ensure_client(self):
        if self._client is not None:
            return
        from qobuz_dl.qopy import Client
        app_id = _FALLBACK_APP_ID
        secrets = []
        try:
            from qobuz_dl.bundle import Bundle
            b = Bundle()
            app_id = str(b.get_app_id())
            secrets = list(b.get_secrets().values())
            logger.debug("Bundle resolved: app_id set, %d secrets", len(secrets))
        except Exception as exc:
            logger.warning("Bundle init failed (%s); using fallback app_id", exc)
        self._client = Client(
            "", "", app_id, secrets, user_auth_token=self._token
        )

    # ── public API ────────────────────────────────────────────────────────────

    def get_playlist_tracks(self, playlist_url: str) -> list[dict]:
        """Return all track objects in a Qobuz playlist."""
        self._ensure_client()
        playlist_id = _extract_id(playlist_url)
        tracks: list[dict] = []
        pages = self._client.get_plist_meta(playlist_id)
        if isinstance(pages, dict):
            pages = [pages]
        for page in pages:
            tracks.extend(page.get("tracks", {}).get("items", []))
        return tracks

    def get_track_album_id(self, track_id: str) -> Optional[str]:
        """Return the Qobuz album id for a track, using DB cache when possible."""
        cached = db.get_cached_album(str(track_id))
        if cached:
            return cached["album_id"]
        self._ensure_client()
        meta = self._client.get_track_meta(str(track_id))
        album_id = str(meta.get("album", {}).get("id", ""))
        if album_id:
            db.cache_track_album(
                str(track_id), album_id, album_url_from_id(album_id)
            )
        return album_id or None

    def playlist_to_album_ids(self, playlist_url: str) -> list[str]:
        """
        Given a playlist URL return deduplicated album IDs for all tracks,
        caching the track→album mapping in the DB.
        """
        tracks = self.get_playlist_tracks(playlist_url)
        seen: set[str] = set()
        album_ids: list[str] = []
        for track in tracks:
            album = track.get("album", {})
            album_id = str(album.get("id", ""))
            track_id = str(track.get("id", ""))
            if album_id and album_id not in seen:
                seen.add(album_id)
                album_ids.append(album_id)
            if track_id and album_id:
                db.cache_track_album(
                    track_id, album_id, album_url_from_id(album_id)
                )
        return album_ids

    def _get_artist_id_from_track(self, track: dict) -> Optional[str]:
        """Extract the primary artist ID from a track dict."""
        performer = track.get("performer", {})
        if performer.get("id"):
            return str(performer["id"])
        album = track.get("album", {})
        artist = album.get("artist", {})
        if artist.get("id"):
            return str(artist["id"])
        return None

    def playlist_to_artist_ids(self, playlist_url: str) -> list[str]:
        """
        Given a playlist URL return deduplicated artist IDs for all tracks.
        """
        tracks = self.get_playlist_tracks(playlist_url)
        seen: set[str] = set()
        artist_ids: list[str] = []
        for track in tracks:
            artist_id = self._get_artist_id_from_track(track)
            if artist_id and artist_id not in seen:
                seen.add(artist_id)
                artist_ids.append(artist_id)
        return artist_ids


# ── module-level helpers ───────────────────────────────────────────────────────

def album_url_from_id(album_id: str) -> str:
    return f"https://play.qobuz.com/album/{album_id}"


def artist_url_from_id(artist_id: str) -> str:
    return f"https://play.qobuz.com/artist/{artist_id}"


def make_client(token: str) -> QobuzClient:
    return QobuzClient(token)
