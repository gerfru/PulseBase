from datetime import date

import structlog
from fastapi import APIRouter, Form, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.responses import Response

import src.deps as _deps
from src.auth_tokens import _make_deletion_token, _verify_deletion_token
from src.db import (
    delete_user,
    export_user_data,
    get_user_by_email,
    get_user_by_id,
    set_pending_deletion,
)
from src.deps import (
    UserRow,
    _ip_hash,
    limiter,
    require_user,
    verify_csrf_token,
    verify_password,
)
from src.mail import send_deletion_confirm_email

logger = structlog.get_logger(__name__)
router = APIRouter()


def _settings_error(request: Request, user: UserRow, error: str) -> Response:
    return _deps.templates.TemplateResponse(
        request,
        "settings.html",
        {"user": user, "today": date.today().isoformat(), "delete_error": error},
        status_code=400,
    )


@router.post("/account/delete")
@limiter.limit("3/hour")
async def delete_account(
    request: Request,
    email: str = Form(max_length=320),
    password: str = Form(max_length=128),
    csrf_token: str | None = Form(default=None),
) -> Response:
    user = await require_user(request)

    if not verify_csrf_token(request, csrf_token):
        return _settings_error(request, user, "Ungültige Anfrage. Bitte neu laden.")

    if email != user["email"]:
        return _settings_error(request, user, "E-Mail stimmt nicht überein.")

    user_with_hash = await get_user_by_email(user["email"])
    if not user_with_hash or not verify_password(
        password, user_with_hash["password_hash"]
    ):
        return _settings_error(request, user, "Passwort falsch.")

    await set_pending_deletion(user["id"])
    token = await _make_deletion_token(user["id"])
    sent = await send_deletion_confirm_email(user["email"], token)
    if not sent:
        logger.warning(
            "auth.account.delete.email_not_sent",
            user_id=user["id"],
            confirm_url=f"/account/delete/confirm/{token}",
        )
    logger.info(
        "auth.account.delete.pending", user_id=user["id"], ip_hash=_ip_hash(request)
    )
    return _deps.templates.TemplateResponse(
        request,
        "account_delete_pending.html",
        {"user": user},
    )


@router.get("/account/delete/confirm/{token}")
@limiter.limit("10/hour")
async def confirm_delete_account(request: Request, token: str) -> Response:
    user_id = await _verify_deletion_token(token)
    if not user_id:
        return _deps.templates.TemplateResponse(
            request,
            "account_delete_pending.html",
            {"error": "Link ungültig oder abgelaufen."},
            status_code=400,
        )

    user = await get_user_by_id(user_id)
    if not user:
        return RedirectResponse("/login", status_code=303)

    await delete_user(user_id)
    logger.info("auth.account.delete.confirmed", user_id=user_id)
    request.session.clear()
    return RedirectResponse("/login?deleted=1", status_code=303)


@router.get("/account/export")
@limiter.limit("10/hour")
async def export_account(request: Request) -> Response:
    user = await require_user(request)
    data = await export_user_data(user["id"])
    return JSONResponse(
        content=jsonable_encoder(data),
        headers={
            "Content-Disposition": "attachment; filename=pulsebase-export.json",
            "Cache-Control": "no-store",
        },
    )
