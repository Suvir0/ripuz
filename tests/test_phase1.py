"""
Phase 1 tests: config, db, settings_store, /healthz endpoint.
"""
import configparser
import importlib
from pathlib import Path

import pytest


# ── config ─────────────────────────────────────────────────────────────────────

def test_config_dirs_are_paths():
    import app.config as cfg
    assert isinstance(cfg.CONFIG_DIR, Path)
    assert isinstance(cfg.DOWNLOADS_DIR, Path)
    assert isinstance(cfg.MUSIC_DIR, Path)


def test_ensure_dirs_creates_directories(tmp_dirs):
    import app.config as cfg
    assert cfg.CONFIG_DIR.exists()
    assert cfg.DOWNLOADS_DIR.exists()
    assert cfg.MUSIC_DIR.exists()
    assert cfg.QOBUZ_DL_CONFIG_DIR.exists()


def test_quality_default_is_27():
    import app.config as cfg
    assert cfg.QOBUZ_QUALITY == 27


# ── db ─────────────────────────────────────────────────────────────────────────

def test_settings_round_trip():
    import app.db as db
    db.set_setting("foo", "bar")
    assert db.get_setting("foo") == "bar"


def test_settings_overwrite():
    import app.db as db
    db.set_setting("k", "v1")
    db.set_setting("k", "v2")
    assert db.get_setting("k") == "v2"


def test_get_missing_setting_returns_default():
    import app.db as db
    assert db.get_setting("nonexistent", "default") == "default"
    assert db.get_setting("nonexistent") is None


def test_get_all_settings():
    import app.db as db
    db.set_setting("a", "1")
    db.set_setting("b", "2")
    all_s = db.get_all_settings()
    assert all_s["a"] == "1"
    assert all_s["b"] == "2"


def test_job_create_and_get():
    import app.db as db
    job_id = db.create_job("playlist", "https://play.qobuz.com/playlist/123")
    job = db.get_job(job_id)
    assert job["type"] == "playlist"
    assert job["url"] == "https://play.qobuz.com/playlist/123"
    assert job["status"] == "queued"
    assert job["log"] == ""


def test_job_update_status():
    import app.db as db
    job_id = db.create_job("playlist", "https://example.com")
    db.update_job(job_id, status="downloading")
    assert db.get_job(job_id)["status"] == "downloading"


def test_job_append_log():
    import app.db as db
    job_id = db.create_job("playlist", "https://example.com")
    db.append_job_log(job_id, "line 1\n")
    db.append_job_log(job_id, "line 2\n")
    log = db.get_job(job_id)["log"]
    assert "line 1\n" in log
    assert "line 2\n" in log


def test_list_jobs_returns_newest_first():
    import app.db as db
    id1 = db.create_job("playlist", "https://a.com")
    id2 = db.create_job("expand_albums", "https://b.com")
    jobs = db.list_jobs()
    assert jobs[0]["id"] == id2
    assert jobs[1]["id"] == id1


def test_get_queued_jobs_ordered_oldest_first():
    import app.db as db
    id1 = db.create_job("playlist", "https://a.com")
    id2 = db.create_job("playlist", "https://b.com")
    queued = db.get_queued_jobs()
    assert queued[0]["id"] == id1
    assert queued[1]["id"] == id2


def test_album_cache_round_trip():
    import app.db as db
    db.cache_track_album("track_abc", "album_xyz", "https://play.qobuz.com/album/xyz")
    result = db.get_cached_album("track_abc")
    assert result["album_id"] == "album_xyz"
    assert result["album_url"] == "https://play.qobuz.com/album/xyz"


def test_album_cache_miss_returns_none():
    import app.db as db
    assert db.get_cached_album("not_there") is None


# ── delete_job ─────────────────────────────────────────────────────────────────

def test_delete_job_removes_row():
    import app.db as db
    job_id = db.create_job("playlist", "https://example.com/del1")
    db.update_job(job_id, status="done")
    assert db.delete_job(job_id) is True
    assert db.get_job(job_id) is None


def test_delete_job_nonexistent_returns_false():
    import app.db as db
    assert db.delete_job(999999) is False


def test_api_delete_terminal_job():
    from fastapi.testclient import TestClient
    from app.main import app
    import app.db as db

    job_id = db.create_job("playlist", "https://example.com/del2")
    db.update_job(job_id, status="done")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.delete(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    assert db.get_job(job_id) is None


def test_api_delete_active_job_rejected():
    from fastapi.testclient import TestClient
    from app.main import app
    import app.db as db

    job_id = db.create_job("playlist", "https://example.com/del3")
    # queued is not a terminal status
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.delete(f"/api/jobs/{job_id}")
    assert resp.status_code == 409
    assert db.get_job(job_id) is not None


def test_api_delete_not_found():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.delete("/api/jobs/999999")
    assert resp.status_code == 404


# ── settings_store ─────────────────────────────────────────────────────────────

def test_save_settings_persists_token():
    import app.settings_store as ss
    ss.save_settings("my_secret_token")
    s = ss.get_settings()
    assert s["qobuz_token"] == "my_secret_token"


def test_save_settings_writes_config_ini():
    import app.config as cfg
    import app.settings_store as ss
    ss.save_settings("tok123", downloads_dir="/tmp/dl", music_dir="/tmp/music")
    cfg_path = ss.qobuz_dl_config_path()
    assert cfg_path.exists()

    parser = configparser.ConfigParser()
    parser.read(cfg_path)

    assert parser["qobuz"]["auth_token"] == "tok123"
    assert parser["qobuz"]["directory"] == "/tmp/dl"
    assert parser["qobuz"]["default_quality"] == "27"
    assert parser["qobuz"]["folder_format"] == "{album_artist}/{album_title}"
    assert parser["qobuz"]["track_format"] == "{track_title}"


def test_config_ini_sets_correct_defaults():
    import app.config as cfg
    import app.settings_store as ss
    ss.save_settings("tok")
    parser = configparser.ConfigParser()
    parser.read(ss.qobuz_dl_config_path())
    assert parser["qobuz"]["default_quality"] == "27"
    assert parser["qobuz"]["directory"] == str(cfg.DOWNLOADS_DIR)


def test_get_token_returns_stored_token():
    import app.settings_store as ss
    ss.save_settings("mytoken")
    assert ss.get_token() == "mytoken"


# ── /healthz endpoint ──────────────────────────────────────────────────────────

def test_healthz():
    from fastapi.testclient import TestClient
    # Re-create a fresh app instance that uses the test config
    import app.config as cfg
    import app.db as db_mod
    db_mod.init_db(cfg.DB_FILE)

    from app.main import app
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
