from datetime import date

import structlog
from fastapi import APIRouter, Form, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.responses import Response

import src.deps as _deps
from src.db import (
    delete_user,
    export_user_data,
    get_user_by_email,
)
from src.deps import (
    UserRow,
    _ip_hash,
    limiter,
    require_user,
    verify_csrf_token,
    verify_password,
)

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
    email: str = Form(),
    password: str = Form(),
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

    await delete_user(user["id"])
    logger.info("auth.account.delete", user_id=user["id"], ip_hash=_ip_hash(request))
    request.session.clear()
    return RedirectResponse("/login?deleted=1", status_code=303)


@router.get("/account/export")
@limiter.limit("10/hour")
async def export_account(request: Request) -> Response:
    user = await require_user(request)
    data = await export_user_data(user["id"])
    return JSONResponse(
        content=jsonable_encoder(data),
        headers={"Content-Disposition": "attachment; filename=pulsebase-export.json"},
    )
