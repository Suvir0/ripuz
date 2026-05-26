"""
Subprocess wrapper around `python -m qobuz_dl dl`.
Streams stdout/stderr to a caller-supplied log callback and returns a result.
Supports cooperative cancellation via cancel_check and subprocess termination.
Tqdm/progress spam is dropped before logging to avoid O(n²) DB write amplification.
"""
import os
import re
import subprocess
import sys
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from app import config

logger = logging.getLogger(__name__)

LogCallback = Callable[[str], None]

# Module-level registry of running subprocesses, keyed by job_id.
_procs: dict[int, subprocess.Popen] = {}
_procs_lock = threading.Lock()

# Matches tqdm progress lines and carriage-return overwrites.
_PROGRESS_RE = re.compile(r"Downloading:\s+\d+%\||\r")

# Maximum lines to retain in the in-memory lines list per run.
_MAX_LINES = 500


@dataclass
class DownloadResult:
    success: bool
    skipped: bool = False
    cancelled: bool = False
    error_message: str = ""
    lines: list[str] = field(default_factory=list)


def terminate_job(job_id: int) -> None:
    """Terminate the subprocess registered for job_id, if any."""
    with _procs_lock:
        proc = _procs.get(job_id)
    if proc is None:
        return
    try:
        proc.terminate()
    except Exception:
        pass


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
        "--no-m3u",
        "--no-lrc-files",
    ]


def run_download(
    url: str,
    downloads_dir: Optional[Path] = None,
    quality: int = config.QOBUZ_QUALITY,
    log_callback: Optional[LogCallback] = None,
    env_overrides: Optional[dict] = None,
    job_id: Optional[int] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> DownloadResult:
    """
    Run qobuz-dl dl for a single URL and stream output to log_callback.
    Returns a DownloadResult with success/skip/cancel status.

    cancel_check: zero-arg callable returning True when the job has been cancelled.
    job_id: when provided, the Popen is registered so terminate_job() can kill it.
    """
    if downloads_dir is None:
        downloads_dir = config.DOWNLOADS_DIR
    if cancel_check is None:
        cancel_check = lambda: False

    cmd = build_download_command(url, downloads_dir, quality)

    env = os.environ.copy()
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
        if job_id is not None:
            with _procs_lock:
                _procs[job_id] = proc

        assert proc.stdout is not None
        for raw_line in proc.stdout:
            if cancel_check():
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return DownloadResult(success=False, cancelled=True, lines=lines)

            line = raw_line.rstrip("\n")

            # Drop tqdm progress spam — contains \r or matches "Downloading: N%|"
            if "\r" in line or _PROGRESS_RE.search(line):
                continue

            if len(lines) >= _MAX_LINES:
                lines = lines[_MAX_LINES // 2:]  # keep the tail
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

    finally:
        if job_id is not None:
            with _procs_lock:
                _procs.pop(job_id, None)

    if cancel_check():
        return DownloadResult(success=False, cancelled=True, lines=lines)

    if not success:
        error_msg = f"qobuz-dl exited with code {proc.returncode}"
        logger.warning(error_msg)
        return DownloadResult(success=False, error_message=error_msg, lines=lines)

    return DownloadResult(success=True, skipped=skipped, lines=lines)
