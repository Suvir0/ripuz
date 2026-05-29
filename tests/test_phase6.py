"""
Phase 6 tests: FastAPI routes (settings, jobs, add playlist).
Uses TestClient; worker and pipeline are mocked.
"""
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

import app.config as cfg
import app.db as db_mod


@pytest.fixture()
def client(tmp_dirs):
    # Ensure db is initialised for the test app
    db_mod.init_db(cfg.DB_FILE)

    # Prevent the background worker from actually starting
    with patch("app.jobs.start_worker"), patch("app.jobs.stop_worker"):
        from app.main import app
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ── /healthz ───────────────────────────────────────────────────────────────────

def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ── settings ───────────────────────────────────────────────────────────────────

def test_get_settings_default(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert "qobuz_token" in data
    # conftest seeds a token so the fixture environment resembles a configured instance;
    # the API returns "***" for any set token (never the raw value).
    assert data["qobuz_token"] in ("", "***")


def test_save_settings_stores_token(client):
    r = client.post("/api/settings", json={"qobuz_token": "mytoken123"})
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # GET returns masked token (not the raw value)
    r2 = client.get("/api/settings")
    assert r2.json()["qobuz_token"] == "***"


def test_save_settings_writes_config_ini(client):
    import configparser
    client.post("/api/settings", json={"qobuz_token": "tok_for_ini"})
    from app.settings_store import qobuz_dl_config_path
    path = qobuz_dl_config_path()
    assert path.exists()
    parser = configparser.ConfigParser()
    parser.read(path)
    assert parser["qobuz"]["auth_token"] == "tok_for_ini"


def test_save_settings_placeholder_does_not_overwrite(client):
    # Save a real token first
    client.post("/api/settings", json={"qobuz_token": "real_token"})
    # Then POST with placeholder (as browser would send when token field is unchanged)
    client.post("/api/settings", json={"qobuz_token": "***"})
    # Real token should still be there
    from app.settings_store import get_token
    assert get_token() == "real_token"


def test_save_settings_updates_paths(client):
    client.post("/api/settings", json={
        "qobuz_token": "t",
        "downloads_dir": "/my/downloads",
        "music_dir": "/my/music",
    })
    r = client.get("/api/settings")
    assert r.json()["downloads_dir"] == "/my/downloads"
    assert r.json()["music_dir"] == "/my/music"


# ── jobs ───────────────────────────────────────────────────────────────────────

def test_list_jobs_empty(client):
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert r.json() == []


def test_create_playlist_job(client):
    r = client.post("/api/jobs", json={
        "type": "playlist",
        "url": "https://play.qobuz.com/playlist/123",
    })
    assert r.status_code == 200
    data = r.json()
    assert "job_id" in data
    assert isinstance(data["job_id"], int)


def test_create_expand_albums_job(client):
    r = client.post("/api/jobs", json={
        "type": "expand_albums",
        "url": "https://play.qobuz.com/playlist/456",
    })
    assert r.status_code == 200
    assert "job_id" in r.json()


def test_create_job_missing_url(client):
    r = client.post("/api/jobs", json={"type": "playlist", "url": ""})
    assert r.status_code == 400


def test_create_job_invalid_type(client):
    r = client.post("/api/jobs", json={
        "type": "hack", "url": "https://play.qobuz.com/playlist/1"
    })
    assert r.status_code == 400


def test_create_job_rejects_non_qobuz_url(client):
    r = client.post("/api/jobs", json={
        "type": "playlist", "url": "https://example.com/playlist/1"
    })
    assert r.status_code == 400


def test_get_job_by_id(client):
    r = client.post("/api/jobs", json={
        "type": "playlist", "url": "https://play.qobuz.com/playlist/789"
    })
    job_id = r.json()["job_id"]

    r2 = client.get(f"/api/jobs/{job_id}")
    assert r2.status_code == 200
    assert r2.json()["url"] == "https://play.qobuz.com/playlist/789"
    assert r2.json()["status"] == "queued"


def test_get_job_not_found(client):
    r = client.get("/api/jobs/9999")
    assert r.status_code == 404


def test_list_jobs_returns_created_job(client):
    client.post("/api/jobs", json={
        "type": "playlist", "url": "https://play.qobuz.com/playlist/1"
    })
    r = client.get("/api/jobs")
    jobs = r.json()
    assert len(jobs) >= 1
    assert any(j["url"] == "https://play.qobuz.com/playlist/1" for j in jobs)


# ── confirm endpoint ───────────────────────────────────────────────────────────

def test_confirm_job_not_found(client):
    r = client.post("/api/jobs/9999/confirm")
    assert r.status_code == 404


def test_confirm_job_wrong_status(client):
    """Confirming a queued job (not awaiting_confirm) must return 409."""
    r = client.post("/api/jobs", json={
        "type": "playlist", "url": "https://play.qobuz.com/playlist/1"
    })
    job_id = r.json()["job_id"]
    r2 = client.post(f"/api/jobs/{job_id}/confirm")
    assert r2.status_code == 409


def test_confirm_job_happy_path(client):
    """A job in awaiting_confirm state transitions to confirmed."""
    job_id = db_mod.create_job("discography", "https://play.qobuz.com/artist/1")
    db_mod.update_job(job_id, status="awaiting_confirm")

    r = client.post(f"/api/jobs/{job_id}/confirm")
    assert r.status_code == 200
    assert r.json()["ok"] is True

    job = db_mod.get_job(job_id)
    assert job["status"] == "confirmed"


# ── cancel endpoint ────────────────────────────────────────────────────────────

def test_cancel_job_not_found(client):
    r = client.post("/api/jobs/9999/cancel")
    assert r.status_code == 404


def test_cancel_job_already_terminal(client):
    """Cancelling a done job returns 409."""
    job_id = db_mod.create_job("album", "https://play.qobuz.com/album/1")
    db_mod.update_job(job_id, status="done")
    r = client.post(f"/api/jobs/{job_id}/cancel")
    assert r.status_code == 409


def test_cancel_job_happy_path(client):
    """A running job can be cancelled via the API."""
    job_id = db_mod.create_job("album", "https://play.qobuz.com/album/1")
    db_mod.update_job(job_id, status="downloading")

    # cancel_job is imported lazily inside api_cancel_job; patch it at source.
    with patch("app.jobs.cancel_job") as mock_cancel:
        r = client.post(f"/api/jobs/{job_id}/cancel")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    mock_cancel.assert_called_once_with(job_id)


# ── delete endpoint (extra edge cases) ────────────────────────────────────────

def test_delete_terminal_job(client):
    job_id = db_mod.create_job("album", "https://play.qobuz.com/album/del")
    db_mod.update_job(job_id, status="done")
    r = client.delete(f"/api/jobs/{job_id}")
    assert r.status_code == 200


def test_delete_active_job_rejected(client):
    job_id = db_mod.create_job("album", "https://play.qobuz.com/album/del2")
    # job is queued (active) — delete must be rejected
    r = client.delete(f"/api/jobs/{job_id}")
    assert r.status_code == 409


# ── settings — boolean toggles ─────────────────────────────────────────────────

def test_save_download_lyrics_round_trip(client):
    """download_lyrics saves and reads back correctly."""
    client.post("/api/settings", json={"qobuz_token": "t", "download_lyrics": True})
    r = client.get("/api/settings")
    assert r.json()["download_lyrics"] is True

    client.post("/api/settings", json={"qobuz_token": "t", "download_lyrics": False})
    r2 = client.get("/api/settings")
    assert r2.json()["download_lyrics"] is False


def test_save_prefer_explicit_round_trip(client):
    """prefer_explicit saves and reads back correctly."""
    client.post("/api/settings", json={"qobuz_token": "t", "prefer_explicit": True})
    r = client.get("/api/settings")
    assert r.json()["prefer_explicit"] is True

    client.post("/api/settings", json={"qobuz_token": "t", "prefer_explicit": False})
    r2 = client.get("/api/settings")
    assert r2.json()["prefer_explicit"] is False


# ── Basic Auth middleware ──────────────────────────────────────────────────────

@pytest.fixture()
def auth_client(tmp_dirs, monkeypatch):
    """TestClient with RIPUZ_AUTH_PASS set to force auth.

    Reloads app.main with auth env set, then reloads it again without auth after
    the test so the module cache is clean for subsequent tests.
    """
    monkeypatch.setenv("RIPUZ_AUTH_PASS", "s3cr3t")
    monkeypatch.setenv("RIPUZ_AUTH_USER", "ripuz")

    import importlib
    import app.config as cfg
    importlib.reload(cfg)
    import app.main as main_mod
    importlib.reload(main_mod)

    db_mod.init_db(cfg.DB_FILE)
    with patch("app.jobs.start_worker"), patch("app.jobs.stop_worker"):
        with TestClient(main_mod.app, raise_server_exceptions=True) as c:
            yield c

    # Restore: unset auth env and reload so other tests see an unauthenticated app.
    monkeypatch.delenv("RIPUZ_AUTH_PASS", raising=False)
    monkeypatch.delenv("RIPUZ_AUTH_USER", raising=False)
    importlib.reload(cfg)
    importlib.reload(main_mod)


def test_auth_required_without_header(auth_client):
    r = auth_client.get("/api/settings")
    assert r.status_code == 401


def test_auth_rejected_bad_password(auth_client):
    import base64
    creds = base64.b64encode(b"ripuz:wrongpass").decode()
    r = auth_client.get("/api/settings", headers={"Authorization": f"Basic {creds}"})
    assert r.status_code == 401


def test_auth_accepted_good_credentials(auth_client):
    import base64
    creds = base64.b64encode(b"ripuz:s3cr3t").decode()
    r = auth_client.get("/api/settings", headers={"Authorization": f"Basic {creds}"})
    assert r.status_code == 200


def test_auth_healthz_bypasses_auth(auth_client):
    """/healthz must be accessible without credentials even when auth is enabled."""
    r = auth_client.get("/healthz")
    assert r.status_code == 200
