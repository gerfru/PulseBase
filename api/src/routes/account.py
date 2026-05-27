from datetime import date

import structlog
from fastapi import APIRouter, Form, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, RedirectResponse

import src.deps as _deps
from src.db import (
    delete_user,
    export_user_data,
    get_user_by_email,
    get_user_by_id,
)
from src.deps import _get_real_ip, limiter, verify_password

logger = structlog.get_logger(__name__)
router = APIRouter()


def _settings_error(request: Request, user: dict, error: str):
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
):
    user_id = int(request.session.get("user_id", 0))
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    user = await get_user_by_id(user_id)
    if not user:
        return RedirectResponse("/login", status_code=303)

    if email != user["email"]:
        return _settings_error(request, user, "E-Mail stimmt nicht überein.")

    user_with_hash = await get_user_by_email(user["email"])
    if not user_with_hash or not verify_password(
        password, user_with_hash["password_hash"]
    ):
        return _settings_error(request, user, "Passwort falsch.")

    await delete_user(user_id)
    logger.info("auth.account.delete", user_id=user_id, ip=_get_real_ip(request))
    request.session.clear()
    return RedirectResponse("/login?deleted=1", status_code=303)


@router.get("/account/export")
@limiter.limit("10/hour")
async def export_account(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    data = await export_user_data(int(user_id))
    return JSONResponse(
        content=jsonable_encoder(data),
        headers={"Content-Disposition": "attachment; filename=pulsebase-export.json"},
    )
