"""
Phase 4 tests: Picard headless runner.
Subprocess is mocked — no real Picard/Xvfb needed.
"""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


from app.picard import (
    build_picard_command,
    run_picard,
    PicardResult,
    picard_executable,
    xvfb_run_executable,
)


# ── build_picard_command ───────────────────────────────────────────────────────

def test_command_starts_with_xvfb(tmp_path):
    cmd = build_picard_command(tmp_path)
    assert cmd[0] == xvfb_run_executable()
    assert "-a" in cmd


def test_command_contains_picard_bin(tmp_path):
    cmd = build_picard_command(tmp_path)
    assert picard_executable() in cmd


def test_command_uses_stand_alone_instance(tmp_path):
    cmd = build_picard_command(tmp_path)
    assert "--stand-alone-instance" in cmd


def test_command_contains_clear(tmp_path):
    cmd = build_picard_command(tmp_path)
    assert "CLEAR" in cmd


def test_command_loads_source_dir(tmp_path):
    cmd = build_picard_command(tmp_path)
    assert f"LOAD {tmp_path}" in cmd


def test_command_has_cluster(tmp_path):
    cmd = build_picard_command(tmp_path)
    assert "CLUSTER" in cmd


def test_command_lookup_disabled_by_default(tmp_path):
    import app.picard as picard_mod
    old = picard_mod.PICARD_LOOKUP
    picard_mod.PICARD_LOOKUP = False
    try:
        cmd = build_picard_command(tmp_path)
        assert "LOOKUP clustered" not in cmd
    finally:
        picard_mod.PICARD_LOOKUP = old


def test_command_lookup_enabled_when_flag_set(tmp_path):
    import app.picard as picard_mod
    old = picard_mod.PICARD_LOOKUP
    picard_mod.PICARD_LOOKUP = True
    try:
        cmd = build_picard_command(tmp_path)
        assert "LOOKUP clustered" in cmd
    finally:
        picard_mod.PICARD_LOOKUP = old


def test_command_has_save(tmp_path):
    cmd = build_picard_command(tmp_path)
    assert "SAVE" in cmd


def test_command_quits_with_force(tmp_path):
    cmd = build_picard_command(tmp_path)
    assert "QUIT force" in cmd


def test_command_uses_config_file_when_exists(tmp_path):
    cfg_file = tmp_path / "Picard.ini"
    cfg_file.write_text("[General]\nversion=3.0\n")
    cmd = build_picard_command(tmp_path, picard_config=cfg_file)
    assert "--config-file" in cmd
    assert str(cfg_file) in cmd


def test_command_skips_config_file_when_missing(tmp_path):
    non_existent = tmp_path / "nope.ini"
    cmd = build_picard_command(tmp_path, picard_config=non_existent)
    assert "--config-file" not in cmd


def test_custom_picard_bin(tmp_path, monkeypatch):
    monkeypatch.setenv("PICARD_BIN", "/usr/local/bin/picard3")
    cmd = build_picard_command(tmp_path)
    assert "/usr/local/bin/picard3" in cmd


# ── run_picard ─────────────────────────────────────────────────────────────────

def _make_proc(returncode: int, output_lines: list[str]):
    mock_proc = MagicMock()
    mock_proc.returncode = returncode
    # run_picard now uses proc.communicate(timeout=...) which returns (stdout, None)
    combined = "\n".join(output_lines)
    mock_proc.communicate.return_value = (combined, None)
    mock_proc.stdout = None  # communicate drains stdout; direct iteration not used
    return mock_proc


def test_run_picard_success(tmp_path):
    mock_proc = _make_proc(0, ["Loading...", "Saving...", "Done."])
    with patch("subprocess.Popen", return_value=mock_proc):
        result = run_picard(tmp_path)
    assert result.success is True


def test_run_picard_captures_log_lines(tmp_path):
    mock_proc = _make_proc(0, ["Tagging file 1", "Tagging file 2"])
    captured = []
    with patch("subprocess.Popen", return_value=mock_proc):
        run_picard(tmp_path, log_callback=captured.append)
    assert any("Tagging file 1" in l for l in captured)
    assert any("Tagging file 2" in l for l in captured)


def test_run_picard_nonzero_exit_is_failure(tmp_path):
    mock_proc = _make_proc(1, ["Error: lookup failed"])
    with patch("subprocess.Popen", return_value=mock_proc):
        result = run_picard(tmp_path)
    assert result.success is False
    assert "1" in result.error_message


def test_run_picard_timeout(tmp_path):
    import subprocess as sp
    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = sp.TimeoutExpired(cmd="picard", timeout=1)
    with patch("subprocess.Popen", return_value=mock_proc):
        result = run_picard(tmp_path, timeout=1)
    assert result.success is False
    assert "timed out" in result.error_message


def test_run_picard_missing_source_dir(tmp_path):
    non_existent = tmp_path / "no_such_dir"
    result = run_picard(non_existent)
    assert result.success is False
    assert "does not exist" in result.error_message


def test_run_picard_subprocess_exception(tmp_path):
    with patch("subprocess.Popen", side_effect=FileNotFoundError("no picard")):
        result = run_picard(tmp_path)
    assert result.success is False
    assert "subprocess error" in result.error_message


def test_run_picard_lines_in_result(tmp_path):
    mock_proc = _make_proc(0, ["alpha", "beta"])
    with patch("subprocess.Popen", return_value=mock_proc):
        result = run_picard(tmp_path)
    assert "alpha" in result.lines
    assert "beta" in result.lines


# ── Picard.ini naming script sanity ───────────────────────────────────────────

def test_picard_ini_exists():
    ini = Path(__file__).parent.parent / "picard" / "Picard.ini"
    assert ini.exists(), "picard/Picard.ini must exist"


def test_picard_ini_has_rename_and_move_disabled():
    """Picard is tag-only; renaming/moving is handled by app/mover.py."""
    ini = Path(__file__).parent.parent / "picard" / "Picard.ini"
    content = ini.read_text()
    assert "rename_files=false" in content
    assert "move_files=false" in content


def test_picard_ini_overwrite_existing_tags():
    """Picard should enrich/overwrite tags in place."""
    ini = Path(__file__).parent.parent / "picard" / "Picard.ini"
    content = ini.read_text()
    assert "overwrite_existing_tags=true" in content


def test_picard_ini_no_script_section():
    """The broken [script] section from the original template must be gone."""
    import configparser
    ini = Path(__file__).parent.parent / "picard" / "Picard.ini"
    p = configparser.ConfigParser(interpolation=None)
    p.read(ini)
    assert "script" not in p.sections()
