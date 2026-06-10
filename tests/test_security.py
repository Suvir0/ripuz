"""
Tests for security hardening: CSRF protection, response headers,
settings path validation, and auth brute-force backoff.
"""
import importlib
import os
import stat
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app.config as cfg
import app.db as db_mod


@pytest.fixture()
def client(tmp_dirs):
    db_mod.init_db(cfg.DB_FILE)
    with patch("app.jobs.start_worker"), patch("app.jobs.stop_worker"):
        import app.main as main_mod
        importlib.reload(main_mod)
        with TestClient(main_mod.app, raise_server_exceptions=True) as c:
            yield c


# ── CSRF: Origin header ────────────────────────────────────────────────────────

def test_csrf_cross_origin_rejected(client):
    r = client.post(
        "/api/jobs",
        json={"type": "fetch_lyrics", "url": "library"},
        headers={"Origin": "http://evil.example.com"},
    )
    assert r.status_code == 403
    assert "cross-origin" in r.json()["error"]


def test_csrf_same_origin_allowed(client):
    # testserver host matches the Host header; should pass CSRF and get a real response
    r = client.post(
        "/api/jobs",
        json={"type": "fetch_lyrics", "url": "library"},
        headers={"Origin": "http://testserver"},
    )
    # CSRF passes — we'll get 200 (job enqueued)
    assert r.status_code == 200


def test_csrf_no_origin_allowed(client):
    # curl/scripts have no Origin — should NOT be blocked
    r = client.post(
        "/api/jobs",
        json={"type": "fetch_lyrics", "url": "library"},
    )
    assert r.status_code == 200


def test_csrf_sec_fetch_cross_site_rejected(client):
    r = client.post(
        "/api/jobs",
        json={"type": "fetch_lyrics", "url": "library"},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert r.status_code == 403


def test_csrf_sec_fetch_same_origin_allowed(client):
    r = client.post(
        "/api/jobs",
        json={"type": "fetch_lyrics", "url": "library"},
        headers={"Sec-Fetch-Site": "same-origin"},
    )
    assert r.status_code == 200


def test_csrf_delete_cross_origin_rejected(client):
    r = client.delete(
        "/api/jobs/999",
        headers={"Origin": "http://evil.example.com"},
    )
    assert r.status_code == 403


# ── Security response headers ──────────────────────────────────────────────────

def test_security_headers_on_static(client):
    r = client.get("/")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "same-origin"
    assert "Content-Security-Policy" in r.headers


def test_security_headers_on_api(client):
    r = client.get("/api/jobs")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"


# ── Settings path validation ───────────────────────────────────────────────────

def test_settings_relative_path_rejected(client):
    r = client.post("/api/settings", json={"downloads_dir": "relative/path"})
    assert r.status_code == 400
    assert "absolute" in r.json()["error"]


def test_settings_etc_path_rejected(client):
    r = client.post("/api/settings", json={"downloads_dir": "/etc"})
    assert r.status_code == 400


def test_settings_path_outside_root_rejected(client):
    r = client.post("/api/settings", json={"music_dir": "/tmp/outside"})
    assert r.status_code == 400


def test_settings_subpath_of_root_accepted(client, tmp_dirs):
    sub = cfg.DOWNLOADS_DIR / "sub"
    sub.mkdir()
    r = client.post("/api/settings", json={"downloads_dir": str(sub)})
    assert r.status_code == 200


def test_settings_root_itself_accepted(client, tmp_dirs):
    r = client.post("/api/settings", json={"downloads_dir": str(cfg.DOWNLOADS_DIR)})
    assert r.status_code == 200


# ── DB file permissions ────────────────────────────────────────────────────────

def test_db_file_permissions(tmp_dirs):
    mode = os.stat(cfg.DB_FILE).st_mode & 0o777
    assert mode == 0o600


# ── Auth brute-force backoff ───────────────────────────────────────────────────

@pytest.fixture()
def auth_client(tmp_dirs, monkeypatch):
    """Client with auth enabled; resets failure state before and after tests."""
    monkeypatch.setenv("RIPUZ_AUTH_PASS", "secret")
    # Reload config first so _AUTH_PASS picks up the new env var
    importlib.reload(cfg)
    import app.main as main_mod
    importlib.reload(main_mod)
    # Clear any stale failure state
    main_mod._auth_failures.clear()
    db_mod.init_db(cfg.DB_FILE)
    with patch("app.jobs.start_worker"), patch("app.jobs.stop_worker"):
        with TestClient(main_mod.app, raise_server_exceptions=True) as c:
            yield c, main_mod
    # Teardown: reload modules back to default (no auth password) so other tests
    # don't inherit the "secret" password or the brute-force lockout state.
    main_mod._auth_failures.clear()
    monkeypatch.delenv("RIPUZ_AUTH_PASS", raising=False)
    importlib.reload(cfg)
    importlib.reload(main_mod)


def test_auth_correct_credentials(auth_client):
    c, _ = auth_client
    r = c.get("/api/jobs", auth=("ripuz", "secret"))
    assert r.status_code == 200


def test_auth_wrong_credentials(auth_client):
    c, _ = auth_client
    r = c.get("/api/jobs", auth=("ripuz", "wrong"))
    assert r.status_code == 401


def test_auth_brute_force_lockout(auth_client):
    c, main_mod = auth_client
    # 5 failures → 6th should get 429
    for _ in range(6):
        c.get("/api/jobs", auth=("ripuz", "wrong"))
    r = c.get("/api/jobs", auth=("ripuz", "wrong"))
    assert r.status_code == 429
