import logging
from datetime import datetime, timedelta, timezone

import asyncpg
import resend as resend_client
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.db import (
    create_user,
    get_user_by_email,
    increment_failed_login,
    lock_user_until,
    reset_failed_login,
    update_password,
)
from src.deps import (
    DUMMY_HASH,
    hash_password,
    limiter,
    settings,
    templates,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_RESET_SALT = "password-reset"
_RESET_MAX_AGE = 3600
_MAX_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


def _make_reset_token(user_id: int) -> str:
    return URLSafeTimedSerializer(settings.session_secret).dumps(
        user_id, salt=_RESET_SALT
    )


def _verify_reset_token(token: str) -> int | None:
    try:
        user_id = URLSafeTimedSerializer(settings.session_secret).loads(
            token, salt=_RESET_SALT, max_age=_RESET_MAX_AGE
        )
        return int(user_id)
    except (BadSignature, SignatureExpired):
        return None


async def _send_lockout_email(to_email: str) -> None:
    if not settings.resend_api_key:
        logger.warning("lockout mail skipped — RESEND_API_KEY not set")
        return
    resend_client.api_key = settings.resend_api_key
    resend_client.Emails.send(
        {
            "from": settings.resend_from_email,
            "to": to_email,
            "subject": "PulseBase — Konto vorübergehend gesperrt",
            "html": (
                "<p>Dein Konto wurde nach mehreren fehlgeschlagenen Login-Versuchen "
                f"für {_LOCKOUT_MINUTES} Minuten gesperrt.</p>"
                "<p>Falls du das nicht warst, ändere bitte dein Passwort über "
                f"<a href='{settings.app_base_url}/auth/reset-request'>"
                "Passwort zurücksetzen</a>.</p>"
            ),
        }
    )


async def _send_reset_email(to_email: str, token: str) -> None:
    if not settings.resend_api_key:
        logger.warning("reset mail skipped — RESEND_API_KEY not set, token: %s", token)
        return
    resend_client.api_key = settings.resend_api_key
    url = f"{settings.app_base_url}/auth/reset/{token}"
    resend_client.Emails.send(
        {
            "from": settings.resend_from_email,
            "to": to_email,
            "subject": "PulseBase — Passwort zurücksetzen",
            "html": (
                f"<p>Klicke auf diesen Link um dein Passwort zurückzusetzen "
                f"(gültig 1 Stunde):</p><p><a href='{url}'>{url}</a></p>"
            ),
        }
    )


@router.get("/login")
async def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    email: str = Form(),
    password: str = Form(),
):
    user = await get_user_by_email(email)

    if (
        user
        and user["locked_until"]
        and user["locked_until"] > datetime.now(timezone.utc)
    ):
        remaining = (
            int(
                (user["locked_until"] - datetime.now(timezone.utc)).total_seconds() / 60
            )
            + 1
        )
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": f"Account gesperrt. Bitte in {remaining} Minuten erneut versuchen."
            },
            status_code=400,
        )

    password_hash: str = user["password_hash"] if user else DUMMY_HASH
    valid = verify_password(password, password_hash)

    if not user or not valid:
        if user:
            await increment_failed_login(user["id"])
            if user["failed_login_attempts"] + 1 >= _MAX_ATTEMPTS:
                until = datetime.now(timezone.utc) + timedelta(minutes=_LOCKOUT_MINUTES)
                await lock_user_until(user["id"], until)
                await _send_lockout_email(user["email"])
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "E-Mail oder Passwort falsch."},
            status_code=400,
        )

    await reset_failed_login(user["id"])
    request.session.clear()
    request.session["user_id"] = str(user["id"])
    return RedirectResponse("/", status_code=303)


@router.get("/register")
async def register_form(request: Request):
    return templates.TemplateResponse(request, "register.html")


@router.post("/register")
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
    except asyncpg.UniqueViolationError:
        logger.warning("register: duplicate email '%s'", email)
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Diese E-Mail ist bereits registriert."},
            status_code=400,
        )
    request.session.clear()
    request.session["user_id"] = str(user["id"])
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/auth/reset-request")
async def reset_request_form(request: Request):
    return templates.TemplateResponse(request, "reset_request.html")


@router.post("/auth/reset-request")
@limiter.limit("3/hour")
async def reset_request(request: Request, email: str = Form()):
    user = await get_user_by_email(email)
    if user:
        token = _make_reset_token(user["id"])
        await _send_reset_email(email, token)
    return templates.TemplateResponse(
        request,
        "reset_request.html",
        {
            "info": "Falls diese E-Mail registriert ist, erhältst du in Kürze einen Link."
        },
    )


@router.get("/auth/reset/{token}")
async def reset_password_form(request: Request, token: str):
    if not _verify_reset_token(token):
        return templates.TemplateResponse(
            request,
            "reset_request.html",
            {"error": "Link ungültig oder abgelaufen. Bitte neu anfordern."},
            status_code=400,
        )
    return templates.TemplateResponse(request, "reset_password.html", {"token": token})


@router.post("/auth/reset/{token}")
@limiter.limit("5/hour")
async def reset_password(
    request: Request,
    token: str,
    password: str = Form(),
    password_confirm: str = Form(),
):
    user_id = _verify_reset_token(token)
    if not user_id:
        return templates.TemplateResponse(
            request,
            "reset_request.html",
            {"error": "Link ungültig oder abgelaufen. Bitte neu anfordern."},
            status_code=400,
        )
    if password != password_confirm:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {"token": token, "error": "Passwörter stimmen nicht überein."},
            status_code=400,
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {"token": token, "error": "Passwort muss mindestens 8 Zeichen haben."},
            status_code=400,
        )
    await update_password(user_id, hash_password(password))
    return RedirectResponse("/login?reset=1", status_code=303)
