"""Health / Diagnostic helper (Session 18 SOP §5).

不做真实网络探测作为默认 health; 外部源状态只说明 configured / optional / placeholder.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _runtime_dir(name: str, env_var: str | None = None) -> tuple[bool, str]:
    """检查 .runtime 子目录是否存在, 返回 (writable, abs_path)."""

    base = Path(os.environ.get(env_var, PROJECT_ROOT / ".runtime" / name))
    try:
        base.mkdir(parents=True, exist_ok=True)
        probe = base / ".health_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True, str(base)
    except Exception:
        return False, str(base)


def build_basic_health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": os.environ.get("PAPERAGENT_VERSION", "0.1.0-rc1"),
        "service": "paperagent-api",
        "time": datetime.now(timezone.utc).isoformat(),
    }


def build_detailed_health() -> dict[str, Any]:
    basic = build_basic_health()
    trace_ok, trace_path = _runtime_dir("traces", "PAPERAGENT_TRACE_DIR")
    mat_ok, mat_path = _runtime_dir("materials", "PAPERAGENT_MATERIALS_DIR")
    retr_ok, retr_path = _runtime_dir("retrieval", "PAPERAGENT_RETRIEVAL_DIR")

    # Skill registry: 加载 4 个内部 skill; 失败不致命, 计入 issues
    skill_issues: list[str] = []
    enabled = 0
    try:
        from app.services.skill_registry import list_skills
        skills = list_skills()
        enabled = sum(1 for s in skills if s.get("status") == "enabled")
    except Exception as e:
        skill_issues.append(f"skill_registry 加载失败: {e}")

    return {
        **basic,
        "runtime_dirs": {
            "traces": {"ok": trace_ok, "path": trace_path},
            "materials": {"ok": mat_ok, "path": mat_path},
            "retrieval": {"ok": retr_ok, "path": retr_path},
        },
        "skills": {
            "enabled": enabled,
            "issues": skill_issues,
        },
        "external_sources": {
            "openalex": "optional",
            "arxiv": "optional",
            "github": "optional",
            "huggingface": "optional",
            "semantic_scholar": "placeholder",
            "kaggle": "placeholder",
        },
    }