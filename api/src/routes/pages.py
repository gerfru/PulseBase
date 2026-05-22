from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

import src.deps as _deps
from src.db import get_activity_detail

router = APIRouter()

_VALID_METRICS = {
    "steps",
    "sleep",
    "hrv",
    "body-battery",
    "body-battery-custom",
    "physical",
    "autonomic",
    "cognitive",
    "hr-zscore",
    "readiness-rf",
    "hrv-status",
    "hrv-status-custom",
    "training-status",
    "readiness",
    "sleep-score-custom",
    "stress-score-custom",
    "intensity-minutes",
    "training-effect",
    "acwr",
    "training-monotony",
    "spo2-trend",
    "sleep-consistency",
    "running-economy",
    "hrv-recovery",
}


@router.get("/")
async def index(request: Request):
    await _deps.require_user(request)
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/dashboard")
async def dashboard(request: Request):
    user = await _deps.require_user(request)
    return _deps.templates.TemplateResponse(request, "dashboard.html", {"user": user})


@router.get("/settings")
async def settings_page(request: Request):
    user = await _deps.require_user(request)
    return _deps.templates.TemplateResponse(
        request, "settings.html", {"user": user, "today": date.today().isoformat()}
    )


@router.get("/metrics/{name}")
async def metrics_detail_page(request: Request, name: str):
    user = await _deps.require_user(request)
    if name not in _VALID_METRICS:
        return RedirectResponse("/dashboard", status_code=303)
    return _deps.templates.TemplateResponse(
        request, "metrics.html", {"user": user, "metric_name": name}
    )


@router.get("/activity/{activity_id}")
async def activity_detail_page(request: Request, activity_id: int):
    user = await _deps.require_user(request)
    activity = await get_activity_detail(user["id"], activity_id)
    if not activity:
        return RedirectResponse("/dashboard", status_code=303)
    return _deps.templates.TemplateResponse(
        request, "activity.html", {"user": user, "activity": activity}
    )


@router.get("/epilepsy")
async def epilepsy_page(request: Request):
    user = await _deps.require_user(request)
    if not user.get("epilepsy_mode"):
        return RedirectResponse("/settings", status_code=303)
    return _deps.templates.TemplateResponse(request, "epilepsy.html", {"user": user})


# ── ML detail pages (template renders, no data) ───────────────────────────────


@router.get("/ml/anomaly")
async def ml_anomaly_page(request: Request):
    user = await _deps.require_user(request)
    return _deps.templates.TemplateResponse(
        request,
        "ml_insights.html",
        {"user": user, "section": "anomaly", "title": "Ruhepuls-Anomalie"},
    )


@router.get("/ml/readiness")
async def ml_readiness_page(request: Request):
    user = await _deps.require_user(request)
    return _deps.templates.TemplateResponse(
        request,
        "ml_insights.html",
        {"user": user, "section": "readiness", "title": "Readiness-Prognose"},
    )


@router.get("/ml/correlations")
async def ml_correlations_page(request: Request):
    user = await _deps.require_user(request)
    return _deps.templates.TemplateResponse(
        request,
        "ml_insights.html",
        {"user": user, "section": "correlations", "title": "Korrelationen"},
    )


@router.get("/ml/battery")
async def ml_battery_page(request: Request):
    user = await _deps.require_user(request)
    return _deps.templates.TemplateResponse(
        request,
        "ml_insights.html",
        {"user": user, "section": "battery", "title": "Body Battery Muster"},
    )


# ── Public legal pages (no session required) ──────────────────────────────────


@router.get("/privacy")
async def privacy(request: Request):
    return _deps.templates.TemplateResponse(request, "privacy.html")


@router.get("/terms")
async def terms(request: Request):
    return _deps.templates.TemplateResponse(request, "terms.html")


@router.get("/imprint")
async def imprint(request: Request):
    return _deps.templates.TemplateResponse(request, "imprint.html")
