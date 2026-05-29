"""
Tests for the explicit-upgrade feature:
  - app.explicit.normalize()
  - app.explicit.find_explicit_album()
  - app.explicit.find_explicit_track()
  - QobuzClient.playlist_to_explicit_album_plan()
  - QobuzClient.library_to_explicit_album_plan()
  - QobuzClient.playlist_to_explicit_track_urls()
  - pipeline._build_plan(skip_present_check=True)
  - run_explicit_upgrade_resolve() — resolve phase
  - run_explicit_upgrade_download() — download phase
  - jobs._process_job() routing
  - API: explicit_upgrade type accepted; library sentinel accepted
"""
import json
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app import db
from app.explicit import normalize, find_explicit_album, find_explicit_track
from app.qobuz_client import QobuzClient, _album_dict
from app.pipeline import (
    _build_plan,
    run_explicit_upgrade_resolve,
    run_explicit_upgrade_download,
)
from app.jobs import _process_job
from app.qobuz_cli import DownloadResult
from app.picard import PicardResult
from app.mover import MoveResult


# ── fixtures / helpers ─────────────────────────────────────────────────────────

def _ok_download():
    return DownloadResult(success=True)


def _ok_picard():
    return PicardResult(success=True)


def _ok_move(n: int = 1):
    return MoveResult(moved=[Path(f"/music/a/b/track{i}.FLAC") for i in range(n)])


def _empty_move():
    return MoveResult()


def _make_track(parental_warning: bool, title: str, artist: str,
                album_title: str, duration: int, track_id: str = "t1",
                album_id: str = "alb1") -> dict:
    """Build a minimal Qobuz track dict."""
    return {
        "id": track_id,
        "title": title,
        "parental_warning": parental_warning,
        "duration": duration,
        "album": {
            "id": album_id,
            "title": album_title,
            "artist": {"id": "ar1", "name": artist},
            "tracks_count": 12,
            "duration": 3000,
        },
    }


def _search_response(tracks: list) -> dict:
    return {"tracks": {"items": tracks}}


def _make_client_with_search(search_results: list) -> QobuzClient:
    """Return a QobuzClient whose search_tracks() returns search_results."""
    client = QobuzClient.__new__(QobuzClient)
    client._token = "fake"
    client._client = None
    client.search_tracks = MagicMock(return_value=_search_response(search_results))
    client.search_albums = MagicMock(return_value={})
    return client


# ── normalize() ────────────────────────────────────────────────────────────────

class TestNormalize:
    def test_lowercases(self):
        assert normalize("Hello World") == "hello world"

    def test_strips_clean_parens(self):
        assert normalize("Song (Clean)") == "song"

    def test_strips_explicit_parens(self):
        assert normalize("Song (Explicit)") == "song"

    def test_strips_feat(self):
        assert normalize("Song (feat. Someone)") == "song"

    def test_strips_ft(self):
        assert normalize("Song (ft. Someone)") == "song"

    def test_strips_radio_edit(self):
        assert normalize("Song (Radio Edit)") == "song"

    def test_punctuation_removed(self):
        assert normalize("Don't Stop") == "don t stop"

    def test_collapse_spaces(self):
        assert normalize("  hello   world  ") == "hello world"

    def test_empty_string(self):
        assert normalize("") == ""

    def test_same_after_strip(self):
        # No qualifiers — just lowercased
        assert normalize("Good Kid") == "good kid"


# ── find_explicit_album() ──────────────────────────────────────────────────────

