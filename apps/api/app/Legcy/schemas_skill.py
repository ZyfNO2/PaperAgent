"""Session 13: 内部 Skill Registry schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SkillCategory = Literal["research", "dataset", "engineering", "evidence", "topic", "writing", "defense"]
SkillStatus = Literal["candidate", "reviewed", "adapted", "enabled", "disabled", "deprecated"]
SkillRiskLevel = Literal["low", "medium", "high"]


class SkillMetadata(BaseModel):
    """一个内部 skill 的元数据 (SOP §4)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    category: SkillCategory
    version: str = "0.1.0"
    path: str
    description: str = ""
    status: SkillStatus = "candidate"
    risk_level: SkillRiskLevel = "medium"
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)
    requires_tools: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    used_by: list[str] = Field(default_factory=list)
    summary: str = Field(default="", description="SKILL.md 前 N 字符摘要")


class SkillRegistryResponse(BaseModel):
    """GET /skills 响应."""

    model_config = ConfigDict(extra="forbid")

    skills: list[SkillMetadata]
    enabled_count: int
    disabled_count: int
    high_risk_count: int


class SkillHealthIssue(BaseModel):
    """单个 skill 的健康问题."""

    model_config = ConfigDict(extra="forbid")

    skill: str
    status: SkillStatus
    issues: list[str] = Field(default_factory=list)


class SkillHealthResponse(BaseModel):
    """GET /skills/health 响应."""

    model_config = ConfigDict(extra="forbid")

    total: int
    ok: int
    issues: list[SkillHealthIssue] = Field(default_factory=list)
    default_forbidden_actions: list[str] = Field(default_factory=list)