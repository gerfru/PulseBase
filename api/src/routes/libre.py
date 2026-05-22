import json
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

import src.deps as _deps
from src.crypto import fernet_encrypt
from src.db import save_user_token, set_libre_linked, set_libre_unlinked
from src.deps import _get_real_ip

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/libre/link")
async def libre_link_form(request: Request):
    user = await _deps.require_user(request)
    return _deps.templates.TemplateResponse(request, "link_libre.html", {"user": user})


@router.post("/libre/link")
async def libre_link(
    request: Request,
    libre_email: str = Form(),
    libre_password: str = Form(),
):
    from libre.client import LibreAuthError
    from libre.client import authenticate as libre_authenticate

    user = await _deps.require_user(request)
    settings = _deps.settings
    try:
        client = libre_authenticate(
            libre_email,
            libre_password,
            token_dir=f"/app/tokens/{user['id']}/libre",
        )
        token_json = json.dumps({"token": client.token}).encode()
        blob = (
            fernet_encrypt(token_json, settings.fernet_key)
            if settings.fernet_key
            else token_json
        )
        await save_user_token(user["id"], "libre", blob)
        await set_libre_linked(user["id"], libre_email)
        logger.info(
            "libre.link.success user_id=%s ip=%s", user["id"], _get_real_ip(request)
        )
        return RedirectResponse("/dashboard", status_code=303)
    except LibreAuthError:
        logger.warning(
            "libre.link.fail reason=auth user_id=%s ip=%s",
            user["id"],
            _get_real_ip(request),
        )
        return _deps.templates.TemplateResponse(
            request,
            "link_libre.html",
            {
                "user": user,
                "error": "Login fehlgeschlagen. Bitte Zugangsdaten prüfen und sicherstellen, dass du als Follower akzeptiert wurdest.",
            },
            status_code=400,
        )
    except Exception as e:
        logger.error(
            "libre.link.fail reason=%s user_id=%s ip=%s",
            type(e).__name__,
            user["id"],
            _get_real_ip(request),
        )
        return _deps.templates.TemplateResponse(
            request,
            "link_libre.html",
            {
                "user": user,
                "error": "Verbindung fehlgeschlagen. Bitte erneut versuchen.",
            },
            status_code=400,
        )


@router.post("/libre/unlink")
async def libre_unlink(request: Request):
    user = await _deps.require_user(request)
    await set_libre_unlinked(user["id"])
    token_dir = Path(f"/app/tokens/{user['id']}/libre")
    if token_dir.exists():
        shutil.rmtree(token_dir)
    logger.info("libre.unlink user_id=%s ip=%s", user["id"], _get_real_ip(request))
    return RedirectResponse("/libre/link", status_code=303)
