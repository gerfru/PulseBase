import json
import shutil
import tempfile
from pathlib import Path

import structlog
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response

import src.deps as _deps
from fastapi import HTTPException
from src.crypto import fernet_encrypt
from src.db import save_user_token, set_libre_linked, set_libre_unlinked
from src.deps import _ip_hash, generate_csrf_token, limiter, verify_csrf_token

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/libre/link")
async def libre_link_form(request: Request) -> Response:
    user = await _deps.require_user(request)
    return _deps.templates.TemplateResponse(
        request,
        "link_libre.html",
        {"user": user, "csrf_token": generate_csrf_token(request)},
    )


@router.post("/libre/link")
@limiter.limit("5/hour")
async def libre_link(
    request: Request,
    libre_email: str = Form(),
    libre_password: str = Form(),
    csrf_token: str | None = Form(default=None),
) -> Response:
    from libre.client import LibreAuthError
    from libre.client import authenticate as libre_authenticate

    user = await _deps.require_user(request)
    if not verify_csrf_token(request, csrf_token):
        return _deps.templates.TemplateResponse(
            request,
            "link_libre.html",
            {
                "user": user,
                "error": "Ungültige Anfrage. Bitte neu laden.",
                "csrf_token": generate_csrf_token(request),
            },
            status_code=403,
        )
    settings = _deps.settings
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = libre_authenticate(
                libre_email,
                libre_password,
                token_dir=tmpdir,
            )
            token_json = json.dumps({"token": client.token}).encode()
            blob = fernet_encrypt(token_json, settings.fernet_key)
        await save_user_token(user["id"], "libre", blob)
        await set_libre_linked(user["id"], libre_email)
        logger.info("libre.link.success", user_id=user["id"], ip_hash=_ip_hash(request))
        return RedirectResponse("/dashboard", status_code=303)
    except LibreAuthError:
        logger.warning(
            "libre.link.fail",
            reason="auth",
            user_id=user["id"],
            ip_hash=_ip_hash(request),
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
            "libre.link.fail",
            reason=type(e).__name__,
            user_id=user["id"],
            ip_hash=_ip_hash(request),
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
async def libre_unlink(
    request: Request, csrf_token: str | None = Form(default=None)
) -> Response:
    user = await _deps.require_user(request)
    if not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Ungültige Anfrage.")
    await set_libre_unlinked(user["id"])
    token_dir = Path(f"/app/tokens/{user['id']}/libre")
    if token_dir.exists():
        shutil.rmtree(token_dir)
    logger.info("libre.unlink", user_id=user["id"], ip_hash=_ip_hash(request))
    return RedirectResponse("/libre/link", status_code=303)
