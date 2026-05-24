"""
Phase 2 tests: QobuzClient — playlist parsing, album lookup, dedup, DB caching.
All Qobuz API calls are mocked (no real network).
"""
from unittest.mock import MagicMock, patch

import pytest

from app.qobuz_client import (
    QobuzClient,
    album_url_from_id,
    _extract_id,
    is_valid_qobuz_input,
    make_client,
)


# ── _extract_id ────────────────────────────────────────────────────────────────

def test_extract_id_from_playlist_url():
    assert _extract_id("https://play.qobuz.com/playlist/12345678") == "12345678"


def test_extract_id_from_album_url():
    assert _extract_id("https://play.qobuz.com/album/qxjbxh1dc3xyb") == "qxjbxh1dc3xyb"


def test_extract_id_raw_id_passthrough():
    assert _extract_id("12345678") == "12345678"


def test_extract_id_open_qobuz_url():
    assert _extract_id("https://open.qobuz.com/playlist/99887766") == "99887766"


def test_extract_id_invalid_url_raises():
    with pytest.raises(ValueError):
        _extract_id("https://example.com/playlist/99887766")


def test_is_valid_qobuz_input_accepts_url_and_id():
    assert is_valid_qobuz_input("https://play.qobuz.com/album/qxjbxh1dc3xyb") is True
    assert is_valid_qobuz_input("12345678") is True


def test_is_valid_qobuz_input_rejects_non_qobuz():
    assert is_valid_qobuz_input("https://example.com/album/1") is False


# ── album_url_from_id ──────────────────────────────────────────────────────────

def test_album_url_from_id():
    assert album_url_from_id("abc123") == "https://play.qobuz.com/album/abc123"


# ── fixture helpers ────────────────────────────────────────────────────────────

def _make_mock_client(plist_meta=None, track_meta=None):
    """Return a QobuzClient whose internal qopy Client is fully mocked."""
    client = QobuzClient("fake_token")
    mock_qopy = MagicMock()
    if plist_meta is not None:
        mock_qopy.get_plist_meta.return_value = plist_meta
    if track_meta is not None:
        mock_qopy.get_track_meta.return_value = track_meta
    client._client = mock_qopy
    return client


def _playlist_fixture(*tracks):
    """Build a minimal Qobuz playlist/get API response."""
    return {"tracks": {"items": list(tracks), "total": len(tracks)}}


def _track(track_id: str, title: str, album_id: str, album_title: str) -> dict:
    return {
        "id": track_id,
        "title": title,
        "album": {"id": album_id, "title": album_title},
        "performer": {"name": "Drake"},
    }


# ── get_playlist_tracks ────────────────────────────────────────────────────────

def test_get_playlist_tracks_returns_items():
    t1 = _track("t1", "What Did I Miss?", "album_iceman", "ICEMAN")
    t2 = _track("t2", "Family Matters", "album_fm", "For All The Dogs")
    plist = _playlist_fixture(t1, t2)

    client = _make_mock_client(plist_meta=plist)
    tracks = client.get_playlist_tracks("https://play.qobuz.com/playlist/99")
    client._client.get_plist_meta.assert_called_once_with("99")
    assert len(tracks) == 2
    assert tracks[0]["title"] == "What Did I Miss?"


def test_get_playlist_tracks_empty_playlist():
    client = _make_mock_client(plist_meta={"tracks": {"items": [], "total": 0}})
    assert client.get_playlist_tracks("https://play.qobuz.com/playlist/0") == []


# ── get_track_album_id ─────────────────────────────────────────────────────────

def test_get_track_album_id_from_api():
    track_response = {
        "id": "t1",
        "title": "What Did I Miss?",
        "album": {"id": "album_iceman", "title": "ICEMAN"},
    }
    client = _make_mock_client(track_meta=track_response)
    album_id = client.get_track_album_id("t1")
    assert album_id == "album_iceman"


def test_get_track_album_id_uses_db_cache():
    import app.db as db
    db.cache_track_album("t_cached", "album_cached", "https://play.qobuz.com/album/album_cached")

    client = QobuzClient("fake_token")
    mock_qopy = MagicMock()
    client._client = mock_qopy  # client is already set; cache hit should skip it

    album_id = client.get_track_album_id("t_cached")
    assert album_id == "album_cached"
    mock_qopy.get_track_meta.assert_not_called()


def test_get_track_album_id_writes_cache():
    import app.db as db
    track_response = {"id": "tnew", "album": {"id": "alb_new", "title": "New Album"}}
    client = _make_mock_client(track_meta=track_response)
    client.get_track_album_id("tnew")
    cached = db.get_cached_album("tnew")
    assert cached is not None
    assert cached["album_id"] == "alb_new"


# ── playlist_to_album_ids ──────────────────────────────────────────────────────

def test_playlist_to_album_ids_deduplicates():
    """Two tracks on the same album → only one album_id returned."""
    t1 = _track("t1", "What Did I Miss?", "album_iceman", "ICEMAN")
    t2 = _track("t2", "Mob Ties", "album_iceman", "ICEMAN")   # same album
    t3 = _track("t3", "Family Matters", "album_fm", "For All The Dogs")
    plist = _playlist_fixture(t1, t2, t3)

    client = _make_mock_client(plist_meta=plist)
    album_ids = client.playlist_to_album_ids("https://play.qobuz.com/playlist/1")
    assert album_ids == ["album_iceman", "album_fm"]
    assert len(album_ids) == 2


def test_playlist_to_album_ids_preserves_order():
    tracks = [_track(f"t{i}", f"Song {i}", f"album_{i}", f"Album {i}") for i in range(5)]
    client = _make_mock_client(plist_meta=_playlist_fixture(*tracks))
    ids = client.playlist_to_album_ids("https://play.qobuz.com/playlist/1")
    assert ids == [f"album_{i}" for i in range(5)]


def test_playlist_to_album_ids_caches_tracks():
    import app.db as db
    t1 = _track("cache_t1", "Song", "cache_alb", "Album")
    client = _make_mock_client(plist_meta=_playlist_fixture(t1))
    client.playlist_to_album_ids("https://play.qobuz.com/playlist/1")
    assert db.get_cached_album("cache_t1")["album_id"] == "cache_alb"


def test_playlist_to_album_ids_skips_tracks_without_album():
    t1 = {"id": "t_noalbum", "title": "Mystery", "album": {}}  # no album id
    t2 = _track("t_good", "Real Song", "alb_real", "Real Album")
    client = _make_mock_client(plist_meta=_playlist_fixture(t1, t2))
    ids = client.playlist_to_album_ids("https://play.qobuz.com/playlist/1")
    assert ids == ["alb_real"]


# ── make_client factory ────────────────────────────────────────────────────────

def test_make_client_returns_qobuz_client():
    c = make_client("tok")
    assert isinstance(c, QobuzClient)
    assert c._token == "tok"
