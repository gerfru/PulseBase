import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import asyncpg
import resend as resend_client
import resend.exceptions as resend_exc
import structlog
from fastapi import APIRouter, Form, Request
from pydantic import TypeAdapter, ValidationError
from pydantic.networks import EmailStr
from fastapi.responses import RedirectResponse
from starlette.responses import Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.db import (
    clear_reset_token,
    create_user,
    get_reset_token_user_id,
    get_user_by_email,
    increment_failed_login,
    lock_user_until,
    reset_failed_login,
    save_consent,
    save_reset_token,
    set_email_verified,
    update_password,
)
from src.deps import (
    DUMMY_HASH,
    _ip_hash,
    generate_csrf_token,
    hash_password,
    limiter,
    settings,
    templates,
    verify_csrf_token,
    verify_password,
)

logger = structlog.get_logger(__name__)
router = APIRouter()

_RESET_SALT = "password-reset"
_RESET_MAX_AGE = 3600
_VERIFY_SALT = "email-verify"
_VERIFY_MAX_AGE = 86400  # 24 hours
_MAX_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


async def _make_reset_token(user_id: int) -> str:
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=_RESET_MAX_AGE)
    await save_reset_token(user_id, token_hash, expires_at)
    return raw


async def _verify_reset_token(token: str) -> int | None:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return await get_reset_token_user_id(token_hash)


def _make_verify_token(user_id: int) -> str:
    return URLSafeTimedSerializer(settings.session_secret).dumps(
        user_id, salt=_VERIFY_SALT
    )


def _verify_email_token(token: str) -> int | None:
    try:
        user_id = URLSafeTimedSerializer(settings.session_secret).loads(
            token, salt=_VERIFY_SALT, max_age=_VERIFY_MAX_AGE
        )
        return int(user_id)
    except (BadSignature, SignatureExpired):
        return None


async def _send_email(to: str, subject: str, html: str, log_key: str) -> bool:
    if not settings.resend_api_key:
        logger.warning(f"mail.{log_key}.skipped", reason="RESEND_API_KEY not set")
        return False
    resend_client.api_key = settings.resend_api_key
    try:
        resend_client.Emails.send(
            {
                "from": settings.resend_from_email,
                "to": to,
                "subject": subject,
                "html": html,
            }
        )
        return True
    except resend_exc.ResendError as e:
        logger.warning(f"mail.{log_key}.failed", reason=e.message)
        return False
    except Exception:
        logger.exception(f"mail.{log_key}.unexpected")
        return False


async def _send_lockout_email(to_email: str) -> bool:
    return await _send_email(
        to=to_email,
        subject="PulseBase — Konto vorübergehend gesperrt",
        html=(
            "<p>Dein Konto wurde nach mehreren fehlgeschlagenen Login-Versuchen "
            f"für {_LOCKOUT_MINUTES} Minuten gesperrt.</p>"
            "<p>Falls du das nicht warst, ändere bitte dein Passwort über "
            f"<a href='{settings.app_base_url}/auth/reset-request'>"
            "Passwort zurücksetzen</a>.</p>"
        ),
        log_key="lockout",
    )


async def _send_reset_email(to_email: str, token: str) -> bool:
    url = f"{settings.app_base_url}/auth/reset/{token}"
    return await _send_email(
        to=to_email,
        subject="PulseBase — Passwort zurücksetzen",
        html=(
            f"<p>Klicke auf diesen Link um dein Passwort zurückzusetzen "
            f"(gültig 1 Stunde):</p><p><a href='{url}'>{url}</a></p>"
        ),
        log_key="reset",
    )


async def _send_verify_email(to_email: str, token: str) -> bool:
    url = f"{settings.app_base_url}/auth/verify/{token}"
    return await _send_email(
        to=to_email,
        subject="PulseBase — E-Mail-Adresse bestätigen",
        html=(
            "<p>Klicke auf diesen Link um deine E-Mail-Adresse zu bestätigen "
            f"(gültig 24 Stunden):</p><p><a href='{url}'>{url}</a></p>"
        ),
        log_key="verify",
    )


