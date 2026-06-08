"""Aggregator for the /api/* JSON surface.

Endpoints live in feature modules (ARCH-L5: keeps each file under the 400-line
trigger). main.py registers this single `router`.
"""

from fastapi import APIRouter

from src.routes.api_glucose import router as glucose_router
from src.routes.api_health import router as health_router
from src.routes.api_ml import router as ml_router
from src.routes.api_seizures import router as seizures_router

router = APIRouter()
router.include_router(health_router)
router.include_router(ml_router)
router.include_router(seizures_router)
router.include_router(glucose_router)
