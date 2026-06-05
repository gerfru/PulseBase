import hashlib

import asyncpg
import structlog
from fastapi import APIRouter, Form, Request
from pydantic import TypeAdapter, ValidationError
from pydantic.networks import EmailStr
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from src.auth_helpers import (
    _establish_session,
    _handle_invalid_credentials,
    _handle_unverified_email,
    _lockout_response,
)
from src.auth_tokens import (
    _make_reset_token,
    _make_verify_token,
    _verify_email_token,
    _verify_reset_token,
)
from src.mail import send_reset_email, send_verify_email
from src.db import (
    clear_reset_token,
    create_user,
    get_user_by_email,
    save_consent,
    set_email_verified,
    update_password,
)
from src.deps import (
    _ip_hash,
    generate_csrf_token,
    hash_password,
    limiter,
    templates,
    verify_csrf_token,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/login")
async def login_form(request: Request) -> Response:
    return templates.TemplateResponse(
        request, "login.html", {"csrf_token": generate_csrf_token(request)}
    )


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    email: str = Form(max_length=320),
    password: str = Form(max_length=128),
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
    lockout = _lockout_response(user, request)
    if lockout:
        return lockout
    if resp := await _handle_invalid_credentials(user, password, email, request):
        return resp
    if user is None:
        raise RuntimeError("user_record missing after credential check")
    if resp := _handle_unverified_email(user, request):
        return resp
    await _establish_session(request, user)
    return RedirectResponse("/", status_code=303)


def _register_error(request: Request, msg: str) -> Response:
    return templates.TemplateResponse(
        request,
        "register.html",
        {"error": msg, "csrf_token": generate_csrf_token(request)},
        status_code=400,
    )


def _validate_register_form(
    request: Request,
    name: str,
    email: str,
    password: str,
    password_confirm: str,
    consent_health: str,
    consent_terms: str,
    consent_age: str,
    csrf_token: str | None,
) -> Response | None:
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
    return None


@router.get("/register")
async def register_form(request: Request) -> Response:
    return templates.TemplateResponse(
        request, "register.html", {"csrf_token": generate_csrf_token(request)}
    )


@router.post("/register")
@limiter.limit("5/minute")
async def register(
    request: Request,
    name: str = Form(max_length=100),
    email: str = Form(max_length=320),
    password: str = Form(max_length=128),
    password_confirm: str = Form(max_length=128),
    consent_health: str = Form(default=""),
    consent_terms: str = Form(default=""),
    consent_age: str = Form(default=""),
    csrf_token: str | None = Form(default=None),
) -> Response:
    email = email.lower().strip()
    if resp := _validate_register_form(
        request,
        name,
        email,
        password,
        password_confirm,
        consent_health,
        consent_terms,
        consent_age,
        csrf_token,
    ):
        return resp
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
    sent = await send_verify_email(email, token)
    return RedirectResponse(
        "/login?verify=sent" if sent else "/login?verify=failed", status_code=303
    )


@router.post("/logout")
async def logout(
    request: Request, csrf_token: str | None = Form(default=None)
) -> Response:
    if not verify_csrf_token(request, csrf_token):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Ungültige Anfrage.", "csrf_token": generate_csrf_token(request)},
            status_code=403,
        )
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/auth/resend-verify")
async def resend_verify_form(request: Request) -> Response:
    return templates.TemplateResponse(
        request, "verify_pending.html", {"csrf_token": generate_csrf_token(request)}
    )


@router.post("/auth/resend-verify")
@limiter.limit("3/hour")
async def resend_verify(
    request: Request,
    email: str = Form(max_length=320),
    csrf_token: str | None = Form(default=None),
) -> Response:
    if not verify_csrf_token(request, csrf_token):
        return templates.TemplateResponse(
            request,
            "verify_pending.html",
            {"error": "Ungültige Anfrage.", "csrf_token": generate_csrf_token(request)},
            status_code=400,
        )
    user = await get_user_by_email(email)
    sent = False
    if user and not user["email_verified_at"]:
        token = _make_verify_token(user["id"])
        sent = await send_verify_email(email, token)
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
    return templates.TemplateResponse(
        request, "reset_request.html", {"csrf_token": generate_csrf_token(request)}
    )


@router.post("/auth/reset-request")
@limiter.limit("3/hour")
async def reset_request(
    request: Request,
    email: str = Form(max_length=320),
    csrf_token: str | None = Form(default=None),
) -> Response:
    if not verify_csrf_token(request, csrf_token):
        return templates.TemplateResponse(
            request,
            "reset_request.html",
            {"error": "Ungültige Anfrage.", "csrf_token": generate_csrf_token(request)},
            status_code=400,
        )
    user = await get_user_by_email(email)
    if user:
        token = await _make_reset_token(user["id"])
        await send_reset_email(email, token)
    return templates.TemplateResponse(
        request,
        "reset_request.html",
        {
            "info": "Falls diese E-Mail registriert ist, erhältst du in Kürze einen Link.",
            "csrf_token": generate_csrf_token(request),
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
    request.session["reset_token_hash"] = hashlib.sha256(token.encode()).hexdigest()
    return templates.TemplateResponse(
        request,
        "reset_password.html",
        {"token": token, "csrf_token": generate_csrf_token(request)},
    )


def _validate_reset_request(
    request: Request,
    token: str,
    password: str,
    password_confirm: str,
    csrf_token: str | None,
) -> Response | None:
    if not verify_csrf_token(request, csrf_token):
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {"token": token, "error": "Ungültige Anfrage. Bitte neu laden."},
            status_code=403,
        )
    expected_hash = hashlib.sha256(token.encode()).hexdigest()
    if request.session.pop("reset_token_hash", None) != expected_hash:
        return templates.TemplateResponse(
            request,
            "reset_request.html",
            {"error": "Sitzung abgelaufen. Bitte neu anfordern."},
            status_code=403,
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
    return None


@router.post("/auth/reset/{token}")
@limiter.limit("5/hour")
async def reset_password(
    request: Request,
    token: str,
    password: str = Form(max_length=128),
    password_confirm: str = Form(max_length=128),
    csrf_token: str | None = Form(default=None),
) -> Response:
    if resp := _validate_reset_request(
        request, token, password, password_confirm, csrf_token
    ):
        return resp
    user_id = await _verify_reset_token(token)
    if not user_id:
        return templates.TemplateResponse(
            request,
            "reset_request.html",
            {"error": "Link ungültig oder abgelaufen. Bitte neu anfordern."},
            status_code=400,
        )
    await update_password(user_id, hash_password(password))
    await clear_reset_token(user_id)
    request.session.clear()
    logger.info("auth.password_reset.success", user_id=user_id)
    return RedirectResponse("/login?reset=1", status_code=303)
