"""
Verify and enforce Artist/Album/song.FLAC structure in the music directory.
Also cleans up empty directories left behind by Picard.
"""
import shutil
from pathlib import Path

from app.mover import sanitize_path


def find_flac_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.flac")) + sorted(root.rglob("*.FLAC"))


def list_album_dirs(root: Path) -> list[Path]:
    """
    Return all leaf directories under root that contain at least one FLAC file.
    Used to split a downloads tree into per-album batches for Picard.
    """
    seen: set[Path] = set()
    dirs: list[Path] = []
    for f in find_flac_files(root):
        d = f.parent
        if d not in seen:
            seen.add(d)
            dirs.append(d)
    return sorted(dirs)


def clean_empty_dirs(root: Path) -> list[Path]:
    """Remove empty leaf directories under root, bottom-up. Returns removed paths."""
    removed = []
    for dirpath in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if dirpath.is_dir():
            try:
                dirpath.rmdir()  # only succeeds if empty
                removed.append(dirpath)
            except OSError:
                pass
    return removed


def album_already_present(
    music_dir: Path,
    artist: str,
    album: str,
    expected_tracks: int | None = None,
) -> bool:
    """
    Return True if the album appears to already exist in music_dir.
    Uses the same sanitization as move_album so the path matches what was written.
    When expected_tracks is given, also requires that many FLAC files be present.
    """
    if not artist or not album:
        return False
    album_dir = music_dir / sanitize_path(artist) / sanitize_path(album)
    if not album_dir.is_dir():
        return False
    flacs = find_flac_files(album_dir)
    if not flacs:
        return False
    if expected_tracks and len(flacs) < expected_tracks:
        return False
    return True


def verify_structure(music_dir: Path, min_flac: int = 0) -> dict:
    """
    Walk music_dir and return a dict of stats.
    Returns: {flac_count, artists, issues}
    """
    flacs = find_flac_files(music_dir)
    artists: set[str] = set()
    issues: list[str] = []

    for f in flacs:
        rel = f.relative_to(music_dir)
        parts = rel.parts
        if len(parts) < 3:
            issues.append(f"unexpected depth ({len(parts)} parts): {rel}")
        else:
            artists.add(parts[0])

    if len(flacs) < min_flac:
        issues.append(f"expected at least {min_flac} FLAC files, found {len(flacs)}")

    return {"flac_count": len(flacs), "artists": sorted(artists), "issues": issues}
