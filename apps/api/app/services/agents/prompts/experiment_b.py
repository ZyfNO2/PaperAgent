"""Re5.X: Experiment B — Reflection Critic + Query Writer.

Two-stage controlled reflection:
  1. Critic: diagnoses previous round based on observations only
  2. Writer: generates 0-2 SearchCards from the diagnosis

Both outputs are validated against Pydantic schemas.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, field_validator

from apps.api.app.services.agents.graph.schemas.search_models import Diagnosis


class QueryWriterCard(BaseModel):
    """A single SearchCard from the Query Writer."""
    source: str = Field(description="Must be from allowed_sources")
    query: str = Field(min_length=2)
    target_role: str = Field(default="core")
    expected_signal: str | None = None
    query_term_origin: list[dict[str, str]] = Field(default_factory=list)
    stop_if: str | None = None

    @field_validator("target_role")
    @classmethod
    def _valid_role(cls, v: str) -> str:
        valid = {"core", "baseline", "parallel", "dataset", "repo", "metadata"}
        if v not in valid:
            raise ValueError(f"target_role must be one of {valid}")
        return v


class QueryWriterOutput(BaseModel):
    """Output of the Query Writer."""
    cards: list[QueryWriterCard] = Field(default_factory=list)
    abstain_reason: str | None = None


REFLECTION_CRITIC_SYSTEM = """你只根据 OBSERVATIONS 诊断上一轮检索；不生成论文事实，不判断题目是否可做，
不直接生成查询。

从下列 diagnosis_code 中选择一个：
role_gap | low_precision | query_too_narrow | query_too_broad |
source_unavailable | metadata_gap | no_repair_route | unknown

从下列 action 中选择一个：
rewrite_query | switch_source | expand_from_accepted_seed |
repair_metadata | stop_with_explicit_gap

规则：
- source_status=empty 不得判为 source_unavailable。
- 只有 required_roles 包含 repo 时，repo 缺失才是 gap。
- 每个判断必须引用 query_id 或 candidate_id。
- 没有足够 observation 时输出 unknown；不得猜测。

返回 JSON：
{
  "diagnosis_id": "...",
  "diagnosis_code": "...",
  "confidence": 0.0,
  "action": "...",
  "target_role": "core|baseline|parallel|dataset|repo|metadata",
  "evidence_ids": ["..."],
  "must_keep_terms": ["仅来自 atoms 或 accepted candidate"],
  "avoid_terms": ["仅来自 rejected/noise observation"],
  "source_preference": ["仅来自 allowed_sources"],
  "stop_reason": null
}

[OUTPUT CONTRACT] 你必须输出且仅输出一个合法 JSON 对象，不要输出其他内容。"""


QUERY_WRITER_SYSTEM = """根据 DIAGNOSIS 生成至多两张 SearchCard；每张卡只关闭一个 target_role。

约束：
- source 必须来自 allowed_sources；
- query 必须包含 must_keep_terms 至少一个词；
- 不得包含 avoid_terms；
- 不得与 prior_query_fingerprints 等价；
- 新增词必须标记来源：atom、accepted_seed 或 controlled_synonym；
- 无高质量修复路径时返回空 cards，不可用通用方法词填充。

返回：
{
  "cards": [{
    "source": "...",
    "query": "...",
    "target_role": "...",
    "expected_signal": "代码可验证的命中条件",
    "query_term_origin": [{"term":"...","origin":"atom|accepted_seed|controlled_synonym"}],
    "stop_if": "..."
  }],
  "abstain_reason": null
}

[OUTPUT CONTRACT] 你必须输出且仅输出一个合法 JSON 对象，不要输出其他内容。"""


def build_critic_prompt(
    observations: list[dict[str, Any]],
    required_roles: dict[str, int],
    current_coverage: dict[str, int],
    gaps: list[str],
    allowed_sources: list[str],
) -> str:
    """Build the user prompt for the Reflection Critic."""
    import json
    return json.dumps({
        "observations": observations[-8:],
        "required_roles": required_roles,
        "current_coverage": current_coverage,
        "gaps": gaps,
        "allowed_sources": allowed_sources,
    }, ensure_ascii=False, indent=2)


def build_writer_prompt(
    diagnosis: dict[str, Any],
    allowed_sources: list[str],
    prior_fingerprints: list[str],
    atoms: dict[str, Any],
    accepted_seeds: list[str],
) -> str:
    """Build the user prompt for the Query Writer."""
    import json
    return json.dumps({
        "diagnosis": diagnosis,
        "allowed_sources": allowed_sources,
        "prior_query_fingerprints": prior_fingerprints[-10:],
        "atoms": {
            "method": atoms.get("method", [])[:5],
            "object": atoms.get("object", [])[:5],
            "task": atoms.get("task", [])[:3],
        },
        "accepted_seeds": accepted_seeds[:5],
    }, ensure_ascii=False, indent=2)


def parse_diagnosis(raw: dict[str, Any]) -> Diagnosis | None:
    """Parse and validate critic output. Returns None if invalid."""
    try:
        return Diagnosis(**raw)
    except Exception:
        return None


def parse_writer_output(raw: dict[str, Any]) -> QueryWriterOutput | None:
    """Parse and validate writer output. Returns None if invalid."""
    try:
        return QueryWriterOutput(**raw)
    except Exception:
        return None
