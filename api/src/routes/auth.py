import logging

import asyncpg
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from src.db import create_user, get_user_by_email
from src.deps import (
    DUMMY_HASH,
    hash_password,
    limiter,
    templates,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/login")
async def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    email: str = Form(),
    password: str = Form(),
):
    user = await get_user_by_email(email)
    password_hash: str = user["password_hash"] if user else DUMMY_HASH
    valid = verify_password(password, password_hash)
    if not user or not valid:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "E-Mail oder Passwort falsch."},
            status_code=400,
        )
    request.session.clear()
    request.session["user_id"] = str(user["id"])
    return RedirectResponse("/", status_code=303)


@router.get("/register")
async def register_form(request: Request):
    return templates.TemplateResponse(request, "register.html")


@router.post("/register")
@limiter.limit("5/minute")
async def register(
    request: Request,
    name: str = Form(),
    email: str = Form(),
    password: str = Form(),
    password_confirm: str = Form(),
):
    if password != password_confirm:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Passwörter stimmen nicht überein."},
            status_code=400,
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Passwort muss mindestens 8 Zeichen haben."},
            status_code=400,
        )
    try:
        password_hash = hash_password(password)
        user = await create_user(name, email, password_hash)
    except asyncpg.UniqueViolationError:
        logger.warning("register: duplicate email '%s'", email)
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Diese E-Mail ist bereits registriert."},
            status_code=400,
        )
    request.session.clear()
    request.session["user_id"] = str(user["id"])
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
