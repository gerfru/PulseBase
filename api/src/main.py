import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

from src.db import get_pool
from src.deps import (
    NeedsLogin,
    _rate_limit_exceeded_handler,
    limiter,
    settings,
)
from src.logging_config import configure_logging
from src.routes import account, api as api_routes
from src.routes import auth, garmin, libre, pages

configure_logging()
logger = structlog.get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; "
            "img-src 'self' data: https:; "
            "media-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        clear_contextvars()
        bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/static/") and path.endswith(".js"):
            response.headers["Cache-Control"] = "no-cache"
        elif path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif path.startswith("/api/") and request.method == "GET":
            response.headers.setdefault("Cache-Control", "private, no-cache")
        elif request.method in ("POST", "PUT", "PATCH", "DELETE"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):  # pragma: no cover
    await get_pool()
    logger.info("db.pool_initialized")
    if not settings.fernet_key:
        logger.warning("fernet_key.missing", detail="tokens stored unencrypted in DB")
    else:
        try:
            from cryptography.fernet import Fernet

            Fernet(settings.fernet_key.encode())
        except Exception:
            raise ValueError("FERNET_KEY invalid — must be 32-byte URL-safe base64")
    if settings.sentry_dsn:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[StarletteIntegration(), FastApiIntegration()],
            send_default_pii=False,
            traces_sample_rate=0.0,
        )
        logger.info("sentry.initialized")
    yield


app = FastAPI(title="PulseBase API", lifespan=lifespan)
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "static")),
    name="static",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# Middleware-Reihenfolge: last added = outermost (executes first)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(CacheControlMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=settings.https_only,
    same_site="lax",
    max_age=3600,
)


@app.exception_handler(NeedsLogin)
async def needs_login_handler(request: Request, exc: NeedsLogin):
    return RedirectResponse("/login", status_code=303)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    try:
        pool = await get_pool()
        await pool.fetchval("SELECT 1")
        return {"status": "ready"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})


app.include_router(auth.router)
app.include_router(account.router)
app.include_router(garmin.router)
app.include_router(libre.router)
app.include_router(pages.router)
app.include_router(api_routes.router)
