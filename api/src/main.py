import asyncio
import secrets
import time
import uuid

import psutil
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.sessions import SessionMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

from src.db import get_pool
from src.deps import (
    NeedsLogin,
    _rate_limit_exceeded_handler,
    limiter,
    require_user,
    settings,
)
from src.logging_config import configure_logging, configure_sentry
from src.routes import account, api as api_routes
from src.routes import auth, garmin, libre, pages

configure_logging()
logger = structlog.get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        nonce = secrets.token_urlsafe(16)
        request.state.nonce = nonce
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        if settings.https_only:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'nonce-{nonce}' 'strict-dynamic'; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; "
            "img-src 'self' data: https:; "
            "media-src 'self' data:; "
            "connect-src 'self'; "
            "worker-src 'none'; "
            "manifest-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        return response


_active_requests: int = 0
_error_requests: int = 0
_metrics_lock = asyncio.Lock()
_start_time: float = time.monotonic()


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        global _active_requests, _error_requests
        async with _metrics_lock:
            _active_requests += 1
        request_id = str(uuid.uuid4())[:8]
        clear_contextvars()
        bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            async with _metrics_lock:
                _active_requests -= 1
                _error_requests += 1
            raise
        else:
            async with _metrics_lock:
                _active_requests -= 1
            if response.status_code >= 400:
                async with _metrics_lock:
                    _error_requests += 1
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            active_requests=_active_requests,
        )
        response.headers["X-Request-ID"] = request_id
        return response


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
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
    pool = await get_pool()
    logger.info("db.pool_initialized")
    try:
        from cryptography.fernet import Fernet

        Fernet(settings.fernet_key.encode())
    except ValueError as e:
        raise ValueError("FERNET_KEY invalid — must be 32-byte URL-safe base64") from e
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    configure_sentry(
        settings, integrations=[StarletteIntegration(), FastApiIntegration()]
    )
    yield
    await pool.close()
    logger.info("db.pool_closed")


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
async def needs_login_handler(request: Request, exc: NeedsLogin) -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/metrics")
async def app_metrics(request: Request) -> dict[str, float | int]:
    await require_user(request)
    async with _metrics_lock:
        active = _active_requests
        errors = _error_requests
    proc = psutil.Process()
    return {
        "active_requests": active,
        "error_requests_total": errors,
        "uptime_seconds": round(time.monotonic() - _start_time),
        "memory_mb": round(proc.memory_info().rss / 1024 / 1024, 1),
        "cpu_percent": proc.cpu_percent(interval=None),
    }


@app.get("/ready", response_model=None)
async def ready() -> JSONResponse | dict[str, str]:
    try:
        pool = await get_pool()
        await pool.fetchval("SELECT 1")
        migrations_ok = await pool.fetchval(
            "SELECT COUNT(*) FROM flyway_schema_history WHERE success = TRUE"
        )
        if not migrations_ok:
            return JSONResponse(status_code=503, content={"status": "no_migrations"})
        return {"status": "ready"}
    except Exception:
        logger.exception("readiness.check_failed")
        return JSONResponse(status_code=503, content={"status": "unavailable"})


app.include_router(auth.router)
app.include_router(account.router)
app.include_router(garmin.router)
app.include_router(libre.router)
app.include_router(pages.router)
app.include_router(api_routes.router)
