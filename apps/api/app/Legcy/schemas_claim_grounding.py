"""Session 48: Claim Grounding schemas.

ClaimGroundingResult: 输入一句报告断言 (claim), 返回论文库对该 claim 的判定.

verdict 状态机 (SOP §5):
  - supported:      至少 1 个 direct / indirect chunk 支持
  - weak_support:   仅有 background 或 score 介于 0.4-0.7
  - contradiction:  存在 contradiction chunk 且无 direct 支持
  - unsupported:    无命中, 或全部 score < 0.4

引用规则 (Task 6):
  - rejected chunk: 永不进入 supporting/contradicting (永不出现在 refs)
  - pending chunk:  仅 background, 不可 direct/indirect
  - failed verify:  不可 direct/indirect
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .schemas_paper_rag import EvidenceRef


# 兼容旧 schema 别名
GroundingStatus = Literal["supported", "weak_support", "contradiction", "unsupported"]
GroundingVerdict = GroundingStatus  # SOP §5.2 用 verdict 字段


class ClaimGroundingResult(BaseModel):
    """单条 claim 的 grounding 判定结果."""

    model_config = ConfigDict(extra="forbid")

    claim: str
    status: GroundingStatus
    verdict: GroundingStatus = "unsupported"  # alias for status (SOP §5.2)
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_chunks: list[EvidenceRef] = Field(default_factory=list)
    contradicting_chunks: list[EvidenceRef] = Field(default_factory=list)
    background_chunks: list[EvidenceRef] = Field(default_factory=list)
    reason: str = ""
    retrieval_mode: Literal["llm", "fallback"] = "fallback"


class ClaimGroundBatchRequest(BaseModel):
    """POST /ground-claims 请求体."""

    model_config = ConfigDict(extra="forbid")

    claims: list[str] = Field(min_length=1, max_length=50)
    scope: Literal["all_papers", "accepted_papers", "specific"] = "accepted_papers"
    paper_ids: list[str] | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class ClaimGroundBatchResponse(BaseModel):
    """POST /ground-claims 响应."""

    model_config = ConfigDict(extra="forbid")

    results: list[ClaimGroundingResult]
    total: int


__all__ = [
    "ClaimGroundingResult",
    "ClaimGroundBatchRequest",
    "ClaimGroundBatchResponse",
    "GroundingStatus",
    "GroundingVerdict",
]