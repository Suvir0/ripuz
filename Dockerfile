FROM python:3.12-slim

# ── System packages ───────────────────────────────────────────────────────────
# picard: MusicBrainz Picard 2.9+ (apt name on Debian bookworm is picard)
# xvfb:  virtual framebuffer for headless Picard GUI
# ffmpeg: required by qobuz-dl for audio remuxing
# gosu:  PUID/PGID privilege drop
RUN apt-get update && apt-get install -y --no-install-recommends \
      picard \
      xvfb \
      xauth \
      ffmpeg \
      gosu \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────────────
COPY app/ ./app/
COPY picard/ ./picard/

# ── Entrypoint ────────────────────────────────────────────────────────────────
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ── Volumes ───────────────────────────────────────────────────────────────────
VOLUME ["/config", "/downloads", "/music"]

EXPOSE 8080

ENV CONFIG_DIR=/config \
    DOWNLOADS_DIR=/downloads \
    MUSIC_DIR=/music \
    APP_PORT=8080 \
    LOG_LEVEL=info

ENTRYPOINT ["/entrypoint.sh"]
