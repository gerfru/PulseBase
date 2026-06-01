import tempfile

import structlog
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

import src.deps as _deps
from src.crypto import (
    fernet_decrypt,
    fernet_encrypt,
    restore_token_dir,
    serialize_token_dir,
)
from src.db import (
    get_user_token,
    save_user_token,
    set_garmin_linked,
    set_garmin_unlinked,
)
from src.deps import _ip_hash, limiter
from src.garmin.client import GarminClient

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/garmin/link")
async def garmin_link_form(request: Request):
    user = await _deps.require_user(request)
    return _deps.templates.TemplateResponse(request, "link_garmin.html", {"user": user})


@router.post("/garmin/link")
@limiter.limit("5/hour")
async def garmin_link(
    request: Request,
    garmin_email: str = Form(),
    garmin_password: str = Form(),
):
    user = await _deps.require_user(request)
    settings = _deps.settings
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            existing = await get_user_token(user["id"], "garmin")
            if existing:
                raw = (
                    fernet_decrypt(existing, settings.fernet_key)
                    if settings.fernet_key
                    else existing
                )
                restore_token_dir(raw, tmpdir)

            client = GarminClient(
                email=garmin_email,
                password=garmin_password,
                token_dir=tmpdir,
            )
            client.connect()
            del garmin_password

            serialized = serialize_token_dir(tmpdir)
            blob = (
                fernet_encrypt(serialized, settings.fernet_key)
                if settings.fernet_key
                else serialized
            )
            await save_user_token(user["id"], "garmin", blob)

        await set_garmin_linked(user["id"], garmin_email)
        logger.info(
            "garmin.link.success", user_id=user["id"], ip_hash=_ip_hash(request)
        )
        return RedirectResponse("/?linked=1", status_code=303)
    except Exception as e:
        logger.error(
            "garmin.link.fail",
            user_id=user["id"],
            reason=type(e).__name__,
            ip_hash=_ip_hash(request),
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
    logger.info("garmin.unlink", user_id=user["id"], ip_hash=_ip_hash(request))
    return RedirectResponse("/", status_code=303)