class TestFindExplicitAlbum:
    def test_returns_explicit_album_when_found(self):
        explicit_track = _make_track(
            parental_warning=True,
            title="Money Trees",
            artist="Kendrick Lamar",
            album_title="good kid, m.A.A.d city",
            duration=386,
            track_id="t2",
            album_id="alb_expl",
        )
        client = _make_client_with_search([explicit_track])
        result = find_explicit_album(
            client,
            artist="Kendrick Lamar",
            title="Money Trees",
            album_title="good kid, m.A.A.d city",
            duration=386,
        )
        assert result is not None
        assert result["id"] == "alb_expl"

    def test_returns_none_when_only_clean(self):
        clean_track = _make_track(
            parental_warning=False,
            title="Money Trees",
            artist="Kendrick Lamar",
            album_title="good kid, m.A.A.d city (Clean)",
            duration=386,
        )
        client = _make_client_with_search([clean_track])
        result = find_explicit_album(
            client,
            artist="Kendrick Lamar",
            title="Money Trees",
        )
        assert result is None

    def test_prefers_same_album_title(self):
        """When both a same-album and other-album explicit exist, pick same-album."""
        same_album = _make_track(
            parental_warning=True,
            title="HUMBLE.",
            artist="Kendrick Lamar",
            album_title="DAMN.",
            duration=177,
            track_id="t_same",
            album_id="alb_damn",
        )
        other_album = _make_track(
            parental_warning=True,
            title="HUMBLE.",
            artist="Kendrick Lamar",
            album_title="Greatest Hits",
            duration=177,
            track_id="t_other",
            album_id="alb_hits",
        )
        # Put other_album first so the fallback would pick it without the preference.
        client = _make_client_with_search([other_album, same_album])
        result = find_explicit_album(
            client,
            artist="Kendrick Lamar",
            title="HUMBLE.",
            album_title="DAMN.",
            duration=177,
        )
        assert result is not None
        assert result["id"] == "alb_damn"

    def test_duration_tolerance_respected(self):
        """Track with duration too far off should be rejected."""
        explicit_track = _make_track(
            parental_warning=True,
            title="Track",
            artist="Artist",
            album_title="Album",
            duration=300,
        )
        client = _make_client_with_search([explicit_track])
        # Our track is 200 s, explicit is 300 s → 100 s off, tol=4
        result = find_explicit_album(
            client, artist="Artist", title="Track", duration=200, duration_tol=4
        )
        assert result is None

    def test_duration_within_tolerance(self):
        explicit_track = _make_track(
            parental_warning=True,
            title="Track",
            artist="Artist",
            album_title="Album",
            duration=203,
            album_id="alb_ok",
        )
        client = _make_client_with_search([explicit_track])
        result = find_explicit_album(
            client, artist="Artist", title="Track", duration=200, duration_tol=4
        )
        assert result is not None
        assert result["id"] == "alb_ok"

    def test_title_mismatch_skipped(self):
        """Track whose normalized title differs should be skipped."""
        explicit_track = _make_track(
            parental_warning=True,
            title="Different Title",
            artist="Artist",
            album_title="Album",
            duration=200,
        )
        client = _make_client_with_search([explicit_track])
        result = find_explicit_album(
            client, artist="Artist", title="My Song", duration=200
        )
        assert result is None

    def test_artist_mismatch_skipped(self):
        explicit_track = _make_track(
            parental_warning=True,
            title="My Song",
            artist="Other Artist",
            album_title="Album",
            duration=200,
        )
        client = _make_client_with_search([explicit_track])
        result = find_explicit_album(
            client, artist="The Real Artist", title="My Song", duration=200
        )
        assert result is None

    def test_search_exception_returns_none(self):
        client = QobuzClient.__new__(QobuzClient)
        client._token = "fake"
        client._client = None
        client.search_tracks = MagicMock(side_effect=RuntimeError("network err"))
        result = find_explicit_album(client, artist="A", title="T")
        assert result is None

    def test_normalised_matching_strips_clean_qualifier(self):
        """Clean title 'Song (Clean)' should still match explicit 'Song'."""
        explicit_track = _make_track(
            parental_warning=True,
            title="Song",
            artist="Artist",
            album_title="Album",
            duration=200,
            album_id="alb_good",
        )
        client = _make_client_with_search([explicit_track])
        result = find_explicit_album(
            client, artist="Artist", title="Song (Clean)", duration=200
        )
        assert result is not None
        assert result["id"] == "alb_good"


