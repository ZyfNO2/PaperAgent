"""Session 26: Evidence Promotion schemas (SOP §2-5).

候选→证据晋升闸门：只有 selected + URLVerified + user_confirmed 才能晋升。
Selected != Evidence 是不变式；晋升是显式操作，不自动发生。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import EvidenceRef
from app.schemas_candidates import CandidateKind


# ---------- URL Verification Status ---------- #


URLVerificationStatus = Literal["unchecked", "verified", "partial", "failed", "expired"]


class URLVerificationRecord(BaseModel):
    """URL 验证记录 — 桥接 candidate.url 与 selected.verification_status."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(description="被验证的 URL")
    status: URLVerificationStatus = Field(default="unchecked")
    checked_at: str | None = Field(default=None, description="验证时间")
    failure_reason: str | None = Field(default=None, description="失败原因")
    http_status: int | None = Field(default=None, description="HTTP 状态码")
    response_time_ms: float | None = Field(default=None)


# ---------- Promotion Request / Result ---------- #


class EvidencePromotionRequest(BaseModel):
    """晋升请求 — 用户发起."""

    model_config = ConfigDict(extra="forbid")

    selected_id: str = Field(min_length=1, description="选中资源 ID")
    candidate_id: str = Field(min_length=1, description="来源候选 ID")
    promotion_reason: str = Field(default="", description="晋升理由")
    claim_hint: str = Field(default="", description="该证据可用于支持的论点提示")
    user_confirmed: bool = Field(default=False, description="用户确认（必须为 True 才能晋升）")


PromotionStatus = Literal["blocked", "eligible", "promoted"]


class EvidencePromotionResult(BaseModel):
    """晋升结果."""

    model_config = ConfigDict(extra="forbid")

    status: PromotionStatus
    evidence_ref: EvidenceRef | None = Field(default=None, description="晋升成功时生成的 EvidenceRef")
    blockers: list[str] = Field(default_factory=list, description="阻止晋升的原因列表")
    warnings: list[str] = Field(default_factory=list, description="晋升时的警告（partial 等）")


# ---------- Promotion Gate Logic ---------- #


class PromotionGateInput(BaseModel):
    """晋升闸门输入 — 聚合所有需要的状态."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    candidate_title: str = ""
    candidate_kind: CandidateKind = "paper"
    candidate_url: str = ""
    is_selected: bool = Field(default=False, description="是否已加入左栏")
    selected_id: str | None = Field(default=None)
    url_verification_status: URLVerificationStatus = "unchecked"
    url_failure_reason: str | None = None
    user_confirmed: bool = False
    promotion_reason: str = ""
    claim_hint: str = ""


def check_promotion_gate(inp: PromotionGateInput) -> EvidencePromotionResult:
    """检查晋升条件，返回 blocked/eligible/promoted."""
    blockers: list[str] = []
    warnings: list[str] = []

    # 条件 1: 必须已选中
    if not inp.is_selected:
        blockers.append(f"Candidate {inp.candidate_id} is not selected.")

    # 条件 2: URL 必须验证
    if inp.url_verification_status == "unchecked":
        blockers.append(f"URL for {inp.candidate_id} is not verified.")
    elif inp.url_verification_status == "failed":
        reason = inp.url_failure_reason or "unknown"
        blockers.append(f"URL verification failed for {inp.candidate_id}: {reason}")
    elif inp.url_verification_status == "expired":
        blockers.append(f"URL verification expired for {inp.candidate_id}.")

    # 条件 3: 用户必须确认
    if not inp.user_confirmed:
        blockers.append("User has not confirmed promotion.")

    # 如果有 blockers，返回 blocked
    if blockers:
        return EvidencePromotionResult(
            status="blocked",
            blockers=blockers,
        )

    # partial 有警告但仍然 eligible
    if inp.url_verification_status == "partial":
        warnings.append(f"URL for {inp.candidate_id} is only partially verified.")

    return EvidencePromotionResult(
        status="eligible",
        warnings=warnings,
    )


def promote_to_evidence(
    inp: PromotionGateInput,
    evidence_id: str | None = None,
) -> EvidencePromotionResult:
    """尝试晋升为 EvidenceRef — 先过闸门，通过后构建 EvidenceRef."""
    gate_result = check_promotion_gate(inp)
    if gate_result.status == "blocked":
        return gate_result

    # 构建 EvidenceRef
    ev_id = evidence_id or f"ev_{inp.candidate_id}"
    ev_type: Literal["paper", "dataset", "repo", "baseline", "note"] = inp.candidate_kind if inp.candidate_kind in ("paper", "dataset", "repo") else "note"  # type: ignore[assignment]

    evidence_ref = EvidenceRef(
        evidence_id=ev_id,
        evidence_type=ev_type,
        title=inp.candidate_title or f"Evidence from {inp.candidate_id}",
        role="supports",
        reason=inp.promotion_reason or "Promoted from candidate",
        review_status="pending",
        url=inp.candidate_url or None,
        url_verified=inp.url_verification_status == "verified",
        verification_status=inp.url_verification_status,
    )

    return EvidencePromotionResult(
        status="promoted",
        evidence_ref=evidence_ref,
        warnings=gate_result.warnings,
    )
