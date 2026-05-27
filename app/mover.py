"""
Move tagged FLAC files from a download directory into the music library.

After Picard tags files in place the mover reads each file's embedded tags
(via mutagen) and places it at:

    MUSIC_DIR/<albumartist or artist>/<album>/<title>.FLAC

If a tag is missing we fall back to safe defaults so no file is ever silently
dropped. Spaces and path-unsafe characters are replaced with underscores.
"""
import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from mutagen.flac import FLAC

logger = logging.getLogger(__name__)

_UNSAFE_RE = re.compile(r'[/\\<>:"|?*\x00-\x1f]')


def sanitize_path(name: str) -> str:
    """Replace path-unsafe chars and spaces with underscores."""
    name = _UNSAFE_RE.sub("_", name)
    name = name.replace(" ", "_")
    name = re.sub(r"_+", "_", name)
    name = name.strip("_") or "_"
    if name in (".", ".."):
        return "_"
    return name


_sanitize = sanitize_path  # internal alias


def _first_tag(tags: FLAC, *keys: str, default: str = "") -> str:
    for key in keys:
        val = tags.get(key)
        if val:
            return str(val[0])
    return default


@dataclass
class MoveResult:
    moved: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def move_album(album_dir: Path, music_dir: Path) -> MoveResult:
    """
    Read FLAC tags from every .flac/.FLAC file under album_dir and move each
    one to music_dir/<artist>/<album>/<title>.FLAC.

    Files that cannot be read are skipped (not moved) and logged.
    """
    result = MoveResult()

    flacs = sorted(album_dir.rglob("*.flac")) + sorted(album_dir.rglob("*.FLAC"))
    if not flacs:
        logger.debug("move_album: no FLAC files found in %s", album_dir)
        return result

    music_root = music_dir.resolve()

    for src in flacs:
        try:
            tags = FLAC(src)
        except Exception as exc:
            msg = f"cannot read tags from {src}: {exc}"
            logger.warning(msg)
            result.errors.append(msg)
            result.skipped.append(src)
            continue

        artist = _sanitize(
            _first_tag(tags, "albumartist", "artist", default="Unknown_Artist")
        )
        album = _sanitize(_first_tag(tags, "album", default="Unknown_Album"))
        title = _sanitize(_first_tag(tags, "title", default=src.stem))

        dest = music_dir / artist / album / f"{title}.FLAC"

        # Guard: ensure dest stays within music_dir (crafted tags could escape)
        try:
            dest.resolve().relative_to(music_root)
        except ValueError:
            msg = f"destination escapes music_dir, skipping: {dest}"
            logger.error(msg)
            result.errors.append(msg)
            result.skipped.append(src)
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.exists():
            if not dest.is_file():
                msg = f"destination exists but is not a regular file, skipping: {dest}"
                logger.error(msg)
                result.errors.append(msg)
                result.skipped.append(src)
                continue
            logger.debug("move_album: destination exists, overwriting: %s", dest)
            dest.unlink()

        try:
            shutil.move(str(src), str(dest))
            logger.debug("move_album: %s → %s", src, dest)
            result.moved.append(dest)
        except Exception as exc:
            msg = f"failed to move {src} → {dest}: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            result.skipped.append(src)
            continue

        # Carry the sidecar .lrc lyrics file (if any) so its stem matches the
        # moved FLAC exactly — Plex reads sidecars named identically to the track.
        for lrc_src in (src.with_suffix(".lrc"), src.with_suffix(".LRC")):
            if lrc_src.exists():
                lrc_dest = dest.with_suffix(".lrc")
                try:
                    shutil.move(str(lrc_src), str(lrc_dest))
                    logger.debug("move_album: %s → %s", lrc_src, lrc_dest)
                except Exception as exc:
                    msg = f"failed to move lyrics {lrc_src} → {lrc_dest}: {exc}"
                    logger.warning(msg)
                    result.errors.append(msg)
                break

    return result