@router.get("/login")
async def login_form(request: Request) -> Response:
    return templates.TemplateResponse(
        request, "login.html", {"csrf_token": generate_csrf_token(request)}
    )


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    email: str = Form(),
    password: str = Form(),
    csrf_token: str | None = Form(default=None),
) -> Response:
    if not verify_csrf_token(request, csrf_token):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Ungültige Anfrage.", "csrf_token": generate_csrf_token(request)},
            status_code=400,
        )
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
        logger.warning(
            "auth.login.fail",
            reason="locked",
            user_id=user["id"],
            ip_hash=_ip_hash(request),
        )
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": f"Account gesperrt. Bitte in {remaining} Minuten erneut versuchen.",
                "csrf_token": generate_csrf_token(request),
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
        logger.warning(
            "auth.login.fail",
            reason="bad_credentials",
            email_hash=hashlib.sha256(email.encode()).hexdigest()[:12],
            ip_hash=_ip_hash(request),
        )
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": "E-Mail oder Passwort falsch.",
                "csrf_token": generate_csrf_token(request),
            },
            status_code=400,
        )

    if not user["email_verified_at"]:
        logger.warning(
            "auth.login.fail",
            reason="unverified",
            user_id=user["id"],
            ip_hash=_ip_hash(request),
        )
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": "Bitte bestätige zuerst deine E-Mail-Adresse.",
                "show_resend": True,
                "csrf_token": generate_csrf_token(request),
            },
            status_code=400,
        )

    await reset_failed_login(user["id"])
    request.session.clear()
    request.session["user_id"] = str(user["id"])
    logger.info("auth.login.success", user_id=user["id"], ip_hash=_ip_hash(request))
    return RedirectResponse("/", status_code=303)


def _register_error(request: Request, msg: str) -> Response:
    return templates.TemplateResponse(
        request,
        "register.html",
        {"error": msg, "csrf_token": generate_csrf_token(request)},
        status_code=400,
    )


@router.get("/register")
async def register_form(request: Request) -> Response:
    return templates.TemplateResponse(
        request, "register.html", {"csrf_token": generate_csrf_token(request)}
    )


@router.post("/register")
@limiter.limit("5/minute")
async def register(
    request: Request,
    name: str = Form(),
    email: str = Form(),
    password: str = Form(),
    password_confirm: str = Form(),
    consent_health: str = Form(default=""),
    consent_terms: str = Form(default=""),
    consent_age: str = Form(default=""),
    csrf_token: str | None = Form(default=None),
) -> Response:
    if not verify_csrf_token(request, csrf_token):
        return _register_error(request, "Ungültige Anfrage.")
    if not consent_health:
        return _register_error(
            request, "Bitte stimme der Verarbeitung deiner Gesundheitsdaten zu."
        )
    if not consent_terms:
        return _register_error(request, "Bitte akzeptiere die Nutzungsbedingungen.")
    if not consent_age:
        return _register_error(
            request, "Du musst mindestens 16 Jahre alt sein, um PulseBase zu nutzen."
        )
    email = email.lower().strip()
    try:
        TypeAdapter(EmailStr).validate_python(email)
    except ValidationError:
        return _register_error(request, "Bitte gib eine gültige E-Mail-Adresse ein.")
    if not (1 <= len(name.strip()) <= 100):
        return _register_error(request, "Name muss 1–100 Zeichen haben.")
    if password != password_confirm:
        return _register_error(request, "Passwörter stimmen nicht überein.")
    if len(password) < 12:
        return _register_error(request, "Passwort muss mindestens 12 Zeichen haben.")
    try:
        password_hash = hash_password(password)
        user = await create_user(name, email, password_hash)
    except asyncpg.UniqueViolationError:
        logger.warning("auth.register.fail", reason="duplicate_email")
        return _register_error(request, "Diese E-Mail ist bereits registriert.")
    ip_hash = _ip_hash(request)
    await save_consent(user["id"], "health_data", True, ip_hash)
    await save_consent(user["id"], "terms", True, ip_hash)
    await save_consent(user["id"], "age_16plus", True, ip_hash)
    logger.info("auth.register.success", user_id=user["id"], ip_hash=_ip_hash(request))
    token = _make_verify_token(user["id"])
    sent = await _send_verify_email(email, token)
    return RedirectResponse(
        "/login?verify=sent" if sent else "/login?verify=failed", status_code=303
    )


