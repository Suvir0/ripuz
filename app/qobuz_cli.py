"""
Subprocess wrapper around `python -m qobuz_dl dl`.
Streams stdout/stderr to a caller-supplied log callback and returns a result.
"""
import os
import subprocess
import sys
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from app import config

logger = logging.getLogger(__name__)

LogCallback = Callable[[str], None]


@dataclass
class DownloadResult:
    success: bool
    skipped: bool = False       # already existed, smart-resume skipped
    error_message: str = ""
    lines: list[str] = field(default_factory=list)


def build_download_command(
    url: str,
    downloads_dir: Path,
    quality: int = config.QOBUZ_QUALITY,
    folder_format: str = "{album_artist}/{album_title}",
    track_format: str = "{track_title}",
) -> list[str]:
    """Return the argv list for a qobuz-dl dl invocation."""
    return [
        sys.executable, "-m", "qobuz_dl", "dl",
        "--",   # prevent url from being parsed as a qobuz-dl flag
        url,
        "-q", str(quality),
        "-d", str(downloads_dir),
        "-ff", folder_format,
        "-tf", track_format,
        "--no-m3u",           # we don't need m3u playlists
        "--no-lrc-files",     # keep folder clean; lyrics embedded in tags
    ]


def run_download(
    url: str,
    downloads_dir: Optional[Path] = None,
    quality: int = config.QOBUZ_QUALITY,
    log_callback: Optional[LogCallback] = None,
    env_overrides: Optional[dict] = None,
) -> DownloadResult:
    """
    Run qobuz-dl dl for a single URL and stream output to log_callback.
    Returns a DownloadResult with success/skip status.
    """
    if downloads_dir is None:
        downloads_dir = config.DOWNLOADS_DIR

    cmd = build_download_command(url, downloads_dir, quality)

    env = os.environ.copy()
    # Point qobuz-dl at our config dir so it reads the right config.ini
    env["XDG_CONFIG_HOME"] = str(config.CONFIG_DIR)
    env["HOME"] = str(config.CONFIG_DIR)
    if env_overrides:
        env.update(env_overrides)

    logger.info("Running: %s", " ".join(cmd))

    lines: list[str] = []
    skipped = False

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = raw_line.rstrip("\n")
            lines.append(line)
            if log_callback:
                log_callback(line + "\n")
            if "[DONE]" in line or "Skipping" in line or "already exists" in line.lower():
                skipped = True

        proc.wait()
        success = proc.returncode == 0
    except Exception as exc:
        error_msg = f"subprocess error: {exc}"
        logger.error(error_msg)
        if log_callback:
            log_callback(error_msg + "\n")
        return DownloadResult(success=False, error_message=error_msg, lines=lines)

    if not success:
        error_msg = f"qobuz-dl exited with code {proc.returncode}"
        logger.warning(error_msg)
        return DownloadResult(
            success=False, error_message=error_msg, lines=lines
        )

    return DownloadResult(success=True, skipped=skipped, lines=lines)
