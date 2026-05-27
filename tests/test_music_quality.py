"""
Tests for the configurable music-quality setting.

Covers:
- get_quality() default
- save_settings / get_settings round-trip
- Invalid quality rejected by settings_store.save_settings and by the API
- config.ini reflects stored quality
- pipeline threads quality to run_download
- API GET/POST round-trip and validation
- build_download_command emits the correct -q flag
"""
import configparser
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi.testclient import TestClient

from app import config, db
from app.mover import MoveResult
from app.picard import PicardResult
from app.pipeline import run_track_pipeline
from app.qobuz_cli import DownloadResult, build_download_command
from app.settings_store import (
    VALID_QUALITIES,
    get_quality,
    get_settings,
    save_settings,
    qobuz_dl_config_path,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _ok_download():
    return DownloadResult(success=True)


def _ok_picard():
    return PicardResult(success=True)


def _ok_move(n: int = 1):
    return MoveResult(moved=[Path(f"/music/A/B/t{i}.FLAC") for i in range(n)])


def _one_album_dir(root: Path):
    d = root / "Artist" / "Album"
    d.mkdir(parents=True, exist_ok=True)
    return [d]


# ── VALID_QUALITIES constant ───────────────────────────────────────────────────

def test_valid_qualities_set():
    assert set(VALID_QUALITIES) == {5, 6, 7, 27}


# ── get_quality default ────────────────────────────────────────────────────────

def test_get_quality_default_is_env_value(tmp_dirs):
    # Fresh DB has no music_quality key; should fall back to config.QOBUZ_QUALITY
    assert get_quality() == config.QOBUZ_QUALITY


# ── save_settings / get_settings round-trip ───────────────────────────────────

@pytest.mark.parametrize("q", VALID_QUALITIES)
def test_save_and_get_quality(tmp_dirs, q):
    save_settings("token", quality=q)
    assert get_quality() == q
    assert get_settings()["music_quality"] == q


def test_get_settings_includes_music_quality(tmp_dirs):
    s = get_settings()
    assert "music_quality" in s
    assert s["music_quality"] == config.QOBUZ_QUALITY


# ── invalid quality ignored by save_settings ──────────────────────────────────

def test_save_settings_ignores_invalid_quality(tmp_dirs):
    save_settings("token", quality=27)
    save_settings("token", quality=99)   # invalid — should not overwrite
    assert get_quality() == 27


def test_save_settings_ignores_none_quality(tmp_dirs):
    save_settings("token", quality=6)
    save_settings("token", quality=None)  # None means "don't change"
    assert get_quality() == 6


# ── config.ini reflects stored quality ────────────────────────────────────────

@pytest.mark.parametrize("q", VALID_QUALITIES)
def test_config_ini_default_quality(tmp_dirs, q):
    save_settings("mytoken", quality=q)
    cfg_path = qobuz_dl_config_path()
    assert cfg_path.exists()
    parser = configparser.ConfigParser()
    parser.read(cfg_path)
    assert parser["qobuz"]["default_quality"] == str(q)


# ── pipeline threads quality to run_download ──────────────────────────────────

def test_pipeline_passes_quality_to_run_download(tmp_dirs):
    save_settings("token", quality=7)
    job_id = db.create_job("track", "https://play.qobuz.com/track/999")
    album_dirs = _one_album_dir(tmp_dirs / "downloads")

    with patch("app.pipeline.run_download", return_value=_ok_download()) as mock_dl, \
         patch("app.pipeline.list_album_dirs", side_effect=[[], album_dirs]), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={
             "flac_count": 1, "artists": ["A"], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        ok = run_track_pipeline(job_id, "https://play.qobuz.com/track/999")

    assert ok is True
    _, kwargs = mock_dl.call_args
    assert kwargs.get("quality") == 7


def test_pipeline_uses_default_quality_when_not_set(tmp_dirs):
    job_id = db.create_job("track", "https://play.qobuz.com/track/111")
    album_dirs = _one_album_dir(tmp_dirs / "downloads")

    with patch("app.pipeline.run_download", return_value=_ok_download()) as mock_dl, \
         patch("app.pipeline.list_album_dirs", side_effect=[[], album_dirs]), \
         patch("app.pipeline.run_picard", return_value=_ok_picard()), \
         patch("app.pipeline.move_album", return_value=_ok_move()), \
         patch("app.pipeline.verify_structure", return_value={
             "flac_count": 1, "artists": ["A"], "issues": []}), \
         patch("app.pipeline.clean_empty_dirs"):
        ok = run_track_pipeline(job_id, "https://play.qobuz.com/track/111")

    assert ok is True
    _, kwargs = mock_dl.call_args
    assert kwargs.get("quality") == config.QOBUZ_QUALITY


# ── build_download_command emits -q flag ──────────────────────────────────────

@pytest.mark.parametrize("q", VALID_QUALITIES)
def test_build_download_command_q_flag(tmp_dirs, q):
    cmd = build_download_command("https://play.qobuz.com/album/1", Path("/dl"), quality=q)
    assert "-q" in cmd
    assert cmd[cmd.index("-q") + 1] == str(q)


# ── API round-trip ─────────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_dirs):
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def test_api_get_settings_returns_music_quality(client):
    res = client.get("/api/settings")
    assert res.status_code == 200
    data = res.json()
    assert "music_quality" in data
    assert data["music_quality"] == config.QOBUZ_QUALITY


def test_api_post_persists_quality(client):
    res = client.post("/api/settings", json={
        "qobuz_token": "tok",
        "music_quality": 6,
    })
    assert res.status_code == 200
    data = client.get("/api/settings").json()
    assert data["music_quality"] == 6


def test_api_post_invalid_quality_returns_400(client):
    res = client.post("/api/settings", json={
        "qobuz_token": "tok",
        "music_quality": 99,
    })
    assert res.status_code == 400
    assert "invalid quality" in res.json().get("error", "")


def test_api_post_non_integer_quality_returns_400(client):
    res = client.post("/api/settings", json={
        "qobuz_token": "tok",
        "music_quality": "hi-res",
    })
    assert res.status_code == 400


def test_api_post_omitting_quality_leaves_existing(client):
    # Set quality to 6 first
    client.post("/api/settings", json={"qobuz_token": "tok", "music_quality": 6})
    # POST without music_quality key — should not reset it
    client.post("/api/settings", json={"qobuz_token": "tok"})
    data = client.get("/api/settings").json()
    assert data["music_quality"] == 6
