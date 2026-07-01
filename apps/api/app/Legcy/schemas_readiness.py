"""Session 32: 学校模板合规与导出前检查 schemas."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class ReadinessStatus(str, Enum):
    pass_ = "pass"
    warn = "warn"
    fail = "fail"


class SchoolTemplate(str, Enum):
    default = "default"
    engineering = "engineering"
    cv_ai = "cv_ai"


class ReadinessDimension(BaseModel):
    dimension: str
    status: ReadinessStatus
    message: str
    required_fix: Optional[str] = None
    section_refs: List[str] = []


class ReadinessReport(BaseModel):
    project_id: str
    template_key: SchoolTemplate
    overall_status: ReadinessStatus
    dimensions: List[ReadinessDimension] = []
    hard_blocks: List[str] = []
    export_allowed: bool = True


class ReadinessRequest(BaseModel):
    project_id: str
    template_key: str = "default"
