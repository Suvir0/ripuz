# Ripuz

> **Name:** "Ripuz" is a play on Qobuz — ripping music from a service that ends in *uz*.

Self-hosted Qobuz → MusicBrainz Picard music downloader for UNRAID (and any Linux Docker host).

Downloads your Qobuz library at a **configurable quality** (MP3 320 → FLAC 24-bit/192kHz), enriches tags with MusicBrainz Picard headlessly, and organises files into your music library as `Artist/Album/Title.FLAC`.

---

## Features

| Mode | What it does |
|---|---|
| **Track** | Download a single Qobuz track |
| **Album** | Download a single Qobuz album |
| **Playlist** | Download every track in a Qobuz playlist |
| **Discography** | Download an artist's full catalog from a Qobuz artist URL |
| **Expand to albums** | Resolve each track in a playlist to its full album, then download every album |
| **Expand discographies** | Resolve each artist in a playlist to their full catalog, then download everything |
| **Explicit upgrade** | Replace clean tracks with their explicit versions — from a playlist or by scanning your entire `/music` library |
| **Retag library** | Scan your entire `/music` library for FLACs that are untagged or were never matched by MusicBrainz Picard, and (re-)tag them in place with Picard |

**All bulk modes** (Discography, Expand, Explicit upgrade) are **two-phase**: Ripuz first resolves the full album list, shows you a plan with an estimated download size, and waits for your confirmation before downloading anything. You can cancel at any time.

**Additional capabilities:**
- Per-album Picard tagging (MusicBrainz lookup, headless under Xvfb)
- Whole-library retag pass: finds files missing core tags or a MusicBrainz id and tags them in place (MusicBrainz lookup is forced on for this pass)
- Configurable quality tier via the Settings UI
- Optional synced `.lrc` lyrics download (Plex sidecar format)
- Optional prefer-explicit toggle for playlist downloads
- Disk-space floor guard — aborts a bulk job before the drive fills up
- Cross-job deduplication — two concurrent bulk jobs never download the same album twice
- HTTP Basic Auth (optional) for remote access

---

## Getting your Qobuz auth token

Qobuz no longer allows third-party password login. Extract your browser session token:

