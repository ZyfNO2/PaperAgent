"""Session 13: 内部 Skill Registry 服务 (SOP §5).

加载 skills/registry.json, 提供 list/get/health.
只做管理层, 不执行 skill 内 shell 命令.

调用:
  list_skills(category=None, status=None)
  get_skill(name) -> SkillMetadata | None
  health_check() -> SkillHealthResponse
  get_default_forbidden() -> list[str]
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from ..schemas_skill import (
    SkillCategory,
    SkillHealthIssue,
    SkillHealthResponse,
    SkillMetadata,
    SkillRegistryResponse,
    SkillRiskLevel,
    SkillStatus,
)


# ---------- manifest 路径 ---------- #

# apps/api/app/services/skill_registry.py -> parents[4] = repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]
_MANIFEST_PATH = _REPO_ROOT / "skills" / "registry.json"


# 默认禁止列表 (SOP §8)
DEFAULT_FORBIDDEN = [
    "shell_exec",
    "write_outside_workspace",
    "upload_user_files",
    "unknown_external_api",
    "auto_install_deps",
    "bypass_evidence",
    "fabricate_refs",
]


def get_default_forbidden() -> list[str]:
    return list(DEFAULT_FORBIDDEN)


# ---------- 缓存 ---------- #

_CACHE: list[SkillMetadata] | None = None
_CACHE_LOCK = threading.RLock()


def _load_manifest() -> list[SkillMetadata]:
    """加载并校验 manifest."""

    global _CACHE
    with _CACHE_LOCK:
        if _CACHE is not None:
            return _CACHE
        if not _MANIFEST_PATH.exists():
            _CACHE = []
            return _CACHE
        raw = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        out: list[SkillMetadata] = []
        for item in raw:
            try:
                meta = SkillMetadata(**item)
                # 读 SKILL.md 摘要
                skill_path = _REPO_ROOT / meta.path
                if skill_path.exists():
                    try:
                        text = skill_path.read_text(encoding="utf-8")
                        meta.summary = text[:200].strip()
                    except Exception:
                        meta.summary = "(无法读取 SKILL.md)"
                else:
                    meta.summary = "(SKILL.md 不存在)"
                out.append(meta)
            except Exception:
                # 单个 manifest 条目错, 跳过
                continue
        _CACHE = out
        return _CACHE


def reset_cache() -> None:
    global _CACHE
    with _CACHE_LOCK:
        _CACHE = None


# ---------- 公共 API ---------- #


def list_skills(
    category: SkillCategory | None = None,
    status: SkillStatus | None = None,
) -> SkillRegistryResponse:
    skills = _load_manifest()
    if category:
        skills = [s for s in skills if s.category == category]
    if status:
        skills = [s for s in skills if s.status == status]
    enabled = sum(1 for s in _load_manifest() if s.status == "enabled")
    disabled = sum(1 for s in _load_manifest() if s.status in ("disabled", "deprecated"))
    high_risk = sum(1 for s in _load_manifest() if s.risk_level == "high")
    return SkillRegistryResponse(
        skills=skills,
        enabled_count=enabled,
        disabled_count=disabled,
        high_risk_count=high_risk,
    )


def get_skill(name: str) -> SkillMetadata | None:
    for s in _load_manifest():
        if s.name == name:
            return s
    return None


def health_check() -> SkillHealthResponse:
    skills = _load_manifest()
    issues: list[SkillHealthIssue] = []
    ok = 0
    for s in skills:
        problems: list[str] = []
        # path 存在
        skill_path = _REPO_ROOT / s.path
        if not skill_path.exists():
            problems.append(f"SKILL.md path 不存在: {s.path}")
        # status enabled 时必须有 risk_level
        if s.status == "enabled" and not s.risk_level:
            problems.append("enabled skill 缺 risk_level")
        # high risk 默认不应 enabled
        if s.risk_level == "high" and s.status == "enabled":
            problems.append("high_risk skill 默认不能 enabled (违反 SOP §8)")
        # input/output schema 检查 (MVP: 可选, 不强求)
        if s.status == "enabled" and not s.input_schema and not s.used_by:
            problems.append("enabled skill 缺 input_schema 或 used_by")
        # forbidden_actions 必须包含默认禁止
        if s.status == "enabled":
            for forbidden in ("shell_exec", "bypass_evidence", "fabricate_refs"):
                if forbidden not in s.forbidden_actions:
                    problems.append(f"缺默认禁止动作: {forbidden}")

        if not problems:
            ok += 1
        else:
            issues.append(SkillHealthIssue(skill=s.name, status=s.status, issues=problems))

    return SkillHealthResponse(
        total=len(skills),
        ok=ok,
        issues=issues,
        default_forbidden_actions=get_default_forbidden(),
    )