@router.post("/logout")
async def logout(request: Request) -> Response:
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/auth/resend-verify")
async def resend_verify_form(request: Request) -> Response:
    return templates.TemplateResponse(request, "verify_pending.html")


@router.post("/auth/resend-verify")
@limiter.limit("3/hour")
async def resend_verify(request: Request, email: str = Form()) -> Response:
    user = await get_user_by_email(email)
    sent = False
    if user and not user["email_verified_at"]:
        token = _make_verify_token(user["id"])
        sent = await _send_verify_email(email, token)
    if user and not user["email_verified_at"] and not sent:
        ctx = {
            "warning": "E-Mail konnte nicht gesendet werden. Bitte später erneut versuchen."
        }
    else:
        ctx = {
            "info": "Falls diese E-Mail registriert und unbestätigt ist, erhältst du in Kürze einen Link."
        }
    return templates.TemplateResponse(request, "verify_pending.html", ctx)


@router.get("/auth/verify/{token}")
async def verify_email(request: Request, token: str) -> Response:
    user_id = _verify_email_token(token)
    if not user_id:
        return templates.TemplateResponse(
            request,
            "verify_pending.html",
            {"error": "Link ungültig oder abgelaufen. Bitte neu anfordern."},
            status_code=400,
        )
    await set_email_verified(user_id)
    return RedirectResponse("/login?verified=1", status_code=303)


@router.get("/auth/reset-request")
async def reset_request_form(request: Request) -> Response:
    return templates.TemplateResponse(request, "reset_request.html")


@router.post("/auth/reset-request")
@limiter.limit("3/hour")
async def reset_request(request: Request, email: str = Form()) -> Response:
    user = await get_user_by_email(email)
    if user:
        token = await _make_reset_token(user["id"])
        await _send_reset_email(email, token)
    return templates.TemplateResponse(
        request,
        "reset_request.html",
        {
            "info": "Falls diese E-Mail registriert ist, erhältst du in Kürze einen Link."
        },
    )


@router.get("/auth/reset/{token}")
async def reset_password_form(request: Request, token: str) -> Response:
    if not await _verify_reset_token(token):
        return templates.TemplateResponse(
            request,
            "reset_request.html",
            {"error": "Link ungültig oder abgelaufen. Bitte neu anfordern."},
            status_code=400,
        )
    return templates.TemplateResponse(
        request,
        "reset_password.html",
        {"token": token, "csrf_token": generate_csrf_token(request)},
    )


@router.post("/auth/reset/{token}")
@limiter.limit("5/hour")
async def reset_password(
    request: Request,
    token: str,
    password: str = Form(),
    password_confirm: str = Form(),
    csrf_token: str | None = Form(default=None),
) -> Response:
    if not verify_csrf_token(request, csrf_token):
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {"token": token, "error": "Ungültige Anfrage. Bitte neu laden."},
            status_code=403,
        )
    user_id = await _verify_reset_token(token)
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
    if len(password) < 12:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {"token": token, "error": "Passwort muss mindestens 12 Zeichen haben."},
            status_code=400,
        )
    await update_password(user_id, hash_password(password))
    await clear_reset_token(user_id)
    request.session.clear()
    logger.info("auth.password_reset.success", user_id=user_id)
    return RedirectResponse("/login?reset=1", status_code=303)
