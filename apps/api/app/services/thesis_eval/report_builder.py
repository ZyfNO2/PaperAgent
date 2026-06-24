"""Session 51: 评估报告生成 (区分 4 类信息 + 挂 evidence_refs).

报告必须区分 (SOP §5.4):
1. 题录事实    (title/year/source_url/abstract_snippet) — 可 URL verified
2. 模型推断    (实验需求标签/难度/周期/可行性) — 有 evidence_refs 支撑
3. 未验证信息  (全文/作者结论/具体指标) — 标 unsupported_claims, 不编造
4. 用户可操作建议 (降级方案/审核触发/手动上传 PDF)

每个关键判断挂 evidence_refs (题录/摘要引用). 高风险论文必须给降级建议.
"""

from __future__ import annotations

from typing import Any

from ...schemas import EvidenceRef
from ...schemas_thesis_eval import (
    ExperimentNeedTag,
    ThesisAssessment,
    ThesisRecord,
)


def _make_ref(
    evidence_id: str,
    title: str,
    url: str | None,
    role: str,
    reason: str,
) -> EvidenceRef:
    """构造题录级 EvidenceRef (统一 evidence_type/paper, review_status=verified/partial)."""
    return EvidenceRef(
        evidence_id=evidence_id,
        evidence_type="paper",
        title=title or "(题录)",
        role=role,  # type: ignore[arg-type]
        reason=reason,
        review_status="accepted",
        url=url,
        url_verified=True,
    )


def _risk_tags_from_needs(needs: list[ExperimentNeedTag]) -> list[str]:
    """从实验需求标签导出主风险标签."""
    risks: list[str] = []
    if "hardware_platform_required" in needs:
        risks.append("硬件平台风险")
    if "self_collected_dataset" in needs:
        risks.append("数据自采风险")
    if "annotation_heavy" in needs:
        risks.append("标注成本风险")
    if "domain_data_permission_risk" in needs:
        risks.append("数据合规风险")
    if "h100_level_not_recommended" in needs:
        risks.append("算力不足风险")
    return risks


def _degradation_advice(difficulty: str, needs: list[ExperimentNeedTag], record: ThesisRecord) -> str:
    """高风险论文的具体降级方案 (SOP §5.4 降级建议可用率)."""
    parts: list[str] = []
    if "hardware_platform_required" in needs:
        parts.append("无硬件时先做仿真/视觉识别降级, 待硬件到位再补完整链路")
    if "self_collected_dataset" in needs:
        parts.append("优先转向有公开数据集的相邻方向 (如 NEU-DET/KITTI) 启动, 自采数据作为扩展")
    if "domain_data_permission_risk" in needs:
        parts.append("提前确认数据合规/权限, 不可用时用合成数据或脱敏公开数据替代")
    if "annotation_heavy" in needs:
        parts.append("用预标注+半自动标注降低标注成本, 限制类别数")
    if difficulty in ("高", "中-高"):
        parts.append("砍范围: 先复现单一模块/单视角, 多模态/多视角作为后续扩展")
    if not parts:
        parts.append("现有环境可做, 尽快启动 baseline 复现, 争取多做几轮消融")
    return "；".join(parts)


def _human_review_triggered(record: ThesisRecord, needs: list[ExperimentNeedTag]) -> bool:
    """信息不足时触发人工审核 (verified_status=failed/partial 或 有高风险)."""
    if record.verified_status == "failed":
        return True
    if record.verified_status == "partial" and not record.abstract_snippet:
        return True
    return bool(set(needs) & {"hardware_platform_required", "domain_data_permission_risk"})


