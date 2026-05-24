"""
Phase 3 tests: qobuz_cli download wrapper.
Subprocess is mocked — no actual qobuz-dl execution.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from io import StringIO

import pytest

from app.qobuz_cli import build_download_command, run_download, DownloadResult


# ── build_download_command ─────────────────────────────────────────────────────

def test_command_includes_quality_27():
    cmd = build_download_command(
        "https://play.qobuz.com/album/abc", Path("/downloads")
    )
    assert "-q" in cmd
    assert "27" in cmd


def test_command_includes_url():
    url = "https://play.qobuz.com/album/xyz123"
    cmd = build_download_command(url, Path("/downloads"))
    assert url in cmd


def test_command_includes_end_of_flags_delimiter():
    url = "https://play.qobuz.com/album/xyz123"
    cmd = build_download_command(url, Path("/downloads"))
    assert "--" in cmd
    assert cmd[cmd.index("--") + 1] == url


def test_command_includes_download_dir():
    cmd = build_download_command("https://example.com/album/1", Path("/my/music"))
    assert "-d" in cmd
    assert "/my/music" in cmd


def test_command_includes_folder_and_track_formats():
    cmd = build_download_command(
        "https://example.com/album/1",
        Path("/dl"),
        folder_format="{album_artist}/{album_title}",
        track_format="{track_title}",
    )
    assert "-ff" in cmd
    assert "{album_artist}/{album_title}" in cmd
    assert "-tf" in cmd
    assert "{track_title}" in cmd


def test_command_uses_sys_executable():
    cmd = build_download_command("https://example.com/album/1", Path("/dl"))
    assert cmd[0] == sys.executable


def test_command_includes_no_m3u_and_no_lrc():
    cmd = build_download_command("https://example.com/album/1", Path("/dl"))
    assert "--no-m3u" in cmd
    assert "--no-lrc-files" in cmd


def test_custom_quality_overrides_default():
    cmd = build_download_command("https://example.com/album/1", Path("/dl"), quality=6)
    idx = cmd.index("-q")
    assert cmd[idx + 1] == "6"


# ── run_download ───────────────────────────────────────────────────────────────

def _make_proc(returncode: int, output_lines: list[str]):
    """Build a mock subprocess.Popen that yields output_lines then exits."""
    mock_proc = MagicMock()
    mock_proc.returncode = returncode
    mock_proc.stdout = iter(line + "\n" for line in output_lines)
    mock_proc.wait.return_value = returncode
    return mock_proc


def test_successful_download(tmp_path):
    mock_proc = _make_proc(0, ["Downloading track 1/10", "Downloading track 2/10", "Done."])
    with patch("subprocess.Popen", return_value=mock_proc):
        result = run_download("https://play.qobuz.com/album/abc", downloads_dir=tmp_path)
    assert result.success is True
    assert result.error_message == ""


def test_log_callback_receives_all_lines(tmp_path):
    lines = ["Line A", "Line B", "Line C"]
    mock_proc = _make_proc(0, lines)
    captured = []
    with patch("subprocess.Popen", return_value=mock_proc):
        run_download(
            "https://play.qobuz.com/album/abc",
            downloads_dir=tmp_path,
            log_callback=lambda l: captured.append(l.rstrip()),
        )
    assert captured == lines


def test_nonzero_exit_returns_failure(tmp_path):
    mock_proc = _make_proc(1, ["Error: forbidden"])
    with patch("subprocess.Popen", return_value=mock_proc):
        result = run_download("https://play.qobuz.com/album/abc", downloads_dir=tmp_path)
    assert result.success is False
    assert "1" in result.error_message


def test_smart_resume_skip_detected(tmp_path):
    mock_proc = _make_proc(0, ["Skipping existing file track.flac"])
    with patch("subprocess.Popen", return_value=mock_proc):
        result = run_download("https://play.qobuz.com/album/abc", downloads_dir=tmp_path)
    assert result.success is True
    assert result.skipped is True


def test_subprocess_exception_returns_failure(tmp_path):
    with patch("subprocess.Popen", side_effect=FileNotFoundError("no qobuz-dl")):
        result = run_download("https://play.qobuz.com/album/abc", downloads_dir=tmp_path)
    assert result.success is False
    assert "subprocess error" in result.error_message


def test_exception_logged_via_callback(tmp_path):
    captured = []
    with patch("subprocess.Popen", side_effect=OSError("crash")):
        run_download(
            "https://play.qobuz.com/album/abc",
            downloads_dir=tmp_path,
            log_callback=captured.append,
        )
    assert any("subprocess error" in m for m in captured)


def test_lines_captured_in_result(tmp_path):
    mock_proc = _make_proc(0, ["alpha", "beta", "gamma"])
    with patch("subprocess.Popen", return_value=mock_proc):
        result = run_download("https://play.qobuz.com/album/abc", downloads_dir=tmp_path)
    assert "alpha" in result.lines
    assert "beta" in result.lines
    assert "gamma" in result.lines


def test_env_sets_xdg_config_home(tmp_path):
    import app.config as cfg
    mock_proc = _make_proc(0, [])
    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        run_download("https://play.qobuz.com/album/abc", downloads_dir=tmp_path)
    kwargs = mock_popen.call_args.kwargs
    env_passed = kwargs.get("env", {})
    assert env_passed.get("XDG_CONFIG_HOME") == str(cfg.CONFIG_DIR)