1. Log in at **[play.qobuz.com](https://play.qobuz.com)**
2. Press `F12` → **Application** tab → **Local Storage** → `https://play.qobuz.com`
3. Find the **`localuser`** key and copy the **`token`** string from the JSON value.
4. Paste it in Ripuz **Settings**.

---

## Quick start (Docker)

```bash
docker run -d --name ripuz --restart unless-stopped \
  -p 8080:8080 \
  -v /mnt/user/appdata/ripuz/config:/config \
  -v /mnt/user/appdata/ripuz/downloads:/downloads \
  -v /mnt/user/data/media/music:/music \
  -e PUID=99 -e PGID=100 -e UMASK=022 \
  suvirp/ripuz:latest
```

Then open **http://your-server-ip:8080**.

The image is published to **Docker Hub** (`suvirp/ripuz`) and **GitHub Container Registry** (`ghcr.io/Suvir0/ripuz`) on every push to `main`.

---

## UNRAID deployment

### Option A — Docker Compose

```bash
git clone https://github.com/Suvir0/ripuz.git
cd ripuz
docker compose up -d
```

### Option B — UNRAID Community Apps

Use the included `ripuz.xml` template. Edit the volume paths:

| Container path | Suggested host path | Purpose |
|---|---|---|
| `/config` | `/mnt/user/appdata/ripuz/config` | DB, qobuz-dl config, Picard.ini |
| `/downloads` | `/mnt/user/appdata/ripuz/downloads` | Scratch space (fast drive recommended) |
| `/music` | `/mnt/user/data/media/music` | Your Plex/Roon music library root |

Set `PUID` and `PGID` to match your UNRAID `nobody`/`users` (default `99`/`100`).

### Build locally

```bash
docker build -t ripuz .
```

### Update on the server

```bash
docker pull suvirp/ripuz:latest && \
docker rm -f ripuz && \
docker run -d --name ripuz --restart unless-stopped \
  -p 9999:8080 \
  -v /mnt/user/appdata/ripuz/config:/config \
  -v /mnt/user/data/misc:/downloads \
  -v /mnt/user/data/media/music:/music \
  -e PUID=99 -e PGID=100 -e UMASK=022 \
  -e CONFIG_DIR=/config -e DOWNLOADS_DIR=/downloads \
  -e MUSIC_DIR=/music -e APP_PORT=8080 -e LOG_LEVEL=info \
  suvirp/ripuz:latest
```

---

## Usage walkthrough

1. **Settings** — paste your Qobuz token, set music quality and optional toggles.
2. **Add download** — pick a mode, paste a Qobuz URL (or enable "scan my /music library" for Explicit upgrade).
3. **Bulk jobs** — after resolving, Ripuz shows you a plan:
   - Number of albums to download, estimated GB, albums already present or claimed by another job.
   - Click **Confirm** to start downloading, or **Cancel** to discard.
4. **Jobs tab** — watch live log output per job; cancel or delete finished jobs.
5. **Result** — files land in `MUSIC_DIR/<Artist>/<Album>/<Title>.FLAC`.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PUID` | `99` | User ID the app runs as (UNRAID `nobody`) |
| `PGID` | `100` | Group ID (UNRAID `users`) |
| `UMASK` | `022` | File permissions mask |
| `CONFIG_DIR` | `/config` | Config + SQLite DB directory |
| `DOWNLOADS_DIR` | `/downloads` | Scratch download directory |
| `MUSIC_DIR` | `/music` | Final music library root |
| `APP_PORT` | `8080` | WebUI listening port |
| `LOG_LEVEL` | `info` | Python log level (`debug`, `info`, `warning`, `error`) |
| `QOBUZ_QUALITY` | `27` | Startup default quality tier (overridden by Settings UI once saved) |
| `PICARD_TIMEOUT` | `120` | Seconds before a Picard run is killed per album |
| `PICARD_BIN` | `picard` | Override the Picard binary path |
| `DISK_FLOOR_GB` | `20` | Abort a bulk download if free space on `DOWNLOADS_DIR` drops below this |
| `MAX_ALBUMS_PER_JOB` | `300` | Cap on albums a single bulk job will download |
| `EXPAND_MIN_ARTIST_TRACKS` | `2` | Min tracks an artist must appear on in a playlist before their full catalog is resolved |
| `EXPAND_JUNK_PATTERNS` | _(karaoke / tribute / …)_ | Pipe-separated regex patterns; matching albums are excluded from expand plans |
| `RIPUZ_AUTH_USER` | `ripuz` | Basic Auth username (only used when `RIPUZ_AUTH_PASS` is set) |
| `RIPUZ_AUTH_PASS` | _(empty)_ | Set to enable HTTP Basic Auth; leave empty to disable |
| `CHOWN_MUSIC_RECURSIVE` | `0` | Set to `1` to `chown` `/music` recursively on startup |
| `GIT_SHA` | `dev` | Injected at build time; displayed as the version in the UI |

### Quality tiers

| Value | Format |
|---|---|
| `5` | MP3 320 kbps |
| `6` | FLAC 16-bit / 44.1 kHz (CD quality) |
| `7` | FLAC 24-bit / 96 kHz (hi-res) |
| `27` | FLAC 24-bit / 192 kHz (max) |

### Settings UI keys

The following settings are persisted in the DB and configurable via the **Settings** tab:

| Setting | Description |
|---|---|
| `qobuz_token` | Your Qobuz session token |
| `downloads_dir` | Override the scratch download path at runtime |
| `music_dir` | Override the music library path at runtime |
| `music_quality` | Quality tier (5 / 6 / 7 / 27) |
| `download_lyrics` | Download synced `.lrc` lyrics sidecars (Plex-compatible) |
| `prefer_explicit` | Prefer explicit versions when downloading playlists |

---

## Architecture

```
HTTP request
    │
    ▼
app/main.py          FastAPI app + lifespan + REST API (/api/jobs, /api/settings, /healthz)
    │
    ▼
app/jobs.py          SQLite job queue + single background worker thread
    │
    ▼
app/pipeline.py      Orchestration: download → tag → move → verify → cleanup
    ├── app/qobuz_client.py   Qobuz API: playlist/artist/album/track resolution, explicit matching
    ├── app/qobuz_cli.py      Subprocess wrapper for `python -m qobuz_dl dl`
    ├── app/picard.py         Headless Picard runner (xvfb-run, per-album, best-effort)
    ├── app/mover.py          Read mutagen tags, move files to Artist/Album/Title.FLAC
    └── app/structure.py      FLAC discovery, album-dir listing, empty-dir cleanup, verify

app/db.py            SQLite schema: jobs, settings, album_cache; stale-job purge; cross-job dedup
app/settings_store.py  Persist settings to DB; render qobuz-dl config.ini
app/config.py        Env-driven paths and constants
```

**Bulk job lifecycle:**

```
queued → resolving → awaiting_confirm → (user clicks Confirm) → confirmed
       → downloading → tagging → verifying → done / done_with_warnings / error
```

Simple jobs (track, album, playlist) skip the resolve/confirm phases.

---

## Project structure

```
app/
  main.py             FastAPI app + API routes
  config.py           Env-driven paths and constants
  db.py               SQLite: jobs, settings, album_cache
  settings_store.py   Persist settings + render qobuz-dl config.ini
  qobuz_client.py     Qobuz API resolution and explicit-match logic
  qobuz_cli.py        Subprocess wrapper for qobuz-dl
  picard.py           Headless Picard runner (xvfb-run + remote commands)
  pipeline.py         Orchestrate download → tag → move → verify → cleanup
  jobs.py             SQLite job queue + background worker thread
  mover.py            FLAC tag reader + file mover (Artist/Album/Title.FLAC)
  structure.py        FLAC discovery, album-dir listing, structure verification
  explicit.py         Fuzzy matching to find explicit twins of clean tracks/albums
  static/             index.html, app.js, style.css
picard/
  Picard.ini          Picard config template (tag-only; rename/move handled by mover.py)
scripts/
  drain_downloads.py  One-shot: move all pending downloads into the library (no re-tag)
  normalize_library.py  Relocate flat FLACs into Artist/Album/Title structure from tags
tests/                329 unit tests, all mocked (no real Qobuz account or Picard needed)
Dockerfile            python:3.12-slim + Picard + Xvfb + ffmpeg + gosu
entrypoint.sh         PUID/PGID/UMASK drop-privileges + Picard.ini path injection
docker-compose.yml    Local dev / UNRAID reference
ripuz.xml             UNRAID Community-Apps template
```

---

## Running tests

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -v
```

No real Qobuz account, Picard installation, or Docker is required — all external calls are mocked.

---

## Security

Ripuz ships with **no authentication enabled** by default for trusted-LAN homelab use.

- To enable **HTTP Basic Auth**, set `RIPUZ_AUTH_PASS` (and optionally `RIPUZ_AUTH_USER`).
- Do **not** expose port `8080` to untrusted networks; use a reverse proxy, VPN, or firewall.
- For stricter local file permissions on config/DB files, set `UMASK=077`.
- The `/healthz` endpoint is always accessible without credentials (for container health checks).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Job status `done_with_warnings` | Some albums were geo-blocked, unavailable, or failed to move | Check the job log; re-run failed albums individually |
| Job status `error` after 12 h | Stale-job purge triggered (no status change for 12 h) | Restart the container; increase `PICARD_TIMEOUT` if Picard is hanging |
| Picard times out | Large album or slow MusicBrainz lookup | Increase `PICARD_TIMEOUT` (default `120`); files are still moved using embedded tags |
| Bulk job aborted mid-way | Disk floor guard triggered | Free space on `DOWNLOADS_DIR`; adjust `DISK_FLOOR_GB` |
| Explicit upgrade finds no matches | Clean track has a different album artist or duration | Check the job log — no-match tracks are reported; use playlist mode instead of library |
| UI shows version `dev` | No `GIT_SHA` build arg was passed | Only affects the displayed version string; not functional |

---

## Legal / disclaimer

Ripuz orchestrates downloads using **your own Qobuz subscription** via the official authenticated API. No music is bundled or distributed with this software. Use for personal archival purposes only; this may violate Qobuz's Terms of Service. You are responsible for compliance with applicable laws and terms in your jurisdiction.

---

## Notice

See [CREDITS.md](CREDITS.md) for third-party attribution and licenses.