# ── find_explicit_track() ──────────────────────────────────────────────────────

class TestFindExplicitTrack:
    def test_returns_track_dict(self):
        explicit_track = _make_track(
            parental_warning=True,
            title="Track",
            artist="Artist",
            album_title="Album",
            duration=200,
            track_id="tx",
        )
        client = _make_client_with_search([explicit_track])
        result = find_explicit_track(client, artist="Artist", title="Track")
        assert result is not None
        assert result["id"] == "tx"

    def test_returns_none_when_no_explicit(self):
        client = _make_client_with_search([])
        result = find_explicit_track(client, artist="A", title="T")
        assert result is None


# ── playlist_to_explicit_album_plan() ─────────────────────────────────────────

class TestPlaylistToExplicitAlbumPlan:
    def _make_playlist_client(self, playlist_tracks, search_results_per_call):
        client = QobuzClient.__new__(QobuzClient)
        client._token = "fake"
        client._client = None
        client.get_playlist_tracks = MagicMock(return_value=playlist_tracks)
        client.search_tracks = MagicMock(
            side_effect=[_search_response(r) for r in search_results_per_call]
        )
        return client

    def test_clean_track_resolved_to_explicit_album(self):
        clean = _make_track(
            parental_warning=False, title="Song", artist="Artist",
            album_title="Album (Clean)", duration=200,
        )
        explicit = _make_track(
            parental_warning=True, title="Song", artist="Artist",
            album_title="Album", duration=200, album_id="alb_expl",
        )
        client = self._make_playlist_client([clean], [[explicit]])
        albums, report = client.playlist_to_explicit_album_plan("https://play.qobuz.com/playlist/abc")
        assert len(albums) == 1
        assert albums[0]["id"] == "alb_expl"

    def test_already_explicit_tracks_skipped(self):
        explicit = _make_track(
            parental_warning=True, title="Song", artist="Artist",
            album_title="Album", duration=200,
        )
        client = self._make_playlist_client([explicit], [])
        albums, report = client.playlist_to_explicit_album_plan("https://play.qobuz.com/playlist/abc")
        assert albums == []
        assert report == []
        client.search_tracks.assert_not_called()

    def test_no_match_appears_in_report(self):
        clean = _make_track(
            parental_warning=False, title="Song", artist="Artist",
            album_title="Album (Clean)", duration=200,
        )
        client = self._make_playlist_client([clean], [[]])  # empty search result
        albums, report = client.playlist_to_explicit_album_plan("https://play.qobuz.com/playlist/abc")
        assert albums == []
        assert any("no explicit match" in r for r in report)

    def test_title_mismatch_in_report(self):
        clean = _make_track(
            parental_warning=False, title="Song", artist="Artist",
            album_title="Orig Album", duration=200,
        )
        explicit = _make_track(
            parental_warning=True, title="Song", artist="Artist",
            album_title="Explicit Super Edition",  # different title
            duration=200, album_id="alb_diff",
        )
        client = self._make_playlist_client([clean], [[explicit]])
        albums, report = client.playlist_to_explicit_album_plan("https://play.qobuz.com/playlist/abc")
        assert len(albums) == 1
        assert any("title mismatch" in r for r in report)

    def test_duplicate_albums_deduplicated(self):
        """Two clean tracks from the same album → only one album in plan."""
        explicit_alb = _make_track(
            parental_warning=True, title="Song A", artist="Artist",
            album_title="Album", duration=200, album_id="alb_shared",
        )
        explicit_alb2 = _make_track(
            parental_warning=True, title="Song B", artist="Artist",
            album_title="Album", duration=210, album_id="alb_shared",
        )
        clean1 = _make_track(
            parental_warning=False, title="Song A", artist="Artist",
            album_title="Album (Clean)", duration=200, track_id="t1",
        )
        clean2 = _make_track(
            parental_warning=False, title="Song B", artist="Artist",
            album_title="Album (Clean)", duration=210, track_id="t2",
        )
        client = self._make_playlist_client([clean1, clean2], [[explicit_alb], [explicit_alb2]])
        albums, _ = client.playlist_to_explicit_album_plan("https://play.qobuz.com/playlist/abc")
        assert len(albums) == 1
        assert albums[0]["id"] == "alb_shared"


