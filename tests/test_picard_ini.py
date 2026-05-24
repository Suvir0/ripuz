"""
Validate the picard/Picard.ini template against Picard 2.x requirements.
"""
import configparser
from pathlib import Path

_INI = Path(__file__).parent.parent / "picard" / "Picard.ini"


def _parser() -> configparser.ConfigParser:
    p = configparser.ConfigParser(interpolation=None)
    p.read(_INI)
    return p


def test_ini_file_exists():
    assert _INI.exists(), "picard/Picard.ini must exist"


def test_ini_rename_files_false():
    p = _parser()
    assert p["setting"]["rename_files"] == "false"


def test_ini_move_files_false():
    p = _parser()
    assert p["setting"]["move_files"] == "false"


def test_ini_no_broken_script_section():
    p = _parser()
    assert "script" not in p.sections(), \
        "broken [script] section should not exist in Picard.ini"


def test_ini_overwrite_existing_tags():
    p = _parser()
    assert p["setting"]["overwrite_existing_tags"] == "true"


def test_ini_no_music_dir_placeholder():
    content = _INI.read_text()
    assert "__MUSIC_DIR__" not in content, \
        "__MUSIC_DIR__ placeholder must not appear in committed Picard.ini"


def test_ini_has_general_section():
    p = _parser()
    assert "General" in p or "general" in [s.lower() for s in p.sections()]