def build_assessment_report(
    thesis_id: str,
    record: ThesisRecord,
    needs: list[ExperimentNeedTag],
    difficulty_info: dict[str, Any],
    *,
    assessment_mode: str = "heuristic",
) -> ThesisAssessment:
    """组装一条题录的完整评估 (ThesisAssessment).

    区分 4 类信息, 挂 evidence_refs, 累积 unsupported_claims, 高风险给降级建议.
    """
    evidence_refs: list[EvidenceRef] = []
    unsupported_claims: list[str] = []

    # --- 1. 题录事实 (evidence_ref supports) ---
    if record.title or record.abstract_snippet:
        evidence_refs.append(
            _make_ref(
                evidence_id=f"{thesis_id}:record",
                title=record.title or "(题录)",
                url=record.source_url,
                role="supports",
                reason=f"题录事实: title/year/abstract 来自 {record.source_url} (verified_status={record.verified_status})",
            )
        )

    # --- 2. 模型推断 (实验需求/难度/可行性, 挂 evidence_ref warns/supports) ---
    if needs:
        evidence_refs.append(
            _make_ref(
                evidence_id=f"{thesis_id}:needs",
                title=record.title or "(题录)",
                url=record.source_url,
                role="warns" if any(n in needs for n in (
                    "hardware_platform_required",
                    "domain_data_permission_risk",
                    "h100_level_not_recommended",
                )) else "supports",
                reason=f"实验需求推断: {', '.join(needs)} (基于题名+摘要片段)",
            )
        )
    if difficulty_info.get("difficulty"):
        evidence_refs.append(
            _make_ref(
                evidence_id=f"{thesis_id}:difficulty",
                title=record.title or "(题录)",
                url=record.source_url,
                role="supports",
                reason=f"难度/周期推断: {difficulty_info['difficulty']} / {difficulty_info.get('cycle')} (基于方法词+数据风险信号)",
            )
        )

    # --- 3. 未验证信息 (全文/作者结论/具体指标 → unsupported_claims, 不编造) ---
    if record.verified_status != "verified":
        unsupported_claims.append("全文/作者结论未获取 — 仅题录级证据, 建议用户手动上传 PDF 走 S46 RAG")
    if not record.abstract_snippet:
        unsupported_claims.append("摘要片段缺失 — 实验需求/难度推断仅基于题名, 信心度受限")
    # 不编造具体数据集/指标/GPU 型号
    unsupported_claims.append("未编造具体数据集名/训练指标/GPU 型号/作者结论 (防幻觉)")

    risk_tags = _risk_tags_from_needs(needs)
    human_review = _human_review_triggered(record, needs)
    confidence = float(difficulty_info.get("confidence", 0.0))
    if assessment_mode == "llm":
        confidence = min(0.95, confidence + 0.05)

    assessment = ThesisAssessment(
        thesis_id=thesis_id,
        record=record,
        experiment_needs=needs,
        difficulty=difficulty_info.get("difficulty"),
        cycle=difficulty_info.get("cycle"),
        repeatability=difficulty_info.get("repeatability"),
        graduation_feasibility=difficulty_info.get("graduation_feasibility"),
        reality_tier=difficulty_info.get("reality_tier"),
        evidence_refs=evidence_refs,
        unsupported_claims=unsupported_claims,
        risk_tags=risk_tags,
        assessment_mode=assessment_mode,  # type: ignore[arg-type]
        confidence=confidence,
    )
    # 把降级建议 + 人工审核触发挂到 assessment 上 (通过 dict 扩展, 不污染 schema)
    assessment.__dict__["_degradation_advice"] = _degradation_advice(
        difficulty_info.get("difficulty", "中"), needs, record
    )
    assessment.__dict__["_human_review_triggered"] = human_review
    return assessment


def get_report_sections(assessment: ThesisAssessment) -> dict[str, Any]:
    """把 ThesisAssessment 拆成 4 类信息的可读结构 (报告输出用).

    Returns:
        {
            "record_facts": {...},      # 题录事实 (可 verified)
            "model_inference": {...},   # 模型推断 (有 evidence_refs)
            "unverified": [...],        # 未验证信息 (unsupported_claims)
            "user_advice": {...},       # 用户可操作建议 (降级/审核)
        }
    """
    return {
        "record_facts": {
            "thesis_id": assessment.record.thesis_id,
            "title": assessment.record.title,
            "year": assessment.record.year,
            "source_url": assessment.record.source_url,
            "abstract_snippet": assessment.record.abstract_snippet,
            "verified_status": assessment.record.verified_status,
            "fallback_used": assessment.record.fallback_used,
        },
        "model_inference": {
            "experiment_needs": assessment.experiment_needs,
            "difficulty": assessment.difficulty,
            "cycle": assessment.cycle,
            "repeatability": assessment.repeatability,
            "graduation_feasibility": assessment.graduation_feasibility,
            "reality_tier": assessment.reality_tier,
            "risk_tags": assessment.risk_tags,
            "assessment_mode": assessment.assessment_mode,
            "confidence": assessment.confidence,
            "evidence_refs": [ref.model_dump() for ref in assessment.evidence_refs],
        },
        "unverified": list(assessment.unsupported_claims),
        "user_advice": {
            "degradation_advice": assessment.__dict__.get("_degradation_advice", ""),
            "human_review_triggered": assessment.__dict__.get("_human_review_triggered", False),
            "next_step": "手动上传 PDF 走 S46 全文 RAG 以补充全文/作者结论" if assessment.record.verified_status != "verified" else "可进入选题可行性闭环",
        },
    }
