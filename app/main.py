"""
FastAPI application entry point.
"""
import base64
import binascii
import logging
import secrets as _secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app import config, db
from app.qobuz_client import is_valid_qobuz_input

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"

# Optional HTTP Basic Auth — off by default; set RIPUZ_AUTH_PASS to enable.
_AUTH_USER = config.RIPUZ_AUTH_USER
_AUTH_PASS = config.RIPUZ_AUTH_PASS

# Brute-force backoff state (only active when auth is enabled).
# Maps client IP → (fail_count, locked_until_epoch).
_auth_failures: dict[str, tuple[int, float]] = {}

_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "  # unsafe-inline required by existing onclick= rendering
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data: https://static.qobuz.com; "
    "connect-src 'self'"
)
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": _CSP,
}


class _SecurityMiddleware(BaseHTTPMiddleware):
    """CSRF protection (Origin/Sec-Fetch-Site check) + security response headers."""

    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "DELETE", "PUT", "PATCH") and request.url.path.startswith("/api/"):
            origin = request.headers.get("Origin")
            sec_fetch_site = request.headers.get("Sec-Fetch-Site")
            if origin:
                origin_host = urlparse(origin).netloc  # host:port
                host = request.headers.get("Host", "")
                if origin_host != host:
                    return JSONResponse(
                        {"error": "cross-origin request rejected"},
                        status_code=403,
                    )
            elif sec_fetch_site and sec_fetch_site not in ("same-origin", "none"):
                return JSONResponse(
                    {"error": "cross-origin request rejected"},
                    status_code=403,
                )
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
        return response


class _BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _AUTH_PASS:
            return await call_next(request)
        if request.url.path in ("/healthz",):
            return await call_next(request)

        client_ip = (request.client.host if request.client else "") or ""
        now = time.monotonic()
        fail_count, locked_until = _auth_failures.get(client_ip, (0, 0.0))
        if now < locked_until:
            return Response("Too Many Requests", status_code=429)

        auth = request.headers.get("Authorization", "")
        authed = False
        if auth.startswith("Basic "):
            try:
                decoded = base64.b64decode(
                    auth[6:].encode("ascii"), validate=True
                ).decode()
            except (binascii.Error, UnicodeDecodeError, UnicodeEncodeError):
                decoded = ""
            if decoded:
                username, _, password = decoded.partition(":")
                authed = (
                    _secrets.compare_digest(username, _AUTH_USER)
                    and _secrets.compare_digest(password, _AUTH_PASS)
                )
        if not authed:
            new_fails = fail_count + 1
            backoff = min(2 ** max(new_fails - 5, 0), 300) if new_fails >= 5 else 0
            _auth_failures[client_ip] = (new_fails, now + backoff)
            return Response(
                "Unauthorized",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Ripuz"'},
            )
        if fail_count:
            _auth_failures.pop(client_ip, None)
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_dirs()
    db.init_db(config.DB_FILE)
    from app.jobs import start_worker, stop_worker
    start_worker()
    if not config.RIPUZ_AUTH_PASS:
        logger.warning("=" * 64)
        logger.warning("RIPUZ_AUTH_PASS is not set — the web UI and API are UNAUTHENTICATED.")
        logger.warning("Anyone who can reach port %s can download music and change settings.", config.APP_PORT)
        logger.warning("Set RIPUZ_AUTH_PASS to enable HTTP Basic Auth.")
        logger.warning("=" * 64)
    logger.info("Ripuz started. DB: %s", config.DB_FILE)
    yield
    stop_worker()


app = FastAPI(title="Ripuz", lifespan=lifespan)
app.add_middleware(_BasicAuthMiddleware)
app.add_middleware(_SecurityMiddleware)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/api/settings")
async def api_get_settings():
    from app.settings_store import get_settings
    s = get_settings()
    # Never return the token value to the browser, only whether it's set
    return {**s, "qobuz_token": "***" if s["qobuz_token"] else ""}


