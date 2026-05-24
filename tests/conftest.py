"""
Shared pytest fixtures.
"""
import os
import tempfile
from pathlib import Path

import pytest

# Point all path config at a temp dir so tests never touch real filesystem
@pytest.fixture(autouse=True)
def tmp_dirs(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    downloads_dir = tmp_path / "downloads"
    music_dir = tmp_path / "music"
    for d in (config_dir, downloads_dir, music_dir):
        d.mkdir()

    monkeypatch.setenv("CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("DOWNLOADS_DIR", str(downloads_dir))
    monkeypatch.setenv("MUSIC_DIR", str(music_dir))

    # Re-import config so module-level Path() calls pick up new env
    import importlib
    import app.config as cfg
    importlib.reload(cfg)

    import app.db as dbmod
    importlib.reload(dbmod)

    import app.settings_store as ss
    importlib.reload(ss)

    cfg.ensure_dirs()
    dbmod.init_db(cfg.DB_FILE)

    yield tmp_path
