import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, field_validator
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
    update_user_profile,
    set_garmin_linked,
    set_garmin_unlinked,
    get_recent_activities,
    get_activity_detail,
    set_activity_rpe,
    get_daily_summaries,
    get_sleep_sessions,
    get_latest_hrv,
    get_hrv_trend,
    get_latest_training_status,
    get_weekly_stats,
    get_readiness,
    get_energy_metrics,
    get_ml_insights,
    get_ml_history,
    get_ml_status,
    set_libre_linked,
    set_libre_unlinked,
    get_glucose_recent,
    get_glucose_stats,
    request_sync,
    get_sync_status,
    get_training_load_inputs,
    get_activity_hrmax,
    get_user_sex,
    save_seizure,
    get_seizures,
    get_seizure_risk,
)
from src.training_load import build_training_load
from src.garmin.client import GarminClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings()  # type: ignore[call-arg]


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
            "script-src 'self' https://cdn.jsdelivr.net https://unpkg.com https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://unpkg.com https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
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


app = FastAPI(title="PulseBase API", lifespan=lifespan)
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "static")),
    name="static",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=settings.https_only,
    same_site="lax",
)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["v"] = str(int(time.time()))


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
    except Exception as e:
        logger.warning("register failed for '%s': %s", email, e)
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


@app.get("/settings")
async def settings_page(request: Request):
    user = await require_user(request)
    return templates.TemplateResponse(
        request, "settings.html", {"user": user, "today": date.today().isoformat()}
    )


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


# ── LibreLinkUp ───────────────────────────────────────────────────────────────


@app.get("/libre/link")
async def libre_link_form(request: Request):
    user = await require_user(request)
    return templates.TemplateResponse(request, "link_libre.html", {"user": user})


@app.post("/libre/link")
async def libre_link(
    request: Request,
    libre_email: str = Form(),
    libre_password: str = Form(),
):
    from libre.client import LibreAuthError
    from libre.client import authenticate as libre_authenticate

    user = await require_user(request)
    try:
        libre_authenticate(
            libre_email,
            libre_password,
            token_dir=f"/app/tokens/{user['id']}/libre",
        )
        await set_libre_linked(user["id"], libre_email)
        logger.info(f"LibreLinkUp verknüpft für User {user['id']}")
        return RedirectResponse("/dashboard", status_code=303)
    except LibreAuthError as e:
        logger.warning(f"LibreLinkUp Login fehlgeschlagen User {user['id']}: {e}")
        return templates.TemplateResponse(
            request,
            "link_libre.html",
            {
                "user": user,
                "error": "Login fehlgeschlagen. Bitte Zugangsdaten prüfen und sicherstellen, dass du als Follower akzeptiert wurdest.",
            },
            status_code=400,
        )
    except Exception as e:
        logger.error(f"LibreLinkUp Fehler User {user['id']}: {type(e).__name__}")
        return templates.TemplateResponse(
            request,
            "link_libre.html",
            {
                "user": user,
                "error": "Verbindung fehlgeschlagen. Bitte erneut versuchen.",
            },
            status_code=400,
        )


@app.post("/libre/unlink")
async def libre_unlink(request: Request):
    import shutil

    user = await require_user(request)
    await set_libre_unlinked(user["id"])
    token_dir = Path(f"/app/tokens/{user['id']}/libre")
    if token_dir.exists():
        shutil.rmtree(token_dir)
    logger.info(f"LibreLinkUp Verknüpfung + Daten entfernt für User {user['id']}")
    return RedirectResponse("/libre/link", status_code=303)


@app.get("/api/glucose")
async def api_glucose(request: Request, hours: int = Query(default=24, ge=1, le=168)):
    user = await require_user(request)
    return await get_glucose_recent(user["id"], hours)


@app.get("/api/glucose/stats")
async def api_glucose_stats(
    request: Request, days: int = Query(default=14, ge=1, le=90)
):
    user = await require_user(request)
    return await get_glucose_stats(user["id"], days)


# ── Dashboard ─────────────────────────────────────────────────────────────────


@app.get("/dashboard")
async def dashboard(request: Request):
    user = await require_user(request)
    return templates.TemplateResponse(request, "dashboard.html", {"user": user})


_VALID_METRICS = {
    "steps",
    "sleep",
    "hrv",
    "body-battery",
    "physical",
    "autonomic",
    "cognitive",
    "hr-zscore",
    "readiness-rf",
    "hrv-status",
    "hrv-status-custom",
    "training-status",
    "readiness",
    "sleep-score-custom",
    "intensity-minutes",
    "training-effect",
}


@app.get("/metrics/{name}")
async def metrics_detail_page(request: Request, name: str):
    user = await require_user(request)
    if name not in _VALID_METRICS:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(
        request, "metrics.html", {"user": user, "metric_name": name}
    )


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


class RpeBody(BaseModel):
    rpe: int

    @field_validator("rpe")
    @classmethod
    def validate_rpe(cls, v: int) -> int:
        if not 1 <= v <= 10:
            raise ValueError("RPE must be between 1 and 10")
        return v


@app.patch("/api/activities/{activity_id}/rpe")
async def api_set_rpe(request: Request, activity_id: int, body: RpeBody):
    user = await require_user(request)
    updated = await set_activity_rpe(user["id"], activity_id, body.rpe)
    if not updated:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": "Activity not found"}},
        )
    return {"ok": True, "rpe": body.rpe}


@app.get("/api/activities")
async def api_activities(
    request: Request,
    days: int = Query(default=7, ge=1, le=365),
    limit: int = Query(default=500, ge=1, le=500),
    end_date: date | None = Query(default=None),
):
    user = await require_user(request)
    return await get_recent_activities(
        user["id"], limit=limit, days=days, end_date=end_date
    )


