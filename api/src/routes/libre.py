import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

import src.deps as _deps
from src.db import set_libre_linked, set_libre_unlinked

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
    try:
        libre_authenticate(
            libre_email,
            libre_password,
            token_dir=f"/app/tokens/{user['id']}/libre",
        )
        await set_libre_linked(user["id"], libre_email)
        logger.info("LibreLinkUp verknüpft für User %s", user["id"])
        return RedirectResponse("/dashboard", status_code=303)
    except LibreAuthError as e:
        logger.warning("LibreLinkUp Login fehlgeschlagen User %s: %s", user["id"], e)
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
        logger.error("LibreLinkUp Fehler User %s: %s", user["id"], type(e).__name__)
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
    logger.info("LibreLinkUp Verknüpfung + Daten entfernt für User %s", user["id"])
    return RedirectResponse("/libre/link", status_code=303)
