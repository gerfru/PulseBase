import asyncio
import re
import secrets
import statistics
import time
import uuid
from collections import deque
from collections.abc import AsyncGenerator

import psutil
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.sessions import SessionMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

from src.db import get_pool
from src.deps import (
    HTTP_ERROR_CODES,
    NeedsLogin,
    _rate_limit_exceeded_handler,
    error_envelope,
    limiter,
    require_user,
    settings,
)
from src.logging_config import _release, configure_logging, configure_sentry
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
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        if settings.https_only:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'nonce-{nonce}' 'strict-dynamic'; "
            f"style-src 'self' 'nonce-{nonce}'; "
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


_TOKEN_PATH_RE = re.compile(r"^/(auth/(reset|verify)|account/delete/confirm)/[^/]+")


def _safe_path(path: str) -> str:
    """Replace token segments in sensitive URL paths to avoid leaking them in logs."""
    return _TOKEN_PATH_RE.sub(lambda m: m.group(0).rsplit("/", 1)[0] + "/<token>", path)


_active_requests: int = 0
_error_requests: int = 0
_metrics_lock = asyncio.Lock()
_start_time: float = time.monotonic()
_duration_deque: deque[float] = deque(maxlen=1000)
# Module-level Process so cpu_percent() keeps state between scrapes. A fresh
# psutil.Process() per request would always report 0.0 on its first call.
_proc = psutil.Process()


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        global _active_requests, _error_requests
        async with _metrics_lock:
            _active_requests += 1
        request_id = str(uuid.uuid4())
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
        _duration_deque.append(duration_ms)
        logger.info(
            "http.request",
            method=request.method,
            path=_safe_path(request.url.path),
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
            response.headers.setdefault("Vary", "Cookie")
        elif request.method in ("POST", "PUT", "PATCH", "DELETE"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # pragma: no cover
    pool = await get_pool()
    logger.info("db.pool_initialized")
    # Prime cpu_percent() so the first /api/metrics scrape reports a real value.
    _proc.cpu_percent(interval=None)
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


app = FastAPI(title="PulseBase API", version=_release(), lifespan=lifespan)
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
    same_site="strict",
    max_age=3600,
)


@app.exception_handler(NeedsLogin)
async def needs_login_handler(request: Request, exc: NeedsLogin) -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Normalise Pydantic/FastAPI 422s into the unified error envelope. We map
    # only `loc` + `msg` and deliberately DROP `input`/`ctx`: Pydantic echoes the
    # offending value, which on auth POSTs (/login, /register, /auth/reset/*) is
    # the client's plaintext password. Keeping it would leak it into both the
    # response body and the Sentry event. Security invariant: no client-submitted
    # value ever leaves the server via an error response.
    details = [
        {"field": ".".join(str(p) for p in err["loc"]), "msg": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_envelope("VALIDATION_ERROR", "Eingabe ungültig", details),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    # Unify raised HTTPExceptions (e.g. 403 CSRF, 404, 405) into the envelope.
    # Only exc.detail (a developer-controlled string) becomes the message — never
    # internal state. Preserve headers so 401 challenges / 405 Allow survive.
    code = HTTP_ERROR_CODES.get(exc.status_code, "ERROR")
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope(code, message),
        headers=getattr(exc, "headers", None),
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/metrics")
async def app_metrics(request: Request) -> dict[str, float | int | None]:
    await require_user(request)
    async with _metrics_lock:
        active = _active_requests
        errors = _error_requests
    pool = await get_pool()
    pool_size = pool.get_size()
    pool_idle = pool.get_idle_size()
    samples = list(_duration_deque)
    p95 = (
        round(statistics.quantiles(samples, n=20)[18], 1)
        if len(samples) >= 20
        else None
    )
    return {
        "active_requests": active,
        "error_requests_total": errors,
        "uptime_seconds": round(time.monotonic() - _start_time),
        "memory_mb": round(_proc.memory_info().rss / 1024 / 1024, 1),
        "cpu_percent": _proc.cpu_percent(interval=None),
        "db_pool_used": pool_size - pool_idle,
        "db_pool_max": pool_size,
        "p95_duration_ms": p95,
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
