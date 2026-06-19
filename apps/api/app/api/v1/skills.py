"""Session 13: 内部 Skill Registry API."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import ConfigDict

from ...schemas_skill import (
    SkillHealthResponse,
    SkillMetadata,
    SkillRegistryResponse,
)
from ...services import skill_registry as registry_service


router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


@router.get(
    "",
    response_model=SkillRegistryResponse,
    summary="Session 13 §6.1: 列出内部 Skill",
)
def list_skills(
    category: Literal["research", "dataset", "engineering", "evidence", "topic", "writing", "defense"] | None = Query(None),
    status: Literal["candidate", "reviewed", "adapted", "enabled", "disabled", "deprecated"] | None = Query(None),
) -> SkillRegistryResponse:
    return registry_service.list_skills(category=category, status=status)


@router.get(
    "/health",
    response_model=SkillHealthResponse,
    summary="Session 13 §6.3: Skill 健康检查",
)
def health() -> SkillHealthResponse:
    return registry_service.health_check()


@router.get(
    "/{name}",
    response_model=SkillMetadata,
    summary="Session 13 §6.2: 获取单个 Skill",
)
def get_skill(name: str) -> SkillMetadata:
    skill = registry_service.get_skill(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"skill '{name}' 不存在")
    return skill