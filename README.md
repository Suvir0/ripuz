# Ripuz

> **Name:** "Ripuz" is a play on Qobuz — ripping music from a service that ends in *uz*.

Self-hosted Qobuz → MusicBrainz Picard music downloader for UNRAID.

> **Built with AI assistance:** This project was developed with the help of Claude (Anthropic).

Downloads playlists at a **configurable quality** (MP3 320 → FLAC 24-bit/192kHz), tags with Picard, and files tracks into your library as `Artist/Album/Song.FLAC`.

## What it does

1. You paste a Qobuz playlist URL into the WebUI.
2. **Download playlist** — grabs every track at your chosen quality tier (settable in **Settings**).
3. **Expand to full albums** — for each track, finds the album it belongs to via the Qobuz API, deduplicates, then downloads every complete album.
4. Picard runs headlessly (under Xvfb) to tag and move files to your music library as `Artist/Album/Title.FLAC`.

## Getting your Qobuz auth token

Qobuz no longer allows third-party password login. You need your browser auth token:

1. Log in at **[play.qobuz.com](https://play.qobuz.com)**
2. Press `F12` → **Application** tab → **Local Storage** → `https://play.qobuz.com`
3. Find the **`localuser`** key and copy the **`token`** string from the JSON value.
4. Paste it in Ripuz **Settings**.

## Quick start (Docker)

```bash
docker run -d --name ripuz --restart unless-stopped \
  -p 8080:8080 \
  -v /mnt/user/appdata/ripuz/config:/config \
  -v /mnt/user/appdata/ripuz/downloads:/downloads \
  -v /mnt/user/Music:/music \
  -e PUID=99 -e PGID=100 -e UMASK=022 \
  ghcr.io/Suvir0/ripuz:latest
```

Then open **http://your-server-ip:8080**.

## UNRAID deployment

### Option A — Docker Compose (recommended for testing)

```bash
git clone https://github.com/Suvir0/ripuz.git
cd ripuz
docker compose up -d
```

Then open **http://your-server-ip:8080**.

### Option B — UNRAID Community Apps

Use the included `ripuz.xml` template. Edit paths:

| Path | Default | Notes |
|---|---|---|
| `/config` | `/mnt/user/appdata/ripuz/config` | DB, qobuz-dl config, Picard.ini |
| `/downloads` | `/mnt/user/appdata/ripuz/downloads` | Scratch (fast drive recommended) |
| `/music` | `/mnt/user/Music` | **Your Plex/Roon music library root** |

Set `PUID` and `PGID` to match your UNRAID `nobody`/`users` (default `99`/`100`).

### Build the image

```bash
docker build -t ripuz .
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PUID` | `99` | User ID (UNRAID nobody) |
| `PGID` | `100` | Group ID (UNRAID users) |
| `UMASK` | `022` | File permissions mask |
| `CONFIG_DIR` | `/config` | Config + DB directory |
| `DOWNLOADS_DIR` | `/downloads` | Scratch download directory |
| `MUSIC_DIR` | `/music` | Final music library |
| `APP_PORT` | `8080` | WebUI port |
| `PICARD_TIMEOUT` | `600` | Seconds before Picard is killed |
| `PICARD_BIN` | `picard` | Override Picard binary path |
| `QOBUZ_QUALITY` | `27` | Startup default quality: 5=MP3, 6=FLAC 16/44, 7=FLAC 24/96, 27=FLAC 24/192. Overridden by the Settings UI once saved. |
| `RIPUZ_AUTH_USER` | `ripuz` | Basic Auth username (if enabled) |
| `RIPUZ_AUTH_PASS` | _(empty)_ | Basic Auth password; set to enable auth |
| `CHOWN_MUSIC_RECURSIVE` | `0` | Set to `1` to chown `/music` recursively on startup |

## Project structure

```
app/
  main.py           FastAPI app + lifespan + API routes
  config.py         Env-driven paths
  db.py             SQLite: jobs, settings, album_cache
  settings_store.py Persist settings + render qobuz-dl config.ini
  qobuz_client.py   Qobuz API: playlist→tracks, track→album_id, dedup
  qobuz_cli.py      Subprocess wrapper for `qobuz-dl dl -q <quality>`
  picard.py         Headless Picard runner (xvfb-run + -e commands)
  pipeline.py       Orchestrate download→tag→verify→cleanup
  jobs.py           SQLite job queue + background worker thread
  structure.py      Verify Artist/Album/song.FLAC, clean empty dirs
  static/           index.html, style.css, app.js
picard/
  Picard.ini        Picard config template (move+rename, naming script)
tests/              224 unit tests, all mocked (no real Qobuz/Picard needed)
Dockerfile          python:3.12-slim + picard + xvfb + ffmpeg + gosu
entrypoint.sh       PUID/PGID/UMASK drop + Picard.ini MUSIC_DIR injection
docker-compose.yml  Local dev / UNRAID reference
ripuz.xml           UNRAID Community-Apps template
```

## Running tests

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -v
```

## Security

Ripuz ships with **no authentication enabled by default** for trusted-LAN homelab use. To enable Basic Auth, set `RIPUZ_AUTH_PASS` (and optionally `RIPUZ_AUTH_USER`). Do not expose port `8080` to untrusted networks; put it behind a reverse proxy, VPN, or firewall. For stricter local file permissions on config/DB files, set `UMASK=077`.

## Legal / disclaimer

Ripuz orchestrates downloads using **your own Qobuz subscription** and the official authenticated API. No music is bundled or distributed. Use for personal use only; this may violate Qobuz's Terms of Service. You are responsible for compliance in your jurisdiction.

## Notice

See [CREDITS.md](CREDITS.md) for third-party attribution and licenses.

## Known limitations & notes

- **Picard headless is the riskiest part.** MusicBrainz lookup is async; Picard's remote-command interface queues them sequentially but network latency means large batches may time out before all files are saved. Increase `PICARD_TIMEOUT` if needed. The pipeline is isolated in `picard.py` — if Picard proves too unreliable, it can be swapped for `beets` without changing the rest of the code.
- qobuz-dl requires an **active Qobuz subscription** (Studio or higher for hi-res).
- Picard's `LOOKUP clustered` works best when tracks already have embedded MBIDs or good tags — qobuz-dl-ultimate's Roon-optimised tags give it a good starting point.
- The Picard.ini naming script forces `.FLAC` uppercase and replaces spaces with `_`. Tweak `/config/picard/Picard.ini` on the server to change the naming convention without rebuilding the image.
