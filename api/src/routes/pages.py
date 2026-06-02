from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response

import src.deps as _deps
from src.db import get_activity_detail
from src.deps import generate_csrf_token

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
    "training-monotony",
    "spo2-trend",
    "sleep-consistency",
    "running-economy",
    "hrv-recovery",
    "recovery",
    "battery-pattern",
    "correlations",
}


@router.get("/")
async def index(request: Request) -> Response:
    await _deps.require_user(request)
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/dashboard")
async def dashboard(request: Request) -> Response:
    user = await _deps.require_user(request)
    return _deps.templates.TemplateResponse(
        request,
        "dashboard.html",
        {"user": user, "csrf_token": generate_csrf_token(request)},
    )


@router.get("/settings")
async def settings_page(request: Request) -> Response:
    user = await _deps.require_user(request)
    return _deps.templates.TemplateResponse(
        request,
        "settings.html",
        {
            "user": user,
            "today": date.today().isoformat(),
            "csrf_token": generate_csrf_token(request),
        },
    )


@router.get("/help")
async def help_page(request: Request) -> Response:
    user = await _deps.require_user(request)
    return _deps.templates.TemplateResponse(request, "help.html", {"user": user})


@router.get("/metrics")
async def metrics_overview_page(request: Request) -> Response:
    user = await _deps.require_user(request)
    return _deps.templates.TemplateResponse(
        request, "metrics_overview.html", {"user": user}
    )


@router.get("/metrics/{name}")
async def metrics_detail_page(request: Request, name: str) -> Response:
    user = await _deps.require_user(request)
    if name not in _VALID_METRICS:
        return RedirectResponse("/dashboard", status_code=303)
    return _deps.templates.TemplateResponse(
        request,
        "metrics.html",
        {"user": user, "metric_name": name},
    )


@router.get("/activity/{activity_id}")
async def activity_detail_page(request: Request, activity_id: int) -> Response:
    user = await _deps.require_user(request)
    activity = await get_activity_detail(user["id"], activity_id)
    if not activity:
        return RedirectResponse("/dashboard", status_code=303)
    return _deps.templates.TemplateResponse(
        request, "activity.html", {"user": user, "activity": activity}
    )


@router.get("/epilepsy")
async def epilepsy_page(request: Request) -> Response:
    user = await _deps.require_user(request)
    if not user.get("epilepsy_mode"):
        return RedirectResponse("/settings", status_code=303)
    return _deps.templates.TemplateResponse(request, "epilepsy.html", {"user": user})


# ── ML detail pages — redirect to unified /metrics/* blueprint ────────────────


@router.get("/ml/anomaly")
async def ml_anomaly_redirect() -> Response:
    return RedirectResponse("/metrics/hr-zscore", status_code=301)


@router.get("/ml/readiness")
async def ml_readiness_redirect() -> Response:
    return RedirectResponse("/metrics/readiness-rf", status_code=301)


@router.get("/ml/correlations")
async def ml_correlations_redirect() -> Response:
    return RedirectResponse("/metrics/correlations", status_code=301)


@router.get("/ml/battery")
async def ml_battery_redirect() -> Response:
    return RedirectResponse("/metrics/battery-pattern", status_code=301)


# ── Public legal pages (no session required) ──────────────────────────────────


@router.get("/privacy")
async def privacy(request: Request) -> Response:
    return _deps.templates.TemplateResponse(request, "privacy.html")


@router.get("/terms")
async def terms(request: Request) -> Response:
    return _deps.templates.TemplateResponse(request, "terms.html")


@router.get("/imprint")
async def imprint(request: Request) -> Response:
    return _deps.templates.TemplateResponse(request, "imprint.html")


@router.get("/accessibility")
async def accessibility(request: Request) -> Response:
    return _deps.templates.TemplateResponse(request, "accessibility.html")