@app.post("/api/settings")
async def api_save_settings(body: dict):
    from app.settings_store import save_settings, get_token, VALID_QUALITIES, validate_dir_setting
    token = body.get("qobuz_token", "").strip()
    downloads = body.get("downloads_dir", "").strip() or None
    music = body.get("music_dir", "").strip() or None
    if not token or token == "***":
        token = get_token()
    quality: int | None = None
    if "music_quality" in body:
        try:
            quality = int(body["music_quality"])
        except (ValueError, TypeError):
            return JSONResponse({"error": "invalid quality"}, status_code=400)
        if quality not in VALID_QUALITIES:
            return JSONResponse({"error": "invalid quality"}, status_code=400)
    if downloads:
        err = validate_dir_setting(downloads, config.DOWNLOADS_DIR)
        if err:
            return JSONResponse({"error": err}, status_code=400)
    if music:
        err = validate_dir_setting(music, config.MUSIC_DIR)
        if err:
            return JSONResponse({"error": err}, status_code=400)
    download_lyrics: bool | None = None
    if "download_lyrics" in body:
        download_lyrics = bool(body["download_lyrics"])
    prefer_explicit: bool | None = None
    if "prefer_explicit" in body:
        prefer_explicit = bool(body["prefer_explicit"])
    notify_webhook_url: str | None = None
    if "notify_webhook_url" in body:
        notify_webhook_url = body.get("notify_webhook_url", "").strip() or None
    save_settings(token, downloads, music, quality, download_lyrics, prefer_explicit, notify_webhook_url)
    return {"ok": True}


@app.get("/api/jobs")
async def api_list_jobs():
    return db.list_jobs()


