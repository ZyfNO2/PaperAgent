"""Health router (Session 18 SOP §5).

GET /api/v1/health
GET /api/v1/health/detailed
"""

from __future__ import annotations

from fastapi import APIRouter

from app.services.health import build_basic_health, build_detailed_health

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="基础 health (本地诊断)")
def get_health() -> dict:
    return build_basic_health()


@router.get("/detailed", summary="详细 health (runtime dirs / skills / external sources)")
def get_health_detailed() -> dict:
    return build_detailed_health()