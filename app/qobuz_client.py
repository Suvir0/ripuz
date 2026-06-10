"""
Thin wrapper around qobuz_dl.qopy.Client for playlist/track/album/artist lookup.
Only used by the expand and discography pipeline paths; actual downloading is done
by qobuz-dl CLI subprocess in qobuz_cli.py.
"""
import logging
import re
from typing import Optional

from mutagen.flac import FLAC
from app.structure import find_flac_files
from app.mover import _first_tag

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
            if len(config.EXPAND_JUNK_PATTERNS) > 2048:
                logger.warning("EXPAND_JUNK_PATTERNS exceeds 2048 chars; skipping filter to avoid ReDoS")
            else:
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

    # ── search ────────────────────────────────────────────────────────────────

    def search_tracks(self, query: str, limit: int = 20) -> dict:
        """Search Qobuz tracks. Returns the raw API response dict."""
        self._ensure_client()
        try:
            return self._client.search_tracks(query, limit=limit) or {}
        except Exception as exc:
            logger.warning("search_tracks failed (%s)", exc)
            return {}

    def search_albums(self, query: str, limit: int = 20) -> dict:
        """Search Qobuz albums. Returns the raw API response dict."""
        self._ensure_client()
        try:
            return self._client.search_albums(query, limit=limit) or {}
        except Exception as exc:
            logger.warning("search_albums failed (%s)", exc)
            return {}

    def search(self, query: str, media_type: str = "album", limit: int = 15) -> list[dict]:
        """Unified search returning a normalized list of results.

        media_type: "album" | "track" | "artist"
        """
        if media_type == "track":
            raw = self.search_tracks(query, limit=limit)
            items = raw.get("tracks", {}).get("items", [])
            results = []
            for t in items:
                album_obj = t.get("album") or {}
                artist_obj = t.get("performer") or t.get("artist") or {}
                results.append({
                    "type": "track",
                    "id": str(t.get("id", "")),
                    "url": f"https://play.qobuz.com/track/{t.get('id', '')}",
                    "title": t.get("title", ""),
                    "artist": artist_obj.get("name", "") if isinstance(artist_obj, dict) else "",
                    "album": album_obj.get("title", "") if isinstance(album_obj, dict) else "",
                    "year": str(t.get("release_date_original", ""))[:4],
                    "explicit": bool(t.get("parental_warning")),
                    "cover_url": (album_obj.get("image") or {}).get("small", "") if isinstance(album_obj, dict) else "",
                })
            return results
        elif media_type == "artist":
            self._ensure_client()
            try:
                raw = self._client.search_artists(query, limit=limit) or {}
            except Exception:
                raw = {}
            items = raw.get("artists", {}).get("items", [])
            return [
                {
                    "type": "artist",
                    "id": str(a.get("id", "")),
                    "url": f"https://play.qobuz.com/artist/{a.get('id', '')}",
                    "title": a.get("name", ""),
                    "artist": a.get("name", ""),
                    "cover_url": (a.get("image") or {}).get("small", "") if isinstance(a.get("image"), dict) else "",
                }
                for a in items
            ]
        else:
            raw = self.search_albums(query, limit=limit)
            items = raw.get("albums", {}).get("items", [])
            results = []
            for a in items:
                artist_obj = a.get("artist") or {}
                results.append({
                    "type": "album",
                    "id": str(a.get("id", "")),
                    "url": album_url_from_id(str(a.get("id", ""))),
                    "title": a.get("title", ""),
                    "artist": artist_obj.get("name", "") if isinstance(artist_obj, dict) else "",
                    "year": str(a.get("release_date_original", ""))[:4],
                    "track_count": a.get("tracks_count", 0),
                    "explicit": bool(a.get("parental_warning")),
                    "cover_url": (a.get("image") or {}).get("small", "") if isinstance(a.get("image"), dict) else "",
                })
            return results

    # ── explicit-upgrade plan builders ────────────────────────────────────────

    def playlist_to_explicit_album_plan(
        self, playlist_url: str
    ) -> tuple[list[dict], list[str]]:
        """
        Walk a playlist; for every clean track (parental_warning falsy) search for an
        explicit album twin. Return (albums, report) where:
          - albums  — list of album dicts ready for _build_plan (deduplicated)
          - report  — list of human-readable warning strings (no-match, title-mismatch)
        """
        from app.explicit import find_explicit_album, normalize

        tracks = self.get_playlist_tracks(playlist_url)
        seen_album_ids: set[str] = set()
        albums: list[dict] = []
        report: list[str] = []

        for track in tracks:
            if track.get("parental_warning"):
                # Already explicit — nothing to do.
                continue

            artist_obj = (track.get("album") or {}).get("artist") or {}
            artist = artist_obj.get("name", "")
            title = track.get("title", "")
            raw_album = track.get("album") or {}
            clean_album_title = raw_album.get("title", "")
            duration = track.get("duration") or None

            expl_album = find_explicit_album(
                self, artist, title,
                album_title=clean_album_title,
                duration=duration,
            )

            if expl_album is None:
                report.append(
                    f"no explicit match: {artist} — {title} (album: {clean_album_title})"
                )
                continue

            album_id = expl_album.get("id", "")
            if album_id in seen_album_ids:
                continue
            seen_album_ids.add(album_id)
            albums.append(expl_album)

            # Warn if the explicit album has a meaningfully different title.
            if normalize(expl_album.get("title", "")) != normalize(clean_album_title):
                report.append(
                    f"title mismatch — clean: '{clean_album_title}' → "
                    f"explicit: '{expl_album.get('title', '')}' "
                    f"(will land in a different folder; review manually)"
                )

        return albums, report

    def library_to_explicit_album_plan(
        self, music_dir
    ) -> tuple[list[dict], list[str]]:
        """
        Walk /music, read ITUNESADVISORY tags from FLAC files, and for every clean file
        (ITUNESADVISORY==0) search for an explicit album twin.
        Files with no advisory tag are reported as skipped (not auto-processed).
        Returns (albums, report).
        """
        from pathlib import Path
        from app.explicit import find_explicit_album, normalize

        music_dir = Path(music_dir)
        flacs = find_flac_files(music_dir)

        seen_album_ids: set[str] = set()
        albums: list[dict] = []
        report: list[str] = []

        for path in flacs:
            try:
                tags = FLAC(path)
            except Exception as exc:
                report.append(f"cannot read tags: {path.relative_to(music_dir)} — {exc}")
                continue

            advisory = _first_tag(tags, "itunesadvisory")
            if advisory == "":
                report.append(f"no advisory tag (skipped): {path.relative_to(music_dir)}")
                continue
            if advisory != "0":
                # Explicit (1) or unknown non-zero value — leave alone.
                continue

            artist = _first_tag(tags, "albumartist", "artist", default="Unknown Artist")
            title = _first_tag(tags, "title", default=path.stem)
            album_title = _first_tag(tags, "album", default="")
            duration: Optional[float] = None
            try:
                duration = tags.info.length
            except Exception:
                pass

            expl_album = find_explicit_album(
                self, artist, title,
                album_title=album_title,
                duration=duration,
            )

            if expl_album is None:
                report.append(
                    f"no explicit match: {artist} — {title} (album: {album_title})"
                )
                continue

            album_id = expl_album.get("id", "")
            if album_id in seen_album_ids:
                continue
            seen_album_ids.add(album_id)
            albums.append(expl_album)

            if normalize(expl_album.get("title", "")) != normalize(album_title):
                report.append(
                    f"title mismatch — clean: '{album_title}' → "
                    f"explicit: '{expl_album.get('title', '')}' "
                    f"(will land in a different folder; review manually)"
                )

        return albums, report

    def playlist_to_explicit_track_urls(self, playlist_url: str) -> list[str]:
        """
        For the prefer-explicit toggle: return the best Qobuz track URL for every
        track in the playlist. If a clean track has an explicit twin, substitute
        its URL; otherwise keep the original URL.
        """
        from app.explicit import find_explicit_track

        tracks = self.get_playlist_tracks(playlist_url)
        urls: list[str] = []

        for track in tracks:
            track_id = str(track.get("id", ""))
            if not track_id:
                continue

            if track.get("parental_warning"):
                # Already explicit.
                urls.append(f"https://play.qobuz.com/track/{track_id}")
                continue

            artist_obj = (track.get("album") or {}).get("artist") or {}
            artist = artist_obj.get("name", "")
            title = track.get("title", "")
            duration = track.get("duration") or None

            expl_track = find_explicit_track(self, artist, title, duration=duration)
            if expl_track:
                expl_id = str(expl_track.get("id", ""))
                if expl_id:
                    urls.append(f"https://play.qobuz.com/track/{expl_id}")
                    continue

            # No explicit twin found — use original.
            urls.append(f"https://play.qobuz.com/track/{track_id}")

        return urls


# ── module-level helpers ───────────────────────────────────────────────────────

def album_url_from_id(album_id: str) -> str:
    return f"https://play.qobuz.com/album/{album_id}"


def artist_url_from_id(artist_id: str) -> str:
    return f"https://play.qobuz.com/artist/{artist_id}"


def make_client(token: str) -> QobuzClient:
    return QobuzClient(token)
