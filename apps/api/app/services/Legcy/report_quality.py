"""Session 12: 报告质量检查与低门槛委员会复核.

基于 FinalPackage + EvidenceRef + Verification + Trace 评估 8 维,
输出 verdict / score / revision_checklist / defense_questions.

调用:
  build_quality_review(project_id, request) -> ReportQualityReview
  get_quality_review(project_id) -> ReportQualityReview | None
  render_quality_markdown(review) -> str
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from ..schemas import EvidenceRef, OneTopicResponse
from ..schemas_quality import (
    DefenseQuestion,
    QualityResult,
    ReportQualityCheck,
    ReportQualityReview,
    ReportReviewRequest,
    ReportReviewSummary,
    RiskLevel,
)
from . import evidence as ev_store
from . import evidence_refs as refs_service


# ---------- 缓存 ---------- #

_REVIEW: dict[str, ReportQualityReview] = {}


def save_quality_review(project_id: str, review: ReportQualityReview) -> None:
    _REVIEW[project_id] = review


def get_quality_review(project_id: str) -> ReportQualityReview | None:
    return _REVIEW.get(project_id)


# ---------- 阈值与权重 ---------- #

RESULT_THRESHOLDS = [
    (80, "通过"),
    (60, "有条件通过"),
    (40, "需修改"),
    (0, "不建议"),
]


def _result_for_score(score: float) -> QualityResult:
    for th, label in RESULT_THRESHOLDS:
        if score >= th:
            return label  # type: ignore[return-value]
    return "不建议"


# 关键维度: 任一触发 → 总 verdict 不建议
KEY_DIMENSIONS = frozenset({"数据集", "Baseline", "工作包", "证据覆盖"})


# ---------- 主入口 ---------- #


def build_quality_review(
    project_id: str,
    request: ReportReviewRequest | None = None,
    *,
    snapshot: dict[str, Any] | None = None,
) -> ReportQualityReview:
    """从 FinalPackage + Trace + Pool 构建 ReportQualityReview."""

    request = request or ReportReviewRequest()

    if snapshot is None:
        snapshot = ev_store.get_snapshot(project_id)

    if not snapshot:
        # 没 snapshot 不能评
        review = ReportQualityReview(
            project_id=project_id,
            verdict="不建议",
            score=0.0,
            reviewed_at=datetime.now(timezone.utc).isoformat(),
            revision_checklist=["无 snapshot, 请先 POST /analyze 或 /regenerate"],
            defense_questions=[],
        )
        save_quality_review(project_id, review)
        return review

    feas = snapshot.get("feasibility") or {}
    proposal = snapshot.get("proposal_recommendation") or {}
    review_snap = snapshot.get("light_review") or {}
    ev_sum = snapshot.get("evidence_summary") or {}

    feas_refs = feas.get("evidence_refs") or []
    blocking_refs = feas.get("blocking_refs") or []
    topic_refs = proposal.get("topic_evidence_refs") or []
    wp_list = proposal.get("work_packages") or []
    pivot_list = proposal.get("pivot_routes") or []
    review_checks = review_snap.get("checks") or []
    reason_refs = proposal.get("reason_evidence_refs") or {}

    # 收集所有 evidence ref (含 verification)
    all_refs: list[dict[str, Any]] = []
    all_refs.extend(feas_refs)
    all_refs.extend(blocking_refs)
    all_refs.extend(topic_refs)
    for c in review_checks:
        all_refs.extend(c.get("evidence_refs") or [])

    # 把 ledger 里 manual evidence 的 verification 状态透传到 all_refs (影响 failed 检查)
    pool = ev_store.get_pool_items(project_id)
    eid_to_v = {e.evidence_id: e for e in pool if e.verification_status and e.verification_status != "unverified"}
    for r in all_refs:
        eid = r.get("evidence_id", "")
        if eid in eid_to_v:
            item = eid_to_v[eid]
            r["verification_status"] = item.verification_status
            r["verification_confidence"] = item.verification_confidence
            r["verification_warnings"] = list(item.verification_warnings or [])

    # 把 ledger 里 failed/skipped 的 evidence 也加进 all_refs (即使没被 snapshot refs 引用)
    for item in pool:
        if item.verification_status in ("failed", "skipped") and item.evidence_id not in {r.get("evidence_id") for r in all_refs}:
            all_refs.append({
                "evidence_id": item.evidence_id,
                "evidence_type": item.evidence_type,
                "title": item.title,
                "role": "warns",
                "reason": "ledger evidence with failed/skipped verification",
                "score": item.relevance_score or item.quality_score,
                "review_status": item.review_status,
                "url": item.url,
                "verification_status": item.verification_status,
                "verification_confidence": item.verification_confidence,
                "verification_warnings": list(item.verification_warnings or []),
            })

    checks: list[ReportQualityCheck] = []

    # 1. 题目边界
    checks.append(_check_topic_boundary(proposal, snapshot))

    # 2. 研究现状
    checks.append(_check_related_work(feas_refs, ev_sum, all_refs))

    # 3. 数据集
    checks.append(_check_dataset(feas, ev_sum, all_refs))

    # 4. Baseline
    checks.append(_check_baseline(feas, ev_sum, all_refs))

    # 5. 工作包
    checks.append(_check_work_packages(wp_list))

    # 6. 创新点
    checks.append(_check_innovation(reason_refs, all_refs))

    # 7. 风险预案
    checks.append(_check_risks(feas, all_refs))

    # 8. 表达清晰度
    checks.append(_check_clarity(snapshot, feas))

    # 总分 = 各维加权平均 (简单等权)
    total_score = round(sum(c.score for c in checks) / max(len(checks), 1), 1)

    # 总 verdict
    failing = [c.dimension for c in checks if c.result == "不建议"]
    need_fix = [c.dimension for c in checks if c.result == "需修改"]
    cond = [c.dimension for c in checks if c.result == "有条件通过"]

    key_fail = any(d in KEY_DIMENSIONS for d in failing)
    if key_fail or len(failing) >= 1:
        verdict: QualityResult = "不建议"
    elif len(need_fix) >= 2:
        verdict = "需修改"
    elif len(need_fix) == 1 or len(cond) >= 2:
        verdict = "有条件通过"
    else:
        verdict = "通过"

    # revision checklist: 合并 issues + 不通过/需修改的 suggestions
    revision: list[str] = []
    for c in checks:
        if c.result in ("需修改", "不建议", "有条件通过"):
            revision.extend(c.suggestions)

    # 加 FinalPackage 原 revision_checklist
    fp_pkg = ev_store.get_final_package(project_id)
    if fp_pkg and getattr(fp_pkg, "revision_checklist", None):
        # 去重
        for line in fp_pkg.revision_checklist:
            if line not in revision:
                revision.append(line)

    # 答辩问题
    defense = _build_defense_questions(snapshot, all_refs)

    review = ReportQualityReview(
        project_id=project_id,
        verdict=verdict,
        score=total_score,
        checks=checks,
        revision_checklist=revision[:30],
        defense_questions=defense,
        reviewed_at=datetime.now(timezone.utc).isoformat(),
    )

    save_quality_review(project_id, review)
    return review


def get_quality_review_summary(project_id: str) -> ReportReviewSummary | None:
    review = get_quality_review(project_id)
    if not review:
        return None
    return ReportReviewSummary(
        project_id=review.project_id,
        verdict=review.verdict,
        score=review.score,
        dimension_count=len(review.checks),
        passing_count=sum(1 for c in review.checks if c.result == "通过"),
        failing_dimensions=[c.dimension for c in review.checks if c.result in ("需修改", "不建议")],
        reviewed_at=review.reviewed_at,
    )


# ---------- 8 维检查实现 ---------- #


def _check_topic_boundary(proposal: dict, snapshot: dict) -> ReportQualityCheck:
    """检查推荐题目是否过宽 (heuristic: 长度 + 关键词)."""

    topic = proposal.get("recommended_topic", "") or ""
    issues: list[str] = []
    suggestions: list[str] = []
    score = 100.0

    if not topic or topic == "(待定)":
        issues.append("推荐题目缺失")
        suggestions.append("补全 recommended_topic (在 pivot select 后会自动生成)")
        score -= 50
    elif len(topic) > 60:
        issues.append(f"题目过长 ({len(topic)} 字), 可能边界不清")
        suggestions.append("收缩题目边界, 限定方法 / 对象 / 任务")
        score -= 15
    elif len(topic) < 8:
        issues.append("题目过短, 缺乏具体方法 / 对象 / 任务")
        suggestions.append("补全方法 / 对象 / 任务关键词")
        score -= 10

    # 风险词检查
    risk_words = ["智能", "通用", "高精度", "实时", "自适应", "端到端"]
    for w in risk_words:
        if w in topic and "限定" not in topic:
            issues.append(f"包含风险词 '{w}', 开题答辩可能被追问界定")
            suggestions.append(f"在题目中限定 '{w}' 的范围 (例如 '特定场景下的智能')")
            score -= 10
            break

    score = max(0.0, score)
    return ReportQualityCheck(
        dimension="题目边界",
        result=_result_for_score(score),
        score=score,
        issues=issues,
        suggestions=suggestions,
    )


def _check_related_work(feas_refs: list, ev_sum: dict, all_refs: list) -> ReportQualityCheck:
    """检查 feasibility.paper refs 数量 + verification 状态."""

    paper_refs = [r for r in feas_refs if r.get("evidence_type") == "paper"]
    n = len(paper_refs)
    issues: list[str] = []
    suggestions: list[str] = []
    score = 100.0

    if n == 0:
        issues.append("可行性判断没有 paper 引用")
        suggestions.append("补 1-3 篇 arXiv / OpenAlex 论文支撑研究现状")
        score -= 50
    elif n < 2:
        issues.append(f"仅 {n} 篇 paper 引用, 研究现状偏薄")
        suggestions.append("再补 1-2 篇核心论文")
        score -= 20

    failed_n = sum(1 for r in all_refs if r.get("verification_status") == "failed")
    if failed_n:
        issues.append(f"{failed_n} 条 evidence 验证失败, 研究现状可信度降低")
        suggestions.append("复核 failed 证据的 URL, 或换用替代证据")
        score -= 10 * failed_n

    # 找 paper_failed: 直接从 all_refs 中找 failed paper (即使不在 feas_refs)
    paper_failed_n = sum(
        1 for r in all_refs
        if r.get("evidence_type") == "paper" and r.get("verification_status") == "failed"
    )
    if paper_failed_n and score >= 100:
        score -= 10 * paper_failed_n

    score = max(0.0, score)
    return ReportQualityCheck(
        dimension="研究现状",
        result=_result_for_score(score),
        score=score,
        evidence_refs=[_to_ref(r) for r in paper_refs[:3]],
        issues=issues,
        suggestions=suggestions,
    )


def _check_dataset(feas: dict, ev_sum: dict, all_refs: list) -> ReportQualityCheck:
    """检查 dataset ref + license/download 字段."""

    datasets = ev_sum.get("datasets", []) or []
    feas_dataset_refs = [r for r in (feas.get("evidence_refs") or []) if r.get("evidence_type") == "dataset"]
    n = len(datasets) + len(feas_dataset_refs)

    issues: list[str] = []
    suggestions: list[str] = []
    score = 100.0

    if n == 0:
        issues.append("未匹配到公开数据集, 工作包无数据基础")
        suggestions.append("补一个公开数据集 (HuggingFace / Kaggle / GitHub) 或自采")
        score -= 70
    else:
        # license 检查
        no_license = sum(1 for d in datasets if not (d.get("license") or "").strip())
        if no_license:
            issues.append(f"{no_license} 个数据集 license 未确认")
            suggestions.append("手动确认数据集 license (CC-BY / MIT / 商业可用)")
            score -= 15 * no_license
        # download 检查
        no_dl = sum(1 for d in datasets if not (d.get("download") or "").strip())
        if no_dl:
            issues.append(f"{no_dl} 个数据集 download URL 缺失")
            suggestions.append("补 download URL")
            score -= 10 * no_dl

    score = max(0.0, score)
    refs = feas_dataset_refs[:2] + [{"evidence_id": d.get("dataset_id", d.get("evidence_id", "")), "title": d.get("name", ""), "evidence_type": "dataset"} for d in datasets[:2]]
    return ReportQualityCheck(
        dimension="数据集",
        result=_result_for_score(score),
        score=score,
        evidence_refs=[_to_ref(r) for r in refs],
        issues=issues,
        suggestions=suggestions,
    )


def _check_baseline(feas: dict, ev_sum: dict, all_refs: list) -> ReportQualityCheck:
    """检查 repo/baseline ref."""

    repos = ev_sum.get("baselines", []) or []
    feas_repo_refs = [r for r in (feas.get("evidence_refs") or []) if r.get("evidence_type") in ("repo", "baseline")]
    n = len(repos) + len(feas_repo_refs)

    issues: list[str] = []
    suggestions: list[str] = []
    score = 100.0

    if n == 0:
        issues.append("未匹配到 baseline repo, 工作包无可复现工程")
        suggestions.append("补一个 GitHub repo (official / reproduction)")
        score -= 70
    else:
        # repo_type 检查
        unknown = sum(1 for r in repos if (r.get("repo_type") or "unknown") in ("unknown", "demo_only", "not_reproducible"))
        if unknown:
            issues.append(f"{unknown} 个 repo repo_type 不可复现 (unknown/demo_only)")
            suggestions.append("替换为可复现的 official/baseline_framework repo")
            score -= 20 * unknown

    score = max(0.0, score)
    refs = feas_repo_refs[:2] + [{"evidence_id": r.get("baseline_id", r.get("evidence_id", "")), "title": r.get("name", ""), "evidence_type": "repo"} for r in repos[:2]]
    return ReportQualityCheck(
        dimension="Baseline",
        result=_result_for_score(score),
        score=score,
        evidence_refs=[_to_ref(r) for r in refs],
        issues=issues,
        suggestions=suggestions,
    )


def _check_work_packages(wp_list: list) -> ReportQualityCheck:
    """检查每个 WP 是否有 paper/dataset/repo/metric ref."""

    issues: list[str] = []
    suggestions: list[str] = []
    score = 100.0

    if not wp_list:
        issues.append("工作包为空, 未生成 work_package")
        suggestions.append("先选 pivot 路线生成工作包")
        score -= 80
    else:
        # 启发式: wp 至少有 paper_refs / dataset_refs / baseline_refs / metric_refs 中至少 2 个
        for wp in wp_list:
            refs_count = len(wp.get("evidence_refs") or []) + len(wp.get("dataset_refs") or []) + len(wp.get("baseline_refs") or [])
            if refs_count < 2:
                issues.append(f"工作包 {wp.get('wp_id', '?')} 引用 < 2 条 evidence")
                suggestions.append(f"为 {wp.get('wp_id', '?')} 补 paper / dataset / repo 引用")
                score -= 15

    score = max(0.0, score)
    refs: list[dict] = []
    for wp in wp_list[:3]:
        for r in (wp.get("evidence_refs") or []):
            refs.append(r)
            if len(refs) >= 3:
                break
    return ReportQualityCheck(
        dimension="工作包",
        result=_result_for_score(score),
        score=score,
        evidence_refs=[_to_ref(r) for r in refs],
        issues=issues,
        suggestions=suggestions,
    )


def _check_innovation(reason_refs: dict, all_refs: list) -> ReportQualityCheck:
    """检查 reason_evidence_refs 覆盖."""

    issues: list[str] = []
    suggestions: list[str] = []
    score = 100.0

    if not reason_refs:
        issues.append("推荐理由没有 evidence 绑定")
        suggestions.append("给每条 reason_evidence_refs 补 paper / dataset 引用")
        score -= 30
    else:
        # 至少 50% 的 reason 有 ref
        with_ref = sum(1 for k, v in reason_refs.items() if v)
        coverage = with_ref / max(len(reason_refs), 1)
        if coverage < 0.5:
            issues.append(f"reason_evidence_refs 覆盖率仅 {coverage:.0%}")
            suggestions.append("补齐未绑定的 reason")
            score -= 25

    score = max(0.0, score)
    refs: list[dict] = []
    for v in reason_refs.values():
        if isinstance(v, list):
            refs.extend(v)
            if len(refs) >= 3:
                break
    return ReportQualityCheck(
        dimension="创新点",
        result=_result_for_score(score),
        score=score,
        evidence_refs=[_to_ref(r) for r in refs],
        issues=issues,
        suggestions=suggestions,
    )


def _check_risks(feas: dict, all_refs: list) -> ReportQualityCheck:
    """检查风险预案是否覆盖 missing_evidence + partial 证据."""

    issues: list[str] = []
    suggestions: list[str] = []
    score = 100.0

    missing = feas.get("missing_evidence", []) or []
    missing_refs = feas.get("missing_ref_reasons", []) or []

    if not missing and not missing_refs:
        issues.append("风险预案为空, 未列出缺失证据")
        suggestions.append("在 feasibility.missing_evidence / missing_ref_reasons 列出风险")
        score -= 25

    # partial 证据是否列出
    partial_refs = [r for r in all_refs if r.get("verification_status") == "partial"]
    if partial_refs:
        score -= 5 * min(len(partial_refs), 5)

    score = max(0.0, score)
    return ReportQualityCheck(
        dimension="风险预案",
        result=_result_for_score(score),
        score=score,
        issues=issues,
        suggestions=suggestions,
    )


def _check_clarity(snapshot: dict, feas: dict) -> ReportQualityCheck:
    """检查 markdown 完整性 + 占位符."""

    issues: list[str] = []
    suggestions: list[str] = []
    score = 100.0

    # 检查 FinalPackage 是否存在
    feas_obj = snapshot.get("feasibility") or {}
    if not feas_obj.get("verdict"):
        issues.append("可行性 verdict 缺失")
        score -= 20

    proposal = snapshot.get("proposal_recommendation") or {}
    if not proposal.get("recommended_topic"):
        issues.append("推荐题目缺失")
        score -= 20

    # 检查 coverage
    coverage = feas_obj.get("confidence", 0) or 0
    if coverage < 0.5:
        issues.append(f"evidence confidence 仅 {coverage:.2f}, 表达可信度不足")
        suggestions.append("补核心 evidence 提升 confidence 到 0.7+")
        score -= 15

    score = max(0.0, score)
    return ReportQualityCheck(
        dimension="表达清晰度",
        result=_result_for_score(score),
        score=score,
        issues=issues,
        suggestions=suggestions,
    )


# ---------- 答辩问题 ---------- #


def _build_defense_questions(snapshot: dict, all_refs: list) -> list[DefenseQuestion]:
    """生成 6 题标准 + 绑定 evidence_refs."""

    feas = snapshot.get("feasibility") or {}
    proposal = snapshot.get("proposal_recommendation") or {}
    topic = proposal.get("recommended_topic") or ""

    questions: list[DefenseQuestion] = [
        DefenseQuestion(
            question=f"题目 '{topic[:40]}' 的研究边界如何界定? 与已有方法相比核心差异是什么?",
            risk_level="高",
            suggested_answer="题目边界限定在 [方法/对象/任务], 差异在于 [具体技术]. 已在风险预案中列出界定关键词.",
        ),
        DefenseQuestion(
            question="数据集 license 是否允许用于毕业设计? 是否需要额外授权?",
            risk_level="中",
            suggested_answer="已确认数据集 license 为 [CC-BY/MIT/...], 开题报告 citation 中标注. 无额外授权.",
        ),
        DefenseQuestion(
            question="复现 baseline 的硬件要求是什么? 训练 / 推理耗时估算?",
            risk_level="中",
            suggested_answer="baseline 在 [GPU 型号] 单卡约 [N] 小时完成训练; 推理 [FPS]. 已记录在数据章节.",
        ),
        DefenseQuestion(
            question="题目风险词 (智能 / 通用 / 高精度 / 实时) 如何界定?",
            risk_level="高",
            suggested_answer="题目边界限定为 '特定场景下的智能' 等, 已在 Section 三说明量化指标.",
        ),
        DefenseQuestion(
            question="创新点是否可量化? 与 SOTA 对比的具体指标提升?",
            risk_level="中",
            suggested_answer="创新点对应 [mAP / Recall / FPS] 提升 [X]%, 已在工作包设计中给出实验方案.",
        ),
        DefenseQuestion(
            question="工作包之间的依赖关系? 如果分支失败如何降级?",
            risk_level="低",
            suggested_answer="WP1 → WP2 → WP3 顺序; 若 WP2 失败, 退化到 baseline + ablation, 已在 pivot 路线中提供 conservative 选项.",
        ),
    ]

    # 尝试绑定 evidence_refs
    paper_refs = [r for r in all_refs if r.get("evidence_type") == "paper"]
    dataset_refs = [r for r in all_refs if r.get("evidence_type") == "dataset"]
    repo_refs = [r for r in all_refs if r.get("evidence_type") in ("repo", "baseline")]

    if paper_refs:
        questions[0].evidence_refs = [_to_ref(paper_refs[0])]
        questions[4].evidence_refs = [_to_ref(paper_refs[0])]
    if dataset_refs:
        questions[1].evidence_refs = [_to_ref(dataset_refs[0])]
    if repo_refs:
        questions[2].evidence_refs = [_to_ref(repo_refs[0])]

    return questions


# ---------- helpers ---------- #


def _to_ref(r: dict) -> EvidenceRef:
    """从 dict 构造 EvidenceRef, 容错缺失字段."""

    try:
        return EvidenceRef.model_validate({
            "evidence_id": r.get("evidence_id", ""),
            "evidence_type": r.get("evidence_type") or "paper",
            "title": r.get("title") or "(无标题)",
            "role": r.get("role") or "supports",
            "reason": r.get("reason") or "",
            "score": r.get("score"),
            "review_status": r.get("review_status") or "pending",
            "url": r.get("url"),
        })
    except Exception:
        return EvidenceRef(
            evidence_id=r.get("evidence_id", ""),
            evidence_type=r.get("evidence_type") or "paper",
            title=r.get("title") or "(无标题)",
            role="supports",
            reason="",
            score=None,
            review_status="pending",
        )


def render_quality_markdown(review: ReportQualityReview) -> str:
    """独立 Markdown 导出 (SOP §7.3)."""

    lines: list[str] = []
    lines.append(f"# 报告质量审核 (Report Quality Review)")
    lines.append("")
    lines.append(f"> Project: `{review.project_id}`")
    lines.append(f"> 审核时间: {review.reviewed_at}")
    lines.append("")
    lines.append(f"## 总体判断: **{review.verdict}** ({review.score:.1f} / 100)")
    lines.append("")

    lines.append("## 8 维检查")
    lines.append("")
    lines.append("| 维度 | 结果 | 分数 | 问题数 |")
    lines.append("|---|---|---:|---:|")
    for c in review.checks:
        lines.append(f"| {c.dimension} | {c.result} | {c.score:.0f} | {len(c.issues)} |")
    lines.append("")

    for c in review.checks:
        lines.append(f"### {c.dimension}: {c.result} ({c.score:.0f})")
        if c.issues:
            lines.append("")
            lines.append("**问题:**")
            for issue in c.issues:
                lines.append(f"- {issue}")
        if c.suggestions:
            lines.append("")
            lines.append("**建议:**")
            for s in c.suggestions:
                lines.append(f"- {s}")
        if c.evidence_refs:
            lines.append("")
            lines.append(f"**关联证据 ({len(c.evidence_refs)}):** " + ", ".join(r.evidence_id for r in c.evidence_refs))
        lines.append("")

    lines.append("## 修改清单")
    lines.append("")
    if review.revision_checklist:
        for line in review.revision_checklist:
            lines.append(f"- {line}")
    else:
        lines.append("(无)")
    lines.append("")

    lines.append("## 开题答辩可能追问")
    lines.append("")
    for q in review.defense_questions:
        lines.append(f"### [{q.risk_level} 风险] {q.question}")
        lines.append("")
        lines.append(f"**建议回答:** {q.suggested_answer}")
        if q.evidence_refs:
            lines.append("")
            lines.append("**关联证据:** " + ", ".join(r.evidence_id for r in q.evidence_refs))
        lines.append("")

    return "\n".join(lines)


# ---------- 测试用 ---------- #


def reset_quality_reviews() -> None:
    global _REVIEW
    _REVIEW = {}