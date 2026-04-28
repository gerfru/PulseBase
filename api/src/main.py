import logging
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import bcrypt
from starlette.middleware.sessions import SessionMiddleware

from src.db import (
    Settings,
    create_user,
    get_user_by_email,
    get_user_by_id,
    set_garmin_linked,
    set_garmin_unlinked,
    get_recent_activities,
    get_daily_summaries,
    get_sleep_sessions,
    get_latest_hrv,
    get_hrv_trend,
    get_latest_training_status,
)
from src.garmin.client import GarminClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


app = FastAPI(title="Garmin Dashboard API")
app.add_middleware(
    SessionMiddleware, secret_key=settings.session_secret, https_only=True
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


# ── Öffentliche Routen ────────────────────────────────────────────────────────


@app.get("/login")
async def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.post("/login")
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
        logger.error(f"Garmin Login fehlgeschlagen: {e}")
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


@app.get("/api/activities")
async def api_activities(request: Request, limit: int = 10):
    user = await require_user(request)
    return await get_recent_activities(user["id"], limit=limit)


@app.get("/api/daily")
async def api_daily(request: Request, days: int = 30):
    user = await require_user(request)
    return await get_daily_summaries(user["id"], days=days)


@app.get("/api/sleep")
async def api_sleep(request: Request, days: int = 14):
    user = await require_user(request)
    return await get_sleep_sessions(user["id"], limit=days)


@app.get("/api/hrv")
async def api_hrv(request: Request):
    user = await require_user(request)
    return await get_latest_hrv(user["id"])


@app.get("/api/hrv/trend")
async def api_hrv_trend(request: Request, days: int = 30):
    user = await require_user(request)
    return await get_hrv_trend(user["id"], days=days)


@app.get("/api/training-status")
async def api_training_status(request: Request):
    user = await require_user(request)
    return await get_latest_training_status(user["id"])
