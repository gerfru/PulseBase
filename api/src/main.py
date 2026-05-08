import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import bcrypt
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from src.db import (
    Settings,
    get_pool,
    create_user,
    get_user_by_email,
    get_user_by_id,
    set_garmin_linked,
    set_garmin_unlinked,
    get_recent_activities,
    get_activity_detail,
    get_daily_summaries,
    get_sleep_sessions,
    get_latest_hrv,
    get_hrv_trend,
    get_latest_training_status,
    get_weekly_stats,
    get_readiness,
    request_sync,
    get_sync_status,
)
from src.garmin.client import GarminClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings()


def _get_real_ip(request: Request) -> str:
    """Extract real client IP behind reverse proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


limiter = Limiter(key_func=_get_real_ip)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://unpkg.com; "
            "img-src 'self' data: https:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    logger.info("DB pool initialized")
    yield


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": {"code": "RATE_LIMITED", "message": "Too many requests."}},
    )


app = FastAPI(title="Garmin Dashboard API", lifespan=lifespan)
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "static")),
    name="static",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=settings.https_only,
    same_site="lax",
)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class NeedsLogin(Exception):
    pass


@app.exception_handler(NeedsLogin)
async def needs_login_handler(request: Request, exc: NeedsLogin):
    return RedirectResponse("/login", status_code=303)


async def require_user(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if not user_id:
        raise NeedsLogin()
    user = await get_user_by_id(user_id)
    if not user:
        raise NeedsLogin()
    return user


# ── Health ────────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Öffentliche Routen ────────────────────────────────────────────────────────


@app.get("/login")
async def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    email: str = Form(),
    password: str = Form(),
):
    user = await get_user_by_email(email)
    if not user or not verify_password(password, user.get("password_hash") or ""):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "E-Mail oder Passwort falsch."},
            status_code=400,
        )
    request.session["user_id"] = user["id"]
    return RedirectResponse("/", status_code=303)


@app.get("/register")
async def register_form(request: Request):
    return templates.TemplateResponse(request, "register.html")


@app.post("/register")
@limiter.limit("5/minute")
async def register(
    request: Request,
    name: str = Form(),
    email: str = Form(),
    password: str = Form(),
    password_confirm: str = Form(),
):
    if password != password_confirm:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Passwörter stimmen nicht überein."},
            status_code=400,
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Passwort muss mindestens 8 Zeichen haben."},
            status_code=400,
        )
    try:
        password_hash = hash_password(password)
        user = await create_user(name, email, password_hash)
    except Exception:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Diese E-Mail ist bereits registriert."},
            status_code=400,
        )
    request.session["user_id"] = user["id"]
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ── Geschützte Routen ─────────────────────────────────────────────────────────


@app.get("/")
async def index(request: Request):
    await require_user(request)
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/garmin/link")
async def garmin_link_form(request: Request):
    user = await require_user(request)
    return templates.TemplateResponse(request, "link_garmin.html", {"user": user})


@app.post("/garmin/link")
async def garmin_link(
    request: Request,
    garmin_email: str = Form(),
    garmin_password: str = Form(),
):
    user = await require_user(request)
    try:
        client = GarminClient(
            email=garmin_email,
            password=garmin_password,
            token_dir=f"/app/tokens/{user['id']}",
        )
        client.connect()
        del garmin_password
        await set_garmin_linked(user["id"], garmin_email)
        logger.info(f"Garmin verknüpft für User {user['id']}")
        return RedirectResponse("/?linked=1", status_code=303)
    except Exception as e:
        logger.error(
            f"Garmin Login fehlgeschlagen für User {user['id']}: {type(e).__name__}"
        )
        return templates.TemplateResponse(
            request,
            "link_garmin.html",
            {"user": user, "error": "Login fehlgeschlagen. Bitte Zugangsdaten prüfen."},
            status_code=400,
        )


@app.post("/garmin/unlink")
async def garmin_unlink(request: Request):
    user = await require_user(request)
    await set_garmin_unlinked(user["id"])
    logger.info(f"Garmin Verknüpfung entfernt für User {user['id']}")
    return RedirectResponse("/", status_code=303)


# ── Dashboard ─────────────────────────────────────────────────────────────────


@app.get("/dashboard")
async def dashboard(request: Request):
    user = await require_user(request)
    return templates.TemplateResponse(request, "dashboard.html", {"user": user})


# ── JSON API ──────────────────────────────────────────────────────────────────


@app.get("/activity/{activity_id}")
async def activity_detail_page(request: Request, activity_id: int):
    user = await require_user(request)
    activity = await get_activity_detail(user["id"], activity_id)
    if not activity:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(
        request, "activity.html", {"user": user, "activity": activity}
    )


@app.get("/api/activities/{activity_id}")
async def api_activity_detail(request: Request, activity_id: int):
    user = await require_user(request)
    detail = await get_activity_detail(user["id"], activity_id)
    if not detail:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": "Activity not found"}},
        )
    return detail


@app.get("/api/activities")
async def api_activities(
    request: Request,
    days: int = Query(default=7, ge=1, le=365),
    limit: int = Query(default=500, ge=1, le=500),
):
    user = await require_user(request)
    return await get_recent_activities(user["id"], limit=limit, days=days)


@app.get("/api/daily")
async def api_daily(request: Request, days: int = Query(default=30, ge=1, le=365)):
    user = await require_user(request)
    return await get_daily_summaries(user["id"], days=days)


@app.get("/api/sleep")
async def api_sleep(request: Request, days: int = Query(default=14, ge=1, le=365)):
    user = await require_user(request)
    return await get_sleep_sessions(user["id"], limit=days)


@app.get("/api/hrv")
async def api_hrv(request: Request):
    user = await require_user(request)
    return await get_latest_hrv(user["id"])


@app.get("/api/hrv/trend")
async def api_hrv_trend(request: Request, days: int = Query(default=30, ge=1, le=365)):
    user = await require_user(request)
    return await get_hrv_trend(user["id"], days=days)


@app.get("/api/training-status")
async def api_training_status(request: Request):
    user = await require_user(request)
    return await get_latest_training_status(user["id"])


@app.get("/api/weekly")
async def api_weekly(
    request: Request,
    weeks: int = Query(default=12, ge=1, le=52),
):
    user = await require_user(request)
    return await get_weekly_stats(user["id"], weeks=weeks)


@app.get("/api/readiness")
async def api_readiness(request: Request):
    user = await require_user(request)
    return await get_readiness(user["id"])


@app.post("/api/sync")
async def api_sync(request: Request):
    user = await require_user(request)
    if not user.get("garmin_linked"):
        return JSONResponse(
            status_code=400,
            content={
                "error": {"code": "NOT_LINKED", "message": "Garmin account not linked"}
            },
        )
    await request_sync(user["id"])
    return {"status": "requested"}


@app.get("/api/sync-status")
async def api_sync_status(request: Request):
    user = await require_user(request)
    return await get_sync_status(user["id"])