@app.get("/api/jobs/{job_id}")
async def api_get_job(job_id: int):
    job = db.get_job(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    return job


@app.post("/api/jobs/{job_id}/confirm")
async def api_confirm_job(job_id: int):
    job = db.get_job(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    if job["status"] != "awaiting_confirm":
        return JSONResponse(
            {"error": f"job is '{job['status']}', expected 'awaiting_confirm'"},
            status_code=409,
        )
    db.update_job(job_id, status="confirmed")
    return {"ok": True}


@app.post("/api/jobs/{job_id}/cancel")
async def api_cancel_job(job_id: int):
    from app.jobs import cancel_job
    job = db.get_job(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    terminal = {"done", "done_with_warnings", "error", "cancelled"}
    if job["status"] in terminal:
        return JSONResponse(
            {"error": f"job already finished with status '{job['status']}'"},
            status_code=409,
        )
    cancel_job(job_id)
    return {"ok": True}


@app.delete("/api/jobs/{job_id}")
async def api_delete_job(job_id: int):
    job = db.get_job(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    if job["status"] not in db._TERMINAL_STATUSES:
        return JSONResponse(
            {"error": f"cannot delete active job (status: '{job['status']}')"},
            status_code=409,
        )
    db.delete_job(job_id)
    return {"ok": True}


@app.post("/api/jobs")
async def api_create_job(body: dict):
    from app.jobs import enqueue
    VALID_TYPES = {
        "playlist", "expand_albums", "track", "album",
        "discography", "expand_discographies", "explicit_upgrade",
        "retag_library", "fetch_lyrics", "fetch_art",
    }
    _LIBRARY_ONLY_TYPES = {"retag_library", "fetch_lyrics", "fetch_art"}
    _LIBRARY_ALLOWED_TYPES = {"explicit_upgrade", "retag_library", "fetch_lyrics", "fetch_art"}
    job_type = body.get("type", "playlist")
    url = body.get("url", "").strip()
    if not url:
        return JSONResponse({"error": "url required"}, status_code=400)
    if job_type not in VALID_TYPES:
        return JSONResponse({"error": "invalid type"}, status_code=400)
    # retag_library / fetch_lyrics / fetch_art only ever scan the local /music library — no URL.
    if job_type in _LIBRARY_ONLY_TYPES and url != "library":
        return JSONResponse(
            {"error": f"{job_type} only supports the 'library' source"},
            status_code=400,
        )
    # explicit_upgrade may use the sentinel "library" (scan local /music dir)
    # or a normal Qobuz playlist URL — both are valid.
    if url != "library" and not is_valid_qobuz_input(url):
        return JSONResponse({"error": "url must be a qobuz.com URL or ID"}, status_code=400)
    if url == "library" and job_type not in _LIBRARY_ALLOWED_TYPES:
        return JSONResponse(
            {"error": "'library' source is only valid for explicit_upgrade, retag_library, fetch_lyrics, and fetch_art jobs"},
            status_code=400,
        )
    job_id = enqueue(job_type, url)
    return {"job_id": job_id}


@app.get("/api/library")
def api_library(refresh: int = 0):
    from app.library_stats import get_library
    return get_library(refresh=bool(refresh))


@app.get("/api/library/cover/{album_id:path}")
def api_library_cover(album_id: str):
    from fastapi.responses import FileResponse
    from app.art_library import find_cover
    if not album_id or "\x00" in album_id:
        return JSONResponse({"error": "invalid album id"}, status_code=404)
    music_root = config.MUSIC_DIR.resolve()
    try:
        target = (config.MUSIC_DIR / album_id).resolve()
        target.relative_to(music_root)
    except (ValueError, Exception):
        return JSONResponse({"error": "not found"}, status_code=404)
    if not target.is_dir():
        return JSONResponse({"error": "not found"}, status_code=404)
    cover = find_cover(target)
    if not cover:
        return JSONResponse({"error": "no cover art"}, status_code=404)
    return FileResponse(cover, headers={"Cache-Control": "private, max-age=86400"})


@app.get("/api/library/album/{album_id:path}")
def api_library_album(album_id: str):
    if not album_id or "\x00" in album_id:
        return JSONResponse({"error": "invalid album id"}, status_code=404)
    music_root = config.MUSIC_DIR.resolve()
    try:
        target = (config.MUSIC_DIR / album_id).resolve()
        target.relative_to(music_root)
    except (ValueError, Exception):
        return JSONResponse({"error": "not found"}, status_code=404)
    if not target.is_dir():
        return JSONResponse({"error": "not found"}, status_code=404)
    from app.structure import find_flac_files
    from app.art_library import find_cover
    tracks = []
    try:
        from mutagen.flac import FLAC
        for flac_path in sorted(find_flac_files(target)):
            try:
                audio = FLAC(flac_path)
                def _tag(key, default=""):
                    vals = audio.get(key)
                    return str(vals[0]).strip() if vals else default
                try:
                    dur = round(audio.info.length)
                except Exception:
                    dur = 0
                tracks.append({
                    "title": _tag("title", flac_path.stem),
                    "tracknumber": _tag("tracknumber"),
                    "discnumber": _tag("discnumber"),
                    "duration": dur,
                    "bit_depth": getattr(audio.info, "bits_per_sample", 0),
                    "sample_rate": getattr(audio.info, "sample_rate", 0),
                    "has_lyrics": flac_path.with_suffix(".lrc").exists(),
                })
            except Exception:
                continue
    except Exception:
        pass
    has_cover = find_cover(target) is not None
    mbid = None
    if tracks:
        from app.art_library import _read_album_mbid
        mbid = _read_album_mbid(target)
    parts = album_id.split("/", 1)
    return {
        "id": album_id,
        "artist": parts[0] if len(parts) > 0 else "",
        "album": parts[1] if len(parts) > 1 else "",
        "has_cover": has_cover,
        "mbid_present": bool(mbid),
        "track_count": len(tracks),
        "total_duration": sum(t["duration"] for t in tracks),
        "size_bytes": sum(
            (target / t["title"]).stat().st_size if (target / t["title"]).exists() else 0
            for t in tracks
        ),
        "tracks": tracks,
    }


@app.get("/api/jobs/{job_id}/stream")
async def api_job_stream(job_id: int):
    """SSE stream: emits 'log' and 'status' events while the job is active."""
    import asyncio
    from fastapi.responses import StreamingResponse

    TERMINAL = {"done", "done_with_warnings", "error", "cancelled"}

    async def generate():
        last_log_len = 0
        last_status = None
        heartbeat_count = 0
        job = db.get_job(job_id)
        if not job:
            yield "event: error\ndata: not found\n\n"
            return
        while True:
            job = db.get_job(job_id)
            if not job:
                break
            log = job.get("log") or ""
            if len(log) > last_log_len:
                yield "event: log\ndata: append\n\n"
                last_log_len = len(log)
            if job["status"] != last_status:
                last_status = job["status"]
                import json as _json
                yield f"event: status\ndata: {_json.dumps({'status': last_status})}\n\n"
            if last_status in TERMINAL:
                break
            heartbeat_count += 1
            if heartbeat_count % 15 == 0:
                yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.get("/api/search")
async def api_search(q: str = "", type: str = "album", limit: int = 15):
    if not q.strip():
        return JSONResponse({"error": "q required"}, status_code=400)
    from app.settings_store import get_token
    from app.qobuz_client import make_client
    token = get_token()
    if not token:
        return JSONResponse({"error": "Qobuz token not configured"}, status_code=503)
    try:
        client = make_client(token)
        results = client.search(q.strip(), media_type=type, limit=min(limit, 50))
        return {"results": results}
    except Exception as exc:
        logger.warning("Search failed: %s", exc)
        return JSONResponse({"error": f"search failed: {exc}"}, status_code=502)


_INDEX_TEMPLATE = (_STATIC_DIR / "index.html").read_text(encoding="utf-8") if _STATIC_DIR.exists() else ""

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index():
    return _INDEX_TEMPLATE.replace("__VERSION__", config.APP_VERSION)

# Mount static files last (catch-all)
if _STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
