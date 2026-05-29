from datetime import datetime, timedelta, timezone

import asyncpg
import resend as resend_client
import resend.exceptions as resend_exc
import structlog
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.db import (
    create_user,
    get_user_by_email,
    increment_failed_login,
    lock_user_until,
    reset_failed_login,
    save_consent,
    set_email_verified,
    update_password,
)
from src.deps import (
    DUMMY_HASH,
    _get_real_ip,
    hash_password,
    limiter,
    settings,
    templates,
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


async def _send_lockout_email(to_email: str) -> bool:
    if not settings.resend_api_key:
        logger.warning("mail.lockout.skipped", reason="RESEND_API_KEY not set")
        return False
    resend_client.api_key = settings.resend_api_key
    try:
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
        return True
    except resend_exc.ResendError as e:
        logger.warning("mail.lockout.failed", reason=e.message)
        return False
    except Exception:
        logger.exception("mail.lockout.unexpected")
        return False


async def _send_reset_email(to_email: str, token: str) -> bool:
    if not settings.resend_api_key:
        logger.warning("mail.reset.skipped", reason="RESEND_API_KEY not set")
        return False
    resend_client.api_key = settings.resend_api_key
    url = f"{settings.app_base_url}/auth/reset/{token}"
    try:
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
        return True
    except resend_exc.ResendError as e:
        logger.warning("mail.reset.failed", reason=e.message)
        return False
    except Exception:
        logger.exception("mail.reset.unexpected")
        return False


async def _send_verify_email(to_email: str, token: str) -> bool:
    if not settings.resend_api_key:
        logger.warning("mail.verify.skipped", reason="RESEND_API_KEY not set")
        return False
    resend_client.api_key = settings.resend_api_key
    url = f"{settings.app_base_url}/auth/verify/{token}"
    try:
        resend_client.Emails.send(
            {
                "from": settings.resend_from_email,
                "to": to_email,
                "subject": "PulseBase — E-Mail-Adresse bestätigen",
                "html": (
                    "<p>Klicke auf diesen Link um deine E-Mail-Adresse zu bestätigen "
                    f"(gültig 24 Stunden):</p><p><a href='{url}'>{url}</a></p>"
                ),
            }
        )
        return True
    except resend_exc.ResendError as e:
        logger.warning("mail.verify.failed", reason=e.message)
        return False
    except Exception:
        logger.exception("mail.verify.unexpected")
        return False


@router.get("/login")
async def login_form(request: Request) -> Response:
    return templates.TemplateResponse(request, "login.html")


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    email: str = Form(),
    password: str = Form(),
) -> Response:
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
            ip=_get_real_ip(request),
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
        logger.warning(
            "auth.login.fail",
            reason="bad_credentials",
            email=email,
            ip=_get_real_ip(request),
        )
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "E-Mail oder Passwort falsch."},
            status_code=400,
        )

    if not user["email_verified_at"]:
        logger.warning(
            "auth.login.fail",
            reason="unverified",
            user_id=user["id"],
            ip=_get_real_ip(request),
        )
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": "Bitte bestätige zuerst deine E-Mail-Adresse.",
                "show_resend": True,
            },
            status_code=400,
        )

    await reset_failed_login(user["id"])
    request.session.clear()
    request.session["user_id"] = str(user["id"])
    logger.info("auth.login.success", user_id=user["id"], ip=_get_real_ip(request))
    return RedirectResponse("/", status_code=303)


@router.get("/register")
async def register_form(request: Request) -> Response:
    return templates.TemplateResponse(request, "register.html")


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
) -> Response:
    if not consent_health:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Bitte stimme der Verarbeitung deiner Gesundheitsdaten zu."},
            status_code=400,
        )
    if not consent_terms:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Bitte akzeptiere die Nutzungsbedingungen."},
            status_code=400,
        )
    if not consent_age:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Du musst mindestens 16 Jahre alt sein, um PulseBase zu nutzen."},
            status_code=400,
        )
    email = email.lower().strip()
    if not (1 <= len(name.strip()) <= 100):
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Name muss 1–100 Zeichen haben."},
            status_code=400,
        )
    if password != password_confirm:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Passwörter stimmen nicht überein."},
            status_code=400,
        )
    if len(password) < 12:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Passwort muss mindestens 12 Zeichen haben."},
            status_code=400,
        )
    try:
        password_hash = hash_password(password)
        user = await create_user(name, email, password_hash)
    except asyncpg.UniqueViolationError:
        logger.warning("auth.register.fail", reason="duplicate_email")
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Diese E-Mail ist bereits registriert."},
            status_code=400,
        )
    ip = request.client.host if request.client else None
    await save_consent(user["id"], "health_data", True, ip)
    await save_consent(user["id"], "terms", True, ip)
    await save_consent(user["id"], "age_16plus", True, ip)
    logger.info("auth.register.success", user_id=user["id"], ip=_get_real_ip(request))
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
async def reset_password_form(request: Request, token: str) -> Response:
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
) -> Response:
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
    if len(password) < 12:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {"token": token, "error": "Passwort muss mindestens 12 Zeichen haben."},
            status_code=400,
        )
    await update_password(user_id, hash_password(password))
    request.session.clear()
    logger.info("auth.password_reset.success", user_id=user_id)
    return RedirectResponse("/login?reset=1", status_code=303)
