"""
One-shot script to move flat FLAC files into the correct Artist/Album/ structure.

Files at depth < 3 (e.g. Artist/track.FLAC instead of Artist/Album/track.FLAC)
are moved using their embedded tags, the same way move_album works.

By default this is a dry run — pass --apply to actually move files.

Usage (inside container):
    docker exec ripuz python -m scripts.normalize_library            # dry-run
    docker exec ripuz python -m scripts.normalize_library --apply    # move files
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import config
from app.db import init_db
from app.mover import sanitize_path, _first_tag
from app.structure import find_flac_files

from mutagen.flac import FLAC

config.ensure_dirs()
init_db(config.DB_FILE)

parser = argparse.ArgumentParser(description="Normalize flat FLAC files in music library")
parser.add_argument("--apply", action="store_true", help="Actually move files (default: dry run)")
args = parser.parse_args()

DRY_RUN = not args.apply
music_root = config.MUSIC_DIR.resolve()

print(f"[normalize] music dir: {config.MUSIC_DIR}")
print(f"[normalize] mode: {'DRY RUN (pass --apply to move files)' if DRY_RUN else 'APPLY'}")

all_flacs = find_flac_files(config.MUSIC_DIR)
flat_flacs = [f for f in all_flacs if len(f.relative_to(config.MUSIC_DIR).parts) < 3]
print(f"[normalize] {len(all_flacs)} total FLAC file(s), {len(flat_flacs)} at unexpected depth")

total_moved = 0
total_skipped = 0
total_errors = 0

for src in flat_flacs:
    rel = src.relative_to(config.MUSIC_DIR)
    try:
        tags = FLAC(src)
    except Exception as exc:
        print(f"[normalize] ERROR cannot read tags: {rel} — {exc}", file=sys.stderr)
        total_errors += 1
        continue

    artist = sanitize_path(_first_tag(tags, "albumartist", "artist", default="Unknown_Artist"))
    album = sanitize_path(_first_tag(tags, "album", default="Unknown_Album"))
    title = sanitize_path(_first_tag(tags, "title", default=src.stem))

    dest = config.MUSIC_DIR / artist / album / f"{title}.FLAC"

    # Guard against crafted tags escaping the library root.
    try:
        dest.resolve().relative_to(music_root)
    except ValueError:
        print(f"[normalize] ERROR destination escapes music_dir, skipping: {rel}", file=sys.stderr)
        total_errors += 1
        continue

    if dest == src:
        print(f"[normalize] already correct: {rel}")
        total_skipped += 1
        continue

    print(f"[normalize] {'would move' if DRY_RUN else 'moving'}: {rel} → {dest.relative_to(config.MUSIC_DIR)}")

    if not DRY_RUN:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if not dest.is_file():
                print(f"[normalize] ERROR destination exists and is not a file, skipping: {dest}", file=sys.stderr)
                total_errors += 1
                continue
            dest.unlink()
        try:
            shutil.move(str(src), str(dest))
        except Exception as exc:
            print(f"[normalize] ERROR move failed: {src} → {dest}: {exc}", file=sys.stderr)
            total_errors += 1
            continue

        # Carry .lrc sidecar if present.
        for lrc_src in (src.with_suffix(".lrc"), src.with_suffix(".LRC")):
            if lrc_src.exists():
                lrc_dest = dest.with_suffix(".lrc")
                try:
                    shutil.move(str(lrc_src), str(lrc_dest))
                except Exception as exc:
                    print(f"[normalize] WARNING lrc move failed: {lrc_src}: {exc}", file=sys.stderr)
                break

    total_moved += 1

action = "would move" if DRY_RUN else "moved"
print(f"[normalize] done — {action} {total_moved} file(s), already correct {total_skipped}, errors {total_errors}")
if DRY_RUN and total_moved > 0:
    print("[normalize] re-run with --apply to move files")
