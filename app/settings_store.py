"""
Persists application settings to the DB and renders the qobuz-dl config.ini
that qobuz-dl-ultimate reads at startup.
"""
import configparser
import os
from pathlib import Path
from typing import Optional

from app import db, config

_QOBUZ_TOKEN_KEY = "qobuz_token"
_DOWNLOADS_DIR_KEY = "downloads_dir"
_MUSIC_DIR_KEY = "music_dir"
_QUALITY_KEY = "music_quality"
_DOWNLOAD_LYRICS_KEY = "download_lyrics"
_PREFER_EXPLICIT_KEY = "prefer_explicit"
_NOTIFY_WEBHOOK_URL_KEY = "notify_webhook_url"

# All valid Qobuz quality levels accepted by qobuz-dl -q
VALID_QUALITIES = (5, 6, 7, 27)


def validate_dir_setting(value: str, allowed_root: Path) -> Optional[str]:
    """Return an error message string, or None if the path is acceptable.

    Rules: must be absolute; after resolve() must be at or inside allowed_root
    (kills ../ and symlink escapes and prevents setting arbitrary system paths);
    if the path already exists it must be a directory.
    """
    p = Path(value)
    if not p.is_absolute():
        return f"path must be absolute: {value!r}"
    try:
        resolved = p.resolve()
        root_resolved = allowed_root.resolve()
        resolved.relative_to(root_resolved)
    except ValueError:
        return f"path must be at or inside {allowed_root}: {value!r}"
    except Exception as exc:
        return f"invalid path: {exc}"
    if resolved.exists() and not resolved.is_dir():
        return f"path exists but is not a directory: {value!r}"
    return None


def get_quality() -> int:
    """Return the stored quality setting, falling back to the env default."""
    raw = db.get_setting(_QUALITY_KEY, str(config.QOBUZ_QUALITY))
    try:
        q = int(raw)
    except (ValueError, TypeError):
        return config.QOBUZ_QUALITY
    return q if q in VALID_QUALITIES else config.QOBUZ_QUALITY


def get_download_lyrics() -> bool:
    """Return whether synced .lrc lyrics download is enabled (default off)."""
    return db.get_setting(_DOWNLOAD_LYRICS_KEY, "false") == "true"


def get_prefer_explicit() -> bool:
    """Return whether the prefer-explicit toggle is on (default off)."""
    return db.get_setting(_PREFER_EXPLICIT_KEY, "false") == "true"


def save_settings(token: str, downloads_dir: str | None = None,
                  music_dir: str | None = None,
                  quality: int | None = None,
                  download_lyrics: bool | None = None,
                  prefer_explicit: bool | None = None,
                  notify_webhook_url: str | None = None) -> None:
    db.set_setting(_QOBUZ_TOKEN_KEY, token)
    if downloads_dir:
        db.set_setting(_DOWNLOADS_DIR_KEY, downloads_dir)
    if music_dir:
        db.set_setting(_MUSIC_DIR_KEY, music_dir)
    if quality is not None and quality in VALID_QUALITIES:
        db.set_setting(_QUALITY_KEY, str(quality))
    if download_lyrics is not None:
        db.set_setting(_DOWNLOAD_LYRICS_KEY, "true" if download_lyrics else "false")
    if prefer_explicit is not None:
        db.set_setting(_PREFER_EXPLICIT_KEY, "true" if prefer_explicit else "false")
    if notify_webhook_url is not None:
        db.set_setting(_NOTIFY_WEBHOOK_URL_KEY, notify_webhook_url)
    _write_qobuz_dl_config()


def get_notify_webhook_url() -> str:
    return db.get_setting(_NOTIFY_WEBHOOK_URL_KEY, "")


def get_settings() -> dict:
    return {
        "qobuz_token": db.get_setting(_QOBUZ_TOKEN_KEY, ""),
        "downloads_dir": db.get_setting(_DOWNLOADS_DIR_KEY, str(config.DOWNLOADS_DIR)),
        "music_dir": db.get_setting(_MUSIC_DIR_KEY, str(config.MUSIC_DIR)),
        "music_quality": get_quality(),
        "download_lyrics": get_download_lyrics(),
        "prefer_explicit": get_prefer_explicit(),
        "notify_webhook_url": get_notify_webhook_url(),
    }


def get_token() -> str:
    return db.get_setting(_QOBUZ_TOKEN_KEY, "")


def _write_qobuz_dl_config() -> None:
    """Write config.ini for qobuz-dl-ultimate (2026 schema) with stored settings."""
    token = db.get_setting(_QOBUZ_TOKEN_KEY, "")
    downloads = db.get_setting(_DOWNLOADS_DIR_KEY, str(config.DOWNLOADS_DIR))
    lyrics = get_download_lyrics()

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
        # Plex reads sidecar .lrc files only (not embedded tags), so when lyrics
        # are enabled we write external .lrc and skip embedding.
        "fetch_lyrics": "true" if lyrics else "false",
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
        "no_lrc_files": "false" if lyrics else "true",
        "embed_lyrics": "false",
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
    try:
        os.chmod(config.QOBUZ_DL_CONFIG_FILE, 0o600)
    except OSError:
        pass


def qobuz_dl_config_path() -> Path:
    return config.QOBUZ_DL_CONFIG_FILE
