import hashlib
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import Request
from starlette.responses import Response

from src.db import increment_failed_login, lock_user_until, reset_failed_login
from src.deps import (
    DUMMY_HASH,
    _ip_hash,
    generate_csrf_token,
    templates,
    verify_password,
)
from src.mail import send_lockout_email

logger = structlog.get_logger(__name__)

_MAX_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


def _lockout_response(user: dict | None, request: Request) -> Response | None:
    if not (
        user
        and user["locked_until"]
        and user["locked_until"] > datetime.now(timezone.utc)
    ):
        return None
    remaining = (
        int((user["locked_until"] - datetime.now(timezone.utc)).total_seconds() / 60)
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


async def _handle_invalid_credentials(
    user: dict | None,
    password: str,
    email: str,
    request: Request,
) -> Response | None:
    password_hash: str = user["password_hash"] if user else DUMMY_HASH
    valid = verify_password(password, password_hash)
    if user and valid:
        return None
    if user:
        new_attempts = await increment_failed_login(user["id"])
        if new_attempts >= _MAX_ATTEMPTS:
            until = datetime.now(timezone.utc) + timedelta(minutes=_LOCKOUT_MINUTES)
            await lock_user_until(user["id"], until)
            await send_lockout_email(user["email"], _LOCKOUT_MINUTES)
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


def _handle_unverified_email(user: dict, request: Request) -> Response | None:
    if user["email_verified_at"]:
        return None
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


async def _establish_session(request: Request, user: dict) -> None:
    await reset_failed_login(user["id"])
    request.session.clear()
    request.session["user_id"] = str(user["id"])
    logger.info("auth.login.success", user_id=user["id"], ip_hash=_ip_hash(request))
