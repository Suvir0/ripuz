"""
Thin wrapper around qobuz_dl.qopy.Client for playlist/track/album/artist lookup.
Only used by the expand and discography pipeline paths; actual downloading is done
by qobuz-dl CLI subprocess in qobuz_cli.py.
"""
import logging
import re
from typing import Optional

from app import config, db

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


def _album_dict(album: dict) -> dict:
    """Normalise a raw album object from the Qobuz API into our plan format."""
    album_id = str(album.get("id", ""))
    artist_obj = album.get("artist") or {}
    artist_name = artist_obj.get("name", "") if isinstance(artist_obj, dict) else ""
    return {
        "id": album_id,
        "url": album_url_from_id(album_id),
        "title": album.get("title", ""),
        "artist": artist_name,
        "tracks_count": int(album.get("tracks_count") or 0),
        "duration": int(album.get("duration") or 0),
    }


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

    def get_artist_albums(self, artist_id: str) -> list[dict]:
        """Return all album objects for an artist (paginated)."""
        self._ensure_client()
        pages = self._client.get_artist_meta(str(artist_id))
        if isinstance(pages, dict):
            pages = [pages]
        albums: list[dict] = []
        for page in pages:
            albums.extend(page.get("albums", {}).get("items", []))
        return albums

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

    def playlist_to_album_plan_from_tracks(self, playlist_url: str) -> list[dict]:
        """
        For expand_albums: build album plan from playlist track objects.
        No extra API calls — all metadata comes from the track's embedded album dict.
        """
        tracks = self.get_playlist_tracks(playlist_url)
        seen: set[str] = set()
        albums: list[dict] = []
        for track in tracks:
            raw_album = track.get("album", {})
            album_id = str(raw_album.get("id", ""))
            if not album_id or album_id in seen:
                continue
            seen.add(album_id)
            albums.append(_album_dict(raw_album))
            track_id = str(track.get("id", ""))
            if track_id:
                db.cache_track_album(track_id, album_id, album_url_from_id(album_id))
        return albums

    def discography_to_album_plan(self, artist_url: str) -> list[dict]:
        """Return album plan for a single artist URL."""
        artist_id = _extract_id(artist_url)
        return [_album_dict(a) for a in self.get_artist_albums(artist_id) if a.get("id")]

    def playlist_to_album_plan(self, playlist_url: str) -> list[dict]:
        """
        For expand_discographies: resolve all unique artists in the playlist,
        then return their combined album catalogs (deduplicated).

        Filtering applied:
        - Only expands catalogs for artists who appear as album-artist on at least
          EXPAND_MIN_ARTIST_TRACKS tracks (filters out one-off featured artists).
        - Drops albums whose "<artist> <title>" matches EXPAND_JUNK_PATTERNS.
        """
        tracks = self.get_playlist_tracks(playlist_url)

        # Count how many tracks each artist is the *album* artist for.
        album_artist_counts: dict[str, int] = {}
        for track in tracks:
            album = track.get("album") or {}
            artist = album.get("artist") or {}
            a_id = str(artist.get("id", "")).strip()
            if a_id:
                album_artist_counts[a_id] = album_artist_counts.get(a_id, 0) + 1

        min_tracks = config.EXPAND_MIN_ARTIST_TRACKS
        qualified_artists: list[str] = [
            a_id for a_id, cnt in album_artist_counts.items() if cnt >= min_tracks
        ]
        logger.debug(
            "expand_discographies: %d artist(s) meet min_tracks=%d (of %d total)",
            len(qualified_artists), min_tracks, len(album_artist_counts),
        )

        junk_re: Optional[re.Pattern] = None
        if config.EXPAND_JUNK_PATTERNS:
            try:
                junk_re = re.compile(config.EXPAND_JUNK_PATTERNS, re.IGNORECASE)
            except re.error as exc:
                logger.warning("EXPAND_JUNK_PATTERNS invalid regex (%s); skipping filter", exc)

        seen_albums: set[str] = set()
        albums: list[dict] = []
        for artist_id in qualified_artists:
            for raw_album in self.get_artist_albums(artist_id):
                album_id = str(raw_album.get("id", ""))
                if not album_id or album_id in seen_albums:
                    continue
                seen_albums.add(album_id)
                d = _album_dict(raw_album)
                if junk_re:
                    probe = f"{d.get('artist', '')} {d.get('title', '')}"
                    if junk_re.search(probe):
                        logger.debug("expand_discographies: skipping junk album: %s", probe)
                        continue
                albums.append(d)
        return albums

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
