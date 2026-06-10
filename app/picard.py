"""
Headless Picard runner.

Picard is a Qt GUI app. On a headless server we run it under xvfb-run with
the -e remote-command interface (requires Picard 2.5+, tested on 2.8+):

  xvfb-run -a picard \
    --stand-alone-instance \
    -e CLEAR \
    -e "LOAD <dir>" \
    -e CLUSTER \
    [-e "LOOKUP clustered"]   <- optional, off by default (slow network call)
    -e SAVE \
    -e "QUIT force"

--stand-alone-instance bypasses Picard's single-instance pipe mechanism so
each subprocess is fully self-contained and there are no stale FIFO issues.

LOOKUP clustered is disabled by default because it makes MusicBrainz network
calls that can stall indefinitely under rate-limiting, causing every album to
hit the timeout. Enable it explicitly with PICARD_LOOKUP=1 if you want
MusicBrainz tag enrichment and accept the latency risk.

Picard is invoked once per album directory (small batch) instead of the whole
downloads tree at once.
"""
import logging
import os
import signal
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from app import config

logger = logging.getLogger(__name__)

LogCallback = Callable[[str], None]

# 120 s default: a hung Picard fails fast and files still move with qobuz embedded tags.
# Tune via PICARD_TIMEOUT env var (seconds).
PICARD_TIMEOUT_SECONDS = int(os.getenv("PICARD_TIMEOUT", "120"))

# MusicBrainz lookup is opt-in: it makes network calls that can stall indefinitely.
# Set PICARD_LOOKUP=1 to enable (accepts latency/timeout risk).
PICARD_LOOKUP = os.getenv("PICARD_LOOKUP", "0").strip() == "1"


@dataclass
class PicardResult:
    success: bool
    error_message: str = ""
    lines: list[str] = field(default_factory=list)


def picard_executable() -> str:
    """Return the picard binary path (respects PICARD_BIN env override)."""
    return os.getenv("PICARD_BIN", "picard")


def xvfb_run_executable() -> str:
    return os.getenv("XVFB_RUN_BIN", "xvfb-run")


def build_picard_command(
    source_dir: Path,
    picard_config: Optional[Path] = None,
    lookup: Optional[bool] = None,
) -> list[str]:
    """
    Build the xvfb-run + picard command for unattended tagging of source_dir.
    --stand-alone-instance prevents any pipe/single-instance negotiation.

    lookup overrides the global PICARD_LOOKUP default for this one command:
    None = use the PICARD_LOOKUP env default, True/False = force on/off. The
    library-retag pipeline forces it on because MusicBrainz enrichment is the
    whole point of that job.
    """
    picard_bin = picard_executable()
    xvfb = xvfb_run_executable()

    if picard_config is None:
        picard_config = config.PICARD_CONFIG_FILE

    picard_args = [picard_bin, "--stand-alone-instance"]
    if picard_config.exists():
        picard_args += ["--config-file", str(picard_config)]

    picard_args += [
        "-e", "CLEAR",
        "-e", f"LOAD {source_dir}",
        "-e", "CLUSTER",
    ]
    do_lookup = PICARD_LOOKUP if lookup is None else lookup
    if do_lookup:
        picard_args += ["-e", "LOOKUP clustered"]
    picard_args += [
        "-e", "SAVE",
        "-e", "QUIT force",
    ]

    return [xvfb, "-a", "--"] + picard_args


def run_picard(
    source_dir: Path,
    picard_config: Optional[Path] = None,
    log_callback: Optional[LogCallback] = None,
    timeout: int = PICARD_TIMEOUT_SECONDS,
    lookup: Optional[bool] = None,
) -> PicardResult:
    """
    Run Picard headlessly on source_dir. Returns PicardResult.
    Picard tags files in place; moving to MUSIC_DIR is handled by app/mover.py.

    lookup overrides the global PICARD_LOOKUP default (see build_picard_command).
    """
    if not source_dir.exists():
        msg = f"source directory does not exist: {source_dir}"
        logger.error(msg)
        return PicardResult(success=False, error_message=msg)

    cmd = build_picard_command(source_dir, picard_config, lookup=lookup)
    logger.info("Running Picard: %s", " ".join(cmd))

    lines: list[str] = []

    def _log(line: str):
        lines.append(line)
        if log_callback:
            log_callback(line + "\n")

    def _kill_group(p: subprocess.Popen) -> None:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except Exception:
            p.kill()

    try:
        env = os.environ.copy()
        env["HOME"] = str(config.CONFIG_DIR)
        runtime_dir = str(config.CONFIG_DIR / "run")
        env["XDG_RUNTIME_DIR"] = runtime_dir
        os.makedirs(runtime_dir, exist_ok=True)
        # Qt warns if the runtime dir is not mode 0700
        os.chmod(runtime_dir, 0o700)

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            start_new_session=True,
        )
        try:
            stdout_data, _ = proc.communicate(timeout=timeout)
            for raw_line in stdout_data.splitlines():
                _log(raw_line)
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            proc.communicate()
            msg = f"Picard timed out after {timeout}s"
            logger.error(msg)
            _log(msg)
            return PicardResult(success=False, error_message=msg, lines=lines)

    except Exception as exc:
        msg = f"Picard subprocess error: {exc}"
        logger.error(msg)
        _log(msg)
        return PicardResult(success=False, error_message=msg, lines=lines)

    if proc.returncode != 0:
        msg = f"Picard exited with code {proc.returncode}"
        logger.warning(msg)
        return PicardResult(success=False, error_message=msg, lines=lines)

    return PicardResult(success=True, lines=lines)
