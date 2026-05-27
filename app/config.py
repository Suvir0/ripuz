"""
Environment-driven paths and settings.
All paths come from environment variables with sensible defaults for local dev.
"""
import os
from pathlib import Path

CONFIG_DIR = Path(os.getenv("CONFIG_DIR", "/config"))
DOWNLOADS_DIR = Path(os.getenv("DOWNLOADS_DIR", "/downloads"))
MUSIC_DIR = Path(os.getenv("MUSIC_DIR", "/music"))

QOBUZ_DL_CONFIG_DIR = CONFIG_DIR / ".config" / "qobuz-dl"
QOBUZ_DL_CONFIG_FILE = QOBUZ_DL_CONFIG_DIR / "config.ini"
PICARD_CONFIG_FILE = CONFIG_DIR / "picard" / "Picard.ini"
DB_FILE = CONFIG_DIR / "ripuz.db"

APP_PORT = int(os.getenv("APP_PORT", "8080"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

# Qobuz quality: 5=MP3, 6=FLAC 16/44, 7=FLAC 24/96, 27=FLAC 24/192 (max)
QOBUZ_QUALITY = int(os.getenv("QOBUZ_QUALITY", "27"))

# Disk safety guard: abort a bulk download if free space on DOWNLOADS_DIR drops below this.
DISK_FLOOR_GB = float(os.getenv("DISK_FLOOR_GB", "20"))

# Cap on total albums a single bulk job will download (prevents runaway on large catalogs).
MAX_ALBUMS_PER_JOB = int(os.getenv("MAX_ALBUMS_PER_JOB", "300"))

# expand_discographies: minimum tracks an artist must appear as *album artist* in a playlist
# before their full catalog is resolved. Default 2 filters out one-off featured artists.
# Set to 1 to expand every artist in the playlist (original behaviour).
EXPAND_MIN_ARTIST_TRACKS = int(os.getenv("EXPAND_MIN_ARTIST_TRACKS", "2"))

# expand_discographies: pipe-separated regex patterns matched (case-insensitive) against
# "<album_artist> <album_title>". Albums matching any pattern are excluded from the plan.
# Override with EXPAND_JUNK_PATTERNS env var (empty string = disable filter).
_DEFAULT_JUNK = (
    r"karaoke|tribute|originally performed by|made famous by"
    r"|hypertechno|hardstyle|nightcore|turborave"
    r"|slowed.*reverb|sped.up.*reverb|lofi|lo.fi|tabata"
)
EXPAND_JUNK_PATTERNS = os.getenv("EXPAND_JUNK_PATTERNS", _DEFAULT_JUNK)

# Build identity: 7-char git SHA injected at image build time via --build-arg GIT_SHA.
# Falls back to "dev" for local runs without a build arg.
APP_VERSION = os.getenv("GIT_SHA", "dev")[:7]

# Optional HTTP Basic Auth — leave RIPUZ_AUTH_PASS empty to disable (default).
RIPUZ_AUTH_USER = os.getenv("RIPUZ_AUTH_USER", "ripuz")
RIPUZ_AUTH_PASS = os.getenv("RIPUZ_AUTH_PASS", "")


def ensure_dirs() -> None:
    for d in (CONFIG_DIR, DOWNLOADS_DIR, MUSIC_DIR, QOBUZ_DL_CONFIG_DIR,
              PICARD_CONFIG_FILE.parent):
        d.mkdir(parents=True, exist_ok=True)
