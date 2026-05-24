"""
Persists application settings to the DB and renders the qobuz-dl config.ini
that qobuz-dl-ultimate reads at startup.
"""
import configparser
from pathlib import Path

from app import db, config

_QOBUZ_TOKEN_KEY = "qobuz_token"
_DOWNLOADS_DIR_KEY = "downloads_dir"
_MUSIC_DIR_KEY = "music_dir"
_QUALITY_KEY = "music_quality"

# All valid Qobuz quality levels accepted by qobuz-dl -q
VALID_QUALITIES = (5, 6, 7, 27)


def get_quality() -> int:
    """Return the stored quality setting, falling back to the env default."""
    raw = db.get_setting(_QUALITY_KEY, str(config.QOBUZ_QUALITY))
    try:
        q = int(raw)
    except (ValueError, TypeError):
        return config.QOBUZ_QUALITY
    return q if q in VALID_QUALITIES else config.QOBUZ_QUALITY


def save_settings(token: str, downloads_dir: str | None = None,
                  music_dir: str | None = None,
                  quality: int | None = None) -> None:
    db.set_setting(_QOBUZ_TOKEN_KEY, token)
    if downloads_dir:
        db.set_setting(_DOWNLOADS_DIR_KEY, downloads_dir)
    if music_dir:
        db.set_setting(_MUSIC_DIR_KEY, music_dir)
    if quality is not None and quality in VALID_QUALITIES:
        db.set_setting(_QUALITY_KEY, str(quality))
    _write_qobuz_dl_config()


def get_settings() -> dict:
    return {
        "qobuz_token": db.get_setting(_QOBUZ_TOKEN_KEY, ""),
        "downloads_dir": db.get_setting(_DOWNLOADS_DIR_KEY, str(config.DOWNLOADS_DIR)),
        "music_dir": db.get_setting(_MUSIC_DIR_KEY, str(config.MUSIC_DIR)),
        "music_quality": get_quality(),
    }


def get_token() -> str:
    return db.get_setting(_QOBUZ_TOKEN_KEY, "")


def _write_qobuz_dl_config() -> None:
    """Write config.ini for qobuz-dl-ultimate (2026 schema) with stored settings."""
    token = db.get_setting(_QOBUZ_TOKEN_KEY, "")
    downloads = db.get_setting(_DOWNLOADS_DIR_KEY, str(config.DOWNLOADS_DIR))

    # Fetch app_id + secrets dynamically from Qobuz (same as qobuz-dl wizard does)
    app_id = ""
    secrets = ""
    try:
        from qobuz_dl.bundle import Bundle
        bundle = Bundle()
        app_id = str(bundle.get_app_id())
        secrets = ",".join(bundle.get_secrets().values())
    except Exception:
        pass

    cfg = configparser.ConfigParser(interpolation=None)
    cfg["qobuz"] = {
        "email": "",
        "password": "",
        # 2026 schema: auth token key is auth_token, not token
        "auth_token": token,
        "fetch_lyrics": "false",
        "genius_token": "",
        "directory": downloads,
        "folder_format": "{album_artist}/{album_title}",
        "default_quality": str(get_quality()),
        "default_limit": "500",
        "no_m3u": "true",
        "albums_only": "false",
        "no_fallback": "false",
        "og_cover": "true",
        "embed_art": "true",
        "no_cover": "false",
        "no_database": "false",
        "no_lrc_files": "true",
        "embed_lyrics": "true",
        "multi_value_tags": "false",
        "legacy_charmap": "false",
        "blacklist": "blacklist.txt",
        "app_id": app_id,
        "secrets": secrets,
        "track_format": "{track_title}",
        "fallback_folder_format": "{artist} - {album}",
        "smart_discography": "false",
        "no_album_artist_tag": "false",
        "no_album_title_tag": "false",
        "no_track_artist_tag": "false",
        "no_track_title_tag": "false",
        "no_release_date_tag": "false",
        "no_media_type_tag": "false",
        "no_genre_tag": "false",
        "no_track_number_tag": "false",
        "no_track_total_tag": "false",
        "no_disc_number_tag": "false",
        "no_disc_total_tag": "false",
        "no_composer_tag": "false",
        "no_explicit_tag": "false",
        "no_copyright_tag": "false",
        "no_label_tag": "false",
        "no_credits": "false",
        "no_upc_tag": "false",
        "no_isrc_tag": "false",
        "embedded_art_size": "600",
        "saved_art_size": "org",
        "multiple_disc_prefix": "CD",
        "multiple_disc_one_dir": "false",
        "multiple_disc_track_format": "{disc_number}.{track_number} - {track_title}",
        "max_workers": "3",
        "user_auth_token": "",
    }

    config.QOBUZ_DL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.QOBUZ_DL_CONFIG_FILE, "w") as f:
        cfg.write(f)


def qobuz_dl_config_path() -> Path:
    return config.QOBUZ_DL_CONFIG_FILE
