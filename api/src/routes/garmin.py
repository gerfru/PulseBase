import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

import src.deps as _deps
from src.db import set_garmin_linked, set_garmin_unlinked
from src.garmin.client import GarminClient

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/garmin/link")
async def garmin_link_form(request: Request):
    user = await _deps.require_user(request)
    return _deps.templates.TemplateResponse(request, "link_garmin.html", {"user": user})


@router.post("/garmin/link")
async def garmin_link(
    request: Request,
    garmin_email: str = Form(),
    garmin_password: str = Form(),
):
    user = await _deps.require_user(request)
    try:
        client = GarminClient(
            email=garmin_email,
            password=garmin_password,
            token_dir=f"/app/tokens/{user['id']}",
        )
        client.connect()
        del garmin_password
        await set_garmin_linked(user["id"], garmin_email)
        logger.info("Garmin verknüpft für User %s", user["id"])
        return RedirectResponse("/?linked=1", status_code=303)
    except Exception as e:
        logger.error(
            "Garmin Login fehlgeschlagen für User %s: %s", user["id"], type(e).__name__
        )
        return _deps.templates.TemplateResponse(
            request,
            "link_garmin.html",
            {"user": user, "error": "Login fehlgeschlagen. Bitte Zugangsdaten prüfen."},
            status_code=400,
        )


@router.post("/garmin/unlink")
async def garmin_unlink(request: Request):
    user = await _deps.require_user(request)
    await set_garmin_unlinked(user["id"])
    logger.info("Garmin Verknüpfung entfernt für User %s", user["id"])
    return RedirectResponse("/", status_code=303)