# ── library_to_explicit_album_plan() ──────────────────────────────────────────

class TestLibraryToExplicitAlbumPlan:
    def _make_fake_flac(self, tmp_path: Path, artist: str, album: str, title: str,
                        advisory: str | None, duration: float = 200.0) -> Path:
        """Create a minimal FLAC-shaped object via mutagen that library_to_explicit_album_plan can read."""
        from mutagen.flac import FLAC
        # Build an actual FLAC file using mutagen in-memory
        path = tmp_path / "music" / artist / album / f"{title}.FLAC"
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write a tiny valid FLAC (32 bytes of silence via raw bytes is complex;
        # easier to mock mutagen.flac.FLAC at the test level).
        path.write_bytes(b"")
        return path

    def test_clean_flac_resolved(self, tmp_path):
        """A FLAC with ITUNESADVISORY=0 triggers a search and appears in the plan."""
        music_dir = tmp_path / "music"
        music_dir.mkdir(exist_ok=True)

        fake_path = music_dir / "Artist" / "Album_(Clean)" / "Song.FLAC"
        fake_path.parent.mkdir(parents=True, exist_ok=True)
        fake_path.write_bytes(b"")

        explicit_track = _make_track(
            parental_warning=True, title="Song", artist="Artist",
            album_title="Album", duration=200, album_id="alb_expl",
        )

        class FakeTags:
            def get(self, key):
                return {"itunesadvisory": ["0"], "albumartist": ["Artist"],
                        "title": ["Song"], "album": ["Album (Clean)"]}.get(key)

        class FakeInfo:
            length = 200.0

        class FakeFLAC:
            def __init__(self, path): pass
            def get(self, key):
                return FakeTags().get(key)
            @property
            def info(self):
                return FakeInfo()

        client = QobuzClient.__new__(QobuzClient)
        client._token = "fake"
        client._client = None
        client.search_tracks = MagicMock(return_value=_search_response([explicit_track]))

        with patch("app.qobuz_client.FLAC", FakeFLAC), \
             patch("app.qobuz_client.find_flac_files", return_value=[fake_path]):
            albums, report = client.library_to_explicit_album_plan(music_dir)

        assert len(albums) == 1
        assert albums[0]["id"] == "alb_expl"

    def test_explicit_flac_skipped(self, tmp_path):
        """A FLAC with ITUNESADVISORY=1 is not searched."""
        music_dir = tmp_path / "music"
        music_dir.mkdir(exist_ok=True)

        class FakeInfo:
            length = 200.0

        class FakeFLAC:
            def __init__(self, path): pass
            def get(self, key):
                return {"itunesadvisory": ["1"]}.get(key)
            @property
            def info(self): return FakeInfo()

        client = QobuzClient.__new__(QobuzClient)
        client._token = "fake"
        client._client = None
        client.search_tracks = MagicMock()

        with patch("app.qobuz_client.FLAC", FakeFLAC), \
             patch("app.qobuz_client.find_flac_files", return_value=[music_dir / "x.FLAC"]):
            albums, report = client.library_to_explicit_album_plan(music_dir)

        assert albums == []
        client.search_tracks.assert_not_called()

    def test_no_advisory_tag_reported(self, tmp_path):
        """A FLAC missing the advisory tag is reported as skipped."""
        music_dir = tmp_path / "music"
        music_dir.mkdir(exist_ok=True)

        class FakeInfo:
            length = 200.0

        class FakeFLAC:
            def __init__(self, path): pass
            def get(self, key): return None  # no tags at all
            @property
            def info(self): return FakeInfo()

        client = QobuzClient.__new__(QobuzClient)
        client._token = "fake"
        client._client = None
        client.search_tracks = MagicMock()

        with patch("app.qobuz_client.FLAC", FakeFLAC), \
             patch("app.qobuz_client.find_flac_files", return_value=[music_dir / "x.FLAC"]):
            albums, report = client.library_to_explicit_album_plan(music_dir)

        assert albums == []
        assert any("no advisory tag" in r for r in report)
        client.search_tracks.assert_not_called()


# ── playlist_to_explicit_track_urls() ─────────────────────────────────────────

class TestPlaylistToExplicitTrackUrls:
    def test_clean_track_replaced_by_explicit(self):
        clean = _make_track(
            parental_warning=False, title="Song", artist="Artist",
            album_title="Album (Clean)", duration=200, track_id="clean_id",
        )
        explicit_track = _make_track(
            parental_warning=True, title="Song", artist="Artist",
            album_title="Album", duration=200, track_id="expl_id",
        )
        client = QobuzClient.__new__(QobuzClient)
        client._token = "fake"
        client._client = None
        client.get_playlist_tracks = MagicMock(return_value=[clean])
        client.search_tracks = MagicMock(return_value=_search_response([explicit_track]))

        urls = client.playlist_to_explicit_track_urls("https://play.qobuz.com/playlist/abc")
        assert urls == ["https://play.qobuz.com/track/expl_id"]

    def test_already_explicit_kept(self):
        explicit = _make_track(
            parental_warning=True, title="Song", artist="Artist",
            album_title="Album", duration=200, track_id="ex_id",
        )
        client = QobuzClient.__new__(QobuzClient)
        client._token = "fake"
        client._client = None
        client.get_playlist_tracks = MagicMock(return_value=[explicit])
        client.search_tracks = MagicMock()

        urls = client.playlist_to_explicit_track_urls("https://play.qobuz.com/playlist/abc")
        assert urls == ["https://play.qobuz.com/track/ex_id"]
        client.search_tracks.assert_not_called()

    def test_clean_with_no_match_uses_original(self):
        clean = _make_track(
            parental_warning=False, title="Song", artist="Artist",
            album_title="Album (Clean)", duration=200, track_id="orig_id",
        )
        client = QobuzClient.__new__(QobuzClient)
        client._token = "fake"
        client._client = None
        client.get_playlist_tracks = MagicMock(return_value=[clean])
        client.search_tracks = MagicMock(return_value=_search_response([]))  # no results

        urls = client.playlist_to_explicit_track_urls("https://play.qobuz.com/playlist/abc")
        assert urls == ["https://play.qobuz.com/track/orig_id"]


# ── _build_plan skip_present_check ────────────────────────────────────────────

class TestBuildPlanSkipPresent:
    def _fake_album(self, album_id: str, artist: str, title: str,
                    tracks_count: int = 1) -> dict:
        return {
            "id": album_id,
            "url": f"https://play.qobuz.com/album/{album_id}",
            "title": title,
            "artist": artist,
            "tracks_count": tracks_count,
            "duration": 2400,
        }

    def test_skip_present_false_filters_existing_album(self, tmp_path):
        from app import config
        # Create a fake album directory so album_already_present returns True.
        # sanitize_path("The Artist") == "The_Artist", etc.
        album_dir = config.MUSIC_DIR / "The_Artist" / "The_Album"
        album_dir.mkdir(parents=True)
        (album_dir / "track.FLAC").write_bytes(b"")

        job_id = db.create_job("explicit_upgrade", "library")
        # tracks_count=1 matches the single FLAC we created.
        album = self._fake_album("alb1", "The Artist", "The Album", tracks_count=1)
        plan = _build_plan([album], 27, job_id, skip_present_check=False)
        # album_already_present will match — album should be skipped
        assert plan["skipped_existing"] == 1
        assert len(plan["albums"]) == 0

    def test_skip_present_true_includes_existing_album(self, tmp_path):
        from app import config
        album_dir = config.MUSIC_DIR / "The_Artist" / "The_Album"
        album_dir.mkdir(parents=True)
        (album_dir / "track.FLAC").write_bytes(b"")

        job_id = db.create_job("explicit_upgrade", "library")
        album = self._fake_album("alb1", "The Artist", "The Album", tracks_count=1)
        plan = _build_plan([album], 27, job_id, skip_present_check=True)
        # skip_present_check=True means existing album is NOT filtered
        assert plan["skipped_existing"] == 0
        assert len(plan["albums"]) == 1


# ── run_explicit_upgrade_resolve() ────────────────────────────────────────────

class TestExplicitUpgradeResolve:
    def _album(self, album_id="alb1"):
        return {
            "id": album_id, "url": f"https://play.qobuz.com/album/{album_id}",
            "title": "Album", "artist": "Artist", "tracks_count": 10, "duration": 2400,
        }

    @patch("app.pipeline.make_client")
    @patch("app.pipeline.get_token", return_value="tok")
    def test_library_source(self, mock_token, mock_make_client):
        mock_client = MagicMock()
        mock_client.library_to_explicit_album_plan.return_value = ([self._album()], [])
        mock_make_client.return_value = mock_client

        job_id = db.create_job("explicit_upgrade", "library")
        result = run_explicit_upgrade_resolve(job_id, "library")

        job = db.get_job(job_id)
        assert job["status"] == "awaiting_confirm"
        plan = json.loads(job["plan"])
        assert len(plan["albums"]) == 1
        mock_client.library_to_explicit_album_plan.assert_called_once()

    @patch("app.pipeline.make_client")
    @patch("app.pipeline.get_token", return_value="tok")
    def test_playlist_source(self, mock_token, mock_make_client):
        mock_client = MagicMock()
        mock_client.playlist_to_explicit_album_plan.return_value = ([self._album()], ["warning1"])
        mock_make_client.return_value = mock_client

        job_id = db.create_job("explicit_upgrade", "https://play.qobuz.com/playlist/xyz")
        result = run_explicit_upgrade_resolve(job_id, "https://play.qobuz.com/playlist/xyz")

        job = db.get_job(job_id)
        assert job["status"] == "awaiting_confirm"
        # Warning should appear in log
        assert "warning1" in job["log"]

    @patch("app.pipeline.get_token", return_value="")
    def test_no_token_sets_error(self, mock_token):
        job_id = db.create_job("explicit_upgrade", "library")
        run_explicit_upgrade_resolve(job_id, "library")
        job = db.get_job(job_id)
        assert job["status"] == "error"

    @patch("app.pipeline.make_client")
    @patch("app.pipeline.get_token", return_value="tok")
    def test_report_logged(self, mock_token, mock_make_client):
        mock_client = MagicMock()
        report = ["no explicit match: Artist — Song (album: X)"]
        mock_client.library_to_explicit_album_plan.return_value = ([self._album()], report)
        mock_make_client.return_value = mock_client

        job_id = db.create_job("explicit_upgrade", "library")
        run_explicit_upgrade_resolve(job_id, "library")
        job = db.get_job(job_id)
        assert "no explicit match" in job["log"]


# ── run_explicit_upgrade_download() ───────────────────────────────────────────

class TestExplicitUpgradeDownload:
    def _plan(self, n_albums: int = 1) -> dict:
        return {
            "albums": [
                {
                    "id": f"alb{i}", "url": f"https://play.qobuz.com/album/alb{i}",
                    "title": f"Album{i}", "artist": "Artist",
                    "tracks_count": 10, "duration": 2400,
                }
                for i in range(n_albums)
            ],
            "quality": 27,
            "skipped_existing": 0,
            "skipped_duplicate": 0,
            "est_gb": 1.0,
        }

    @patch("app.pipeline.clean_empty_dirs")
    @patch("app.pipeline.move_album", return_value=MoveResult(moved=[Path("/m/a/b/t.FLAC")]))
    @patch("app.pipeline.run_picard", return_value=PicardResult(success=True))
    @patch("app.pipeline.list_album_dirs", side_effect=[set(), {Path("/dl/Artist/Album")}])
    @patch("app.pipeline.run_download", return_value=DownloadResult(success=True))
    def test_successful_download(self, mock_dl, mock_dirs, mock_picard, mock_move, mock_clean):
        job_id = db.create_job("explicit_upgrade", "library")
        db.update_job(job_id, status="confirmed")
        db.set_job_plan(job_id, json.dumps(self._plan()))

        run_explicit_upgrade_download(job_id, lambda: False)
        job = db.get_job(job_id)
        assert job["status"] in ("done", "done_with_warnings")

    @patch("app.pipeline.clean_empty_dirs")
    @patch("app.pipeline.move_album", return_value=MoveResult(moved=[Path("/m/a/b/t.FLAC")]))
    @patch("app.pipeline.run_picard", return_value=PicardResult(success=True))
    @patch("app.pipeline.list_album_dirs", side_effect=[set(), {Path("/dl/Artist/Album")}])
    @patch("app.pipeline.run_download", return_value=DownloadResult(success=True))
    def test_download_passes_no_db_true(self, mock_dl, mock_dirs, mock_picard, mock_move, mock_clean):
        """Explicit-upgrade must pass no_db=True to run_download so qobuz-dl's
        local DB never silently skips an album that was previously downloaded
        as a clean copy."""
        job_id = db.create_job("explicit_upgrade", "library")
        db.update_job(job_id, status="confirmed")
        db.set_job_plan(job_id, json.dumps(self._plan()))

        run_explicit_upgrade_download(job_id, lambda: False)

        mock_dl.assert_called_once()
        _, kwargs = mock_dl.call_args
        assert kwargs.get("no_db") is True, (
            "run_download must be called with no_db=True for explicit_upgrade "
            "so albums previously recorded in qobuz-dl's database are not skipped"
        )


# ── jobs._process_job() routing ───────────────────────────────────────────────

class TestExplicitUpgradeJobRouting:
    @patch("app.jobs.run_explicit_upgrade_resolve")
    def test_routes_queued_to_resolve(self, mock_resolve):
        job_id = db.create_job("explicit_upgrade", "library")
        job = db.get_job(job_id)
        _process_job(job)
        mock_resolve.assert_called_once_with(job_id, "library")

    @patch("app.jobs.run_explicit_upgrade_download")
    def test_routes_confirmed_to_download(self, mock_download):
        job_id = db.create_job("explicit_upgrade", "library")
        db.update_job(job_id, status="confirmed")
        db.set_job_plan(job_id, json.dumps({"albums": [], "quality": 27}))
        job = db.get_job(job_id)
        _process_job(job)
        mock_download.assert_called_once()


# ── API validation ─────────────────────────────────────────────────────────────

class TestApiValidation:
    """Light-weight checks on api_create_job logic without starting a server."""

    def test_explicit_upgrade_in_valid_types(self):
        from app.main import api_create_job
        # Just ensure the function imports without error — full type list is tested
        # in integration. We verify the set contains our new type.
        import inspect
        src = inspect.getsource(api_create_job)
        assert "explicit_upgrade" in src

    def test_library_sentinel_in_source(self):
        from app.main import api_create_job
        import inspect
        src = inspect.getsource(api_create_job)
        assert '"library"' in src
