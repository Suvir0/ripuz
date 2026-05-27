"""
One-shot script to move all leftover FLAC dirs from DOWNLOADS_DIR to MUSIC_DIR.

Picard is intentionally skipped — files are moved using whatever tags qobuz-dl
embedded.  Run once to clear the backlog that accumulated before the tagging-scope
fix, then let the normal pipeline handle new downloads.

Usage (inside container):
    docker exec ripuz python -m scripts.drain_downloads
"""
import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import config
from app.db import init_db
from app.mover import move_album
from app.structure import clean_empty_dirs, list_album_dirs

config.ensure_dirs()
init_db(config.DB_FILE)

dirs = list_album_dirs(config.DOWNLOADS_DIR)
print(f"[drain] {len(dirs)} album dir(s) in {config.DOWNLOADS_DIR}")

total_moved = 0
total_skipped = 0
total_errors = 0

for i, album_dir in enumerate(dirs, 1):
    print(f"[drain] ({i}/{len(dirs)}) moving: {album_dir.name}", flush=True)
    result = move_album(album_dir, config.MUSIC_DIR)
    total_moved += len(result.moved)
    total_skipped += len(result.skipped)
    total_errors += len(result.errors)
    for err in result.errors:
        print(f"[drain]   error: {err}", file=sys.stderr)

removed = clean_empty_dirs(config.DOWNLOADS_DIR)
print(f"[drain] done — moved {total_moved} file(s), skipped {total_skipped}, "
      f"errors {total_errors}, cleaned {len(removed)} empty dir(s)")