@app.get("/api/daily")
async def api_daily(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    end_date: date | None = Query(default=None),
):
    user = await require_user(request)
    return await get_daily_summaries(user["id"], days=days, end_date=end_date)


@app.get("/api/sleep")
async def api_sleep(
    request: Request,
    days: int = Query(default=14, ge=1, le=365),
    end_date: date | None = Query(default=None),
):
    user = await require_user(request)
    return await get_sleep_sessions(user["id"], days=days, end_date=end_date)


@app.get("/api/hrv")
async def api_hrv(request: Request):
    user = await require_user(request)
    return await get_latest_hrv(user["id"])


@app.get("/api/hrv/trend")
async def api_hrv_trend(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    end_date: date | None = Query(default=None),
):
    user = await require_user(request)
    return await get_hrv_trend(user["id"], days=days, end_date=end_date)


@app.get("/api/training-status")
async def api_training_status(request: Request):
    user = await require_user(request)
    return await get_latest_training_status(user["id"])


@app.get("/api/weekly")
async def api_weekly(
    request: Request,
    weeks: int = Query(default=12, ge=1, le=56),
    end_date: date | None = Query(default=None),
):
    user = await require_user(request)
    return await get_weekly_stats(user["id"], weeks=weeks, end_date=end_date)


@app.get("/api/readiness")
async def api_readiness(request: Request):
    user = await require_user(request)
    return await get_readiness(user["id"])


@app.get("/api/energy")
async def api_energy(request: Request):
    user = await require_user(request)
    return await get_energy_metrics(user["id"])


@app.get("/api/training-load")
async def api_training_load(
    request: Request,
    lookback_days: int = Query(default=None, ge=1, le=365),
):
    user = await require_user(request)
    rows, hrmax, sex = await asyncio.gather(
        get_training_load_inputs(user["id"]),
        get_activity_hrmax(user["id"]),
        get_user_sex(user["id"]),
    )
    return build_training_load(
        rows,
        hrmax,
        sex,
        lookback_days if lookback_days is not None else settings.trimp_lookback_days,
        settings.trimp_forecast_days,
    )


@app.get("/ml/anomaly")
async def ml_anomaly_page(request: Request):
    user = await require_user(request)
    return templates.TemplateResponse(
        request,
        "ml_insights.html",
        {"user": user, "section": "anomaly", "title": "Ruhepuls-Anomalie"},
    )


@app.get("/ml/readiness")
async def ml_readiness_page(request: Request):
    user = await require_user(request)
    return templates.TemplateResponse(
        request,
        "ml_insights.html",
        {"user": user, "section": "readiness", "title": "Readiness-Prognose"},
    )


@app.get("/ml/correlations")
async def ml_correlations_page(request: Request):
    user = await require_user(request)
    return templates.TemplateResponse(
        request,
        "ml_insights.html",
        {"user": user, "section": "correlations", "title": "Korrelationen"},
    )


@app.get("/ml/battery")
async def ml_battery_page(request: Request):
    user = await require_user(request)
    return templates.TemplateResponse(
        request,
        "ml_insights.html",
        {"user": user, "section": "battery", "title": "Body Battery Muster"},
    )


@app.get("/api/ml-insights")
async def api_ml_insights(request: Request):
    user = await require_user(request)
    return await get_ml_insights(user["id"])


@app.get("/api/ml-history")
async def api_ml_history(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    end_date: date | None = Query(default=None),
):
    user = await require_user(request)
    return await get_ml_history(user["id"], days, end_date=end_date)


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


@app.get("/api/ml-status")
async def api_ml_status(request: Request):
    user = await require_user(request)
    return await get_ml_status(user["id"])


class ProfileBody(BaseModel):
    date_of_birth: date | None = None
    sex: str | None = None
    epilepsy_mode: bool | None = None

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v: str | None) -> str | None:
        if v is not None and v not in ("m", "f", "diverse"):
            raise ValueError("sex must be 'm', 'f', or 'diverse'")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date | None) -> date | None:
        if v is not None and v >= date.today():
            raise ValueError("date_of_birth must be in the past")
        return v


@app.patch("/api/profile")
async def api_update_profile(request: Request, body: ProfileBody):
    user = await require_user(request)
    await update_user_profile(
        user["id"], body.date_of_birth, body.sex, body.epilepsy_mode
    )
    return {"ok": True}


class SeizureBody(BaseModel):
    occurred_at: datetime
    duration_seconds: int | None = None
    type: str = "unknown"
    severity: int | None = None
    notes: str | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("focal", "generalized", "unknown"):
            raise ValueError("type must be focal, generalized, or unknown")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 5):
            raise ValueError("severity must be 1–5")
        return v


@app.get("/epilepsy")
async def epilepsy_page(request: Request):
    user = await require_user(request)
    if not user.get("epilepsy_mode"):
        return RedirectResponse("/settings", status_code=303)
    return templates.TemplateResponse(request, "epilepsy.html", {"user": user})


@app.post("/api/seizures")
async def api_log_seizure(request: Request, body: SeizureBody):
    user = await require_user(request)
    id_ = await save_seizure(
        user["id"],
        body.occurred_at,
        body.duration_seconds,
        body.type,
        body.severity,
        body.notes,
    )
    return {"ok": True, "id": id_}


@app.get("/api/seizures")
async def api_get_seizures(request: Request, days: int = 365):
    user = await require_user(request)
    return await get_seizures(user["id"], days)


@app.get("/api/seizures/risk")
async def api_seizure_risk(request: Request):
    user = await require_user(request)
    return await get_seizure_risk(user["id"])
