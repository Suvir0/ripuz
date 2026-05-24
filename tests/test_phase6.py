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
    assert data["qobuz_token"] == ""  # not set yet


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
