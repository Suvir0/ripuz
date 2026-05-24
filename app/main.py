"""
FastAPI application entry point.
"""
import base64
import binascii
import logging
import secrets as _secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
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

class _BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _AUTH_PASS:
            return await call_next(request)
        if request.url.path in ("/healthz",):
            return await call_next(request)
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
            return Response(
                "Unauthorized",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Ripuz"'},
            )
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_dirs()
    db.init_db(config.DB_FILE)
    from app.jobs import start_worker, stop_worker
    start_worker()
    logger.info("Ripuz started. DB: %s", config.DB_FILE)
    yield
    stop_worker()


app = FastAPI(title="Ripuz", lifespan=lifespan)
app.add_middleware(_BasicAuthMiddleware)


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
    from app.settings_store import save_settings, get_token, VALID_QUALITIES
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
    save_settings(token, downloads, music, quality)
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


@app.post("/api/jobs")
async def api_create_job(body: dict):
    from app.jobs import enqueue
    VALID_TYPES = {"playlist", "expand_albums", "track", "album", "discography", "expand_discographies"}
    job_type = body.get("type", "playlist")
    url = body.get("url", "").strip()
    if not url:
        return JSONResponse({"error": "url required"}, status_code=400)
    if job_type not in VALID_TYPES:
        return JSONResponse({"error": "invalid type"}, status_code=400)
    if not is_valid_qobuz_input(url):
        return JSONResponse({"error": "url must be a qobuz.com URL or ID"}, status_code=400)
    job_id = enqueue(job_type, url)
    return {"job_id": job_id}


# Mount static files last (catch-all)
if _STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
