#!/bin/sh
set -e

# ── PUID / PGID / UMASK (UNRAID convention) ───────────────────────────────────
PUID=${PUID:-99}
PGID=${PGID:-100}
UMASK=${UMASK:-022}

# Create/update the ripuz user to match requested UID/GID
if ! getent group ripuz > /dev/null 2>&1; then
    groupadd -g "${PGID}" ripuz 2>/dev/null || groupmod -n ripuz "$(getent group "${PGID}" | cut -d: -f1)"
fi
if ! id -u ripuz > /dev/null 2>&1; then
    useradd -u "${PUID}" -g "${PGID}" -d /app -s /sbin/nologin ripuz 2>/dev/null \
      || usermod -u "${PUID}" ripuz
fi

umask "${UMASK}"

# ── Ensure volume directories exist with correct ownership ───────────────────
# Config and downloads are small/app-owned — chown recursively.
for dir in "${CONFIG_DIR:-/config}" "${DOWNLOADS_DIR:-/downloads}"; do
    mkdir -p "${dir}"
    chown -R "${PUID}:${PGID}" "${dir}"
done
# Music library: chown only the top-level dir to avoid slow recursion over
# large existing libraries (Plex/Roon). Set CHOWN_MUSIC_RECURSIVE=1 to force.
mkdir -p "${MUSIC_DIR:-/music}"
if [ "${CHOWN_MUSIC_RECURSIVE:-0}" = "1" ]; then
    chown -R "${PUID}:${PGID}" "${MUSIC_DIR:-/music}"
else
    chown "${PUID}:${PGID}" "${MUSIC_DIR:-/music}"
fi

# ── Install Picard.ini if not already present ─────────────────────────────────
PICARD_CFG="${CONFIG_DIR:-/config}/picard/Picard.ini"
if [ ! -f "${PICARD_CFG}" ]; then
    mkdir -p "$(dirname "${PICARD_CFG}")"
    # Replace __MUSIC_DIR__ placeholder with real path
    sed "s|__MUSIC_DIR__|${MUSIC_DIR:-/music}|g" /app/picard/Picard.ini > "${PICARD_CFG}"
    chown "${PUID}:${PGID}" "${PICARD_CFG}"
fi

# ── Start uvicorn as ripuz user ───────────────────────────────────────────────
exec gosu "${PUID}:${PGID}" \
  python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${APP_PORT:-8080}" \
    --log-level "${LOG_LEVEL:-info}"
