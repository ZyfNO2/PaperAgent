"""EvidenceRef 强制挂接 (Session 7 §5 + §6).

让可行性/Pivot/工作包/轻审核都引用 evidence_pool 里的具体 evidence_id.

规则 (§6):
- review_status in {core, accepted, background} → 可作为 supports
- review_status in {pending, needs_check} → 只能作 warns / blocks
- review_status = rejected → 只能作 alternative (反例/排除)
- ref_priority = 0.40 review + 0.30 score + 0.15 type + 0.10 recency + 0.05 url_verified
"""

from __future__ import annotations

from typing import Any, Literal

from ..schemas import (
    EvidenceRef,
    FeasibilitySummary,
    PivotRoute,
    ProposalRecommendation,
    LightReview,
    WorkPackageSuggestion,
)


# ---------- ref_priority 公式 (§6.2) ---------- #

REVIEW_WEIGHT = {
    "core": 1.00,
    "accepted": 0.80,
    "background": 0.50,
    "pending": 0.20,
    "needs_check": 0.10,
    "rejected": 0.00,
}

# Session 9 §6: workspace_lane bonus 影响 ref_priority
LANE_BONUS = {
    "selected": 0.15,
    "user_preferred": 0.10,
    "system_found": 0.00,
    "rejected": -1.00,  # 直接打到底, 排序时永远垫底
}

PAPER_TYPE_WEIGHT = {
    "baseline_method": 0.90, "application": 0.85, "benchmark": 0.80,
    "survey": 0.75, "dataset_paper": 0.70, "case_study": 0.55,
    "unknown": 0.30, "irrelevant": 0.00,
}
DATASET_STATUS_WEIGHT = {
    "ready": 1.00, "needs_preprocess": 0.80, "needs_permission": 0.50,
    "weak_match": 0.30, "unverified": 0.20, "invalid": 0.00,
}
REPO_TYPE_WEIGHT = {
    "official": 1.00, "baseline_framework": 0.95, "reproduction": 0.85,
    "demo_only": 0.40, "unknown": 0.30, "not_reproducible": 0.00,
}


def _type_weight(evidence_type: str, item: dict[str, Any]) -> float:
    if evidence_type == "paper":
        return PAPER_TYPE_WEIGHT.get(item.get("paper_type") or "unknown", 0.30)
    if evidence_type == "dataset":
        return DATASET_STATUS_WEIGHT.get(item.get("dataset_status") or "unverified", 0.20)
    if evidence_type == "repo" or evidence_type == "baseline":
        return REPO_TYPE_WEIGHT.get(item.get("repo_type") or "unknown", 0.30)
    return 0.30


def _recency(year: int | None, current_year: int = 2026) -> float:
    if not year:
        return 0.3
    age = current_year - year
    if age <= 3: return 1.0
    if age <= 6: return 0.6
    if age <= 10: return 0.3
    return 0.1


def _ref_priority(item: dict[str, Any]) -> float:
    """§6.2 + Session 9 §6: 0.40 review + 0.30 score + 0.15 type + 0.10 recency + 0.05 url_verified + lane_bonus."""

    review_w = REVIEW_WEIGHT.get(item.get("review_status") or "pending", 0.20)
    score = item.get("relevance_score") or item.get("quality_score") or 0.5
    type_w = _type_weight(item.get("evidence_type") or "paper", item)
    rec_w = _recency(item.get("year"))
    url_v = 1.0 if (item.get("url") or item.get("repository_url") or item.get("download")) else 0.0
    lane_b = LANE_BONUS.get(item.get("workspace_lane") or "system_found", 0.0)
    return round(
        0.40 * review_w
        + 0.30 * score
        + 0.15 * type_w
        + 0.10 * rec_w
        + 0.05 * url_v
        + lane_b,
        3,
    )


# ---------- evidence_pool 抽象 (统一 paper/dataset/repo) ---------- #


def _collect_evidence_pool(
    papers: list[Any], datasets: list[Any], repos: list[Any], *,
    project_id: str = "",
    extras: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """从 evidence_summary 拉 evidence pool, 统一字段.

    输出 dict 形如:
    {
      "evidence_id": "auto_paper_xxx_001",
      "evidence_type": "paper|dataset|repo",
      "title": str,
      "url": str,
      "year": int|None,
      "review_status": str,
      "relevance_score": float|None,
      "quality_score": float|None,
      "paper_type": str,
      "dataset_status": str,
      "repo_type": str,
    }
    extras: 手动入池的 evidence_item (从 evidence ledger 拉), 优先匹配.
    """

    pool: list[dict[str, Any]] = []

    # 手动入池的优先 (有真实 evidence_id)
    if extras:
        for e in extras:
            d = e if isinstance(e, dict) else e.model_dump()
            pool.append({
                "evidence_id": d.get("evidence_id", ""),
                "evidence_type": d.get("evidence_type", "paper"),
                "title": d.get("title", ""),
                "url": d.get("url"),
                "year": d.get("year"),
                "review_status": d.get("review_status", "pending"),
                "relevance_score": d.get("relevance_score"),
                "quality_score": d.get("quality_score"),
                "paper_type": d.get("paper_type") or "unknown",
                "dataset_status": d.get("dataset_status") or "unverified",
                "repo_type": d.get("repo_type") or "unknown",
                "workspace_lane": d.get("workspace_lane") or "system_found",  # Session 9
            })

    # 自动入池 (从 evidence_summary 的 papers/datasets/baselines, evidence_id 是合成 ID)
    if papers:
        for i, p in enumerate(papers):
            if isinstance(p, dict):
                pid = p.get("paper_id") or p.get("evidence_id")
            else:
                pid = p.paper_id if hasattr(p, "paper_id") else None
            pool.append({
                "evidence_id": pid or f"auto_paper_{project_id[:6] if project_id else 'x'}_{i+1:03d}",
                "evidence_type": "paper",
                "title": p.title if hasattr(p, "title") else p.get("title", ""),
                "url": p.url if hasattr(p, "url") else p.get("url"),
                "year": p.year if hasattr(p, "year") else p.get("year"),
                "review_status": "accepted",  # 自动入池的默认 accepted (Session 5)
                "relevance_score": getattr(p, "relevance_score", None) or (p.get("relevance_score") if isinstance(p, dict) else None),
                "quality_score": None,
                "paper_type": getattr(p, "paper_type", None) or (p.get("paper_type") if isinstance(p, dict) else None) or "unknown",
                "dataset_status": "unverified",
                "repo_type": "unknown",
                "workspace_lane": "system_found",  # Session 9: 自动入池默认 system_found
            })

    if datasets:
        for i, d_ in enumerate(datasets):
            if isinstance(d_, dict):
                did = d_.get("dataset_id") or d_.get("evidence_id")
            else:
                did = d_.dataset_id if hasattr(d_, "dataset_id") else None
            pool.append({
                "evidence_id": did or f"auto_dataset_{project_id[:6] if project_id else 'x'}_{i+1:03d}",
                "evidence_type": "dataset",
                "title": d_.name if hasattr(d_, "name") else d_.get("name", "") if isinstance(d_, dict) else "",
                "url": d_.download if hasattr(d_, "download") else (d_.get("download") if isinstance(d_, dict) else None),
                "year": None,
                "review_status": "accepted" if (getattr(d_, "fit", "低") or "低") in ("高", "中") else "pending",
                "relevance_score": None,
                "quality_score": getattr(d_, "quality_score", None) or (d_.get("quality_score") if isinstance(d_, dict) else None),
                "paper_type": "unknown",
                "dataset_status": getattr(d_, "dataset_status", None) or (d_.get("dataset_status") if isinstance(d_, dict) else None) or "unverified",
                "repo_type": "unknown",
                "workspace_lane": "system_found",  # Session 9
            })

    if repos:
        for i, b in enumerate(repos):
            if isinstance(b, dict):
                bid = b.get("baseline_id") or b.get("evidence_id")
            else:
                bid = b.baseline_id if hasattr(b, "baseline_id") else None
            pool.append({
                "evidence_id": bid or f"auto_repo_{project_id[:6] if project_id else 'x'}_{i+1:03d}",
                "evidence_type": "repo",
                "title": b.name if hasattr(b, "name") else (b.get("name", "") if isinstance(b, dict) else ""),
                "url": b.repository_url if hasattr(b, "repository_url") else (b.get("repository_url") if isinstance(b, dict) else None),
                "year": None,
                "review_status": "accepted",
                "relevance_score": None,
                "quality_score": getattr(b, "quality_score", None) or (b.get("quality_score") if isinstance(b, dict) else None),
                "paper_type": "unknown",
                "dataset_status": "unverified",
                "repo_type": getattr(b, "repo_type", None) or (b.get("repo_type") if isinstance(b, dict) else None) or "unknown",
                "workspace_lane": "system_found",  # Session 9
            })

    return pool


def _select_role(review_status: str, score: float | None, evidence_type: str, lane: str = "system_found") -> Literal["supports", "warns", "blocks", "background", "alternative"]:
    """§6.1: review_status 决定 role 候选. Session 9: rejected lane 永远不进 supports."""

    if lane == "rejected" or review_status == "rejected":
        return "alternative"  # 反例/排除
    if review_status in ("needs_check", "pending"):
        return "warns" if (score is None or score < 0.5) else "background"
    if review_status in ("accepted", "core", "background"):
        return "supports"
    return "background"


def _make_ref(item: dict[str, Any], role: str, reason: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=item.get("evidence_id", ""),
        evidence_type=item.get("evidence_type", "paper"),
        title=item.get("title", ""),
        role=role,  # type: ignore
        reason=reason,
        score=item.get("relevance_score") or item.get("quality_score"),
        review_status=item.get("review_status", "pending"),
        url=item.get("url"),
        url_verified=bool(item.get("url")),
    )


# ---------- FeasibilitySummary 挂载 (§5.2) ---------- #


def build_feasibility_refs(
    feasibility: FeasibilitySummary,
    papers: list[Any], datasets: list[Any], repos: list[Any], *,
    extras: list[dict[str, Any]] | None = None,
    project_id: str = "",
) -> FeasibilitySummary:
    """§5.2: 给 FeasibilitySummary 挂 evidence_refs / blocking_refs / confidence."""

    pool = _collect_evidence_pool(papers, datasets, repos, extras=extras, project_id=project_id)
    if not pool:
        feasibility.evidence_refs = []
        feasibility.blocking_refs = []
        feasibility.confidence = 0.0
        feasibility.missing_ref_reasons = ["evidence pool 为空, 无法挂载 refs"]
        return feasibility

    # 按 ref_priority 排序
    pool.sort(key=_ref_priority, reverse=True)
    by_type: dict[str, list[dict]] = {"paper": [], "dataset": [], "repo": []}
    for it in pool:
        by_type[it.get("evidence_type", "paper")].append(it)

    supports: list[EvidenceRef] = []
    blocks: list[EvidenceRef] = []
    missing: list[str] = []

    # 论文 supports (取 top 3)
    for p in by_type["paper"][:3]:
        role = _select_role(p.get("review_status", "pending"), p.get("relevance_score"), "paper", p.get("workspace_lane", "system_found"))
        if role == "supports":
            supports.append(_make_ref(p, "supports", f"arXiv 命中, 相关性 {p.get('relevance_score', 0):.2f}"))
        elif role in ("warns", "blocks"):
            blocks.append(_make_ref(p, role, f"论文相关度低或待核查 (score={p.get('relevance_score')})"))
        else:
            supports.append(_make_ref(p, "background", f"论文 (paper_type={p.get('paper_type')})"))

    # 数据集 supports (取 top 1)
    if by_type["dataset"]:
        d = by_type["dataset"][0]
        role = _select_role(d.get("review_status", "pending"), d.get("quality_score"), "dataset", d.get("workspace_lane", "system_found"))
        if role == "supports":
            supports.append(_make_ref(d, "supports", f"数据集 {d.get('dataset_status')}, 质量分 {d.get('quality_score', 0):.2f}"))
        elif role in ("warns", "blocks"):
            blocks.append(_make_ref(d, role, f"数据集可用性低 (status={d.get('dataset_status')})"))
            missing.append("缺明确公开数据集 (license/scale 未确认)")
    else:
        missing.append("未匹配到公开数据集")

    # Repo supports (取 top 1)
    if by_type["repo"]:
        r = by_type["repo"][0]
        role = _select_role(r.get("review_status", "pending"), r.get("quality_score"), "repo", r.get("workspace_lane", "system_found"))
        if role == "supports":
            supports.append(_make_ref(r, "supports", f"Repo {r.get('repo_type')}, 复现分 {r.get('quality_score', 0):.2f}"))
        elif role in ("warns", "blocks"):
            blocks.append(_make_ref(r, role, f"Repo 不可复现 (type={r.get('repo_type')})"))
            missing.append("无可复现 baseline (需手动补)")
    else:
        missing.append("无 baseline / repo")

    # confidence = 平均 ref_priority
    if supports:
        avg_pri = sum(_ref_priority(p) for p in pool[:len(supports)]) / len(supports)
        confidence = round(min(1.0, avg_pri), 3)
    else:
        confidence = 0.0

    # verdict 决定: 缺关键 ref 时降级
    if feasibility.verdict == "可做":
        if not by_type["paper"] or not by_type["dataset"] or not by_type["repo"]:
            feasibility.verdict = "收缩后可做"
            feasibility.reason += " (Session 7 证据挂接: 缺关键 ref)"
    elif feasibility.verdict == "可转向":
        if not by_type["paper"]:
            feasibility.verdict = "暂缓"
            feasibility.reason += " (Session 7 证据挂接: 无 paper ref)"

    feasibility.evidence_refs = supports
    feasibility.blocking_refs = blocks
    feasibility.missing_ref_reasons = missing
    feasibility.confidence = confidence
    return feasibility


# ---------- PivotRoute 挂载 (§5.3) ---------- #


def build_pivot_refs(
    route: PivotRoute,
    papers: list[Any], datasets: list[Any], repos: list[Any], *,
    extras: list[dict[str, Any]] | None = None,
    project_id: str = "",
) -> PivotRoute:
    """§5.3: 给 PivotRoute 挂 evidence_refs / risk_reduction_refs / confidence."""

    pool = _collect_evidence_pool(papers, datasets, repos, extras=extras, project_id=project_id)
    pool.sort(key=_ref_priority, reverse=True)
    by_type: dict[str, list[dict]] = {"paper": [], "dataset": [], "repo": []}
    for it in pool:
        by_type[it.get("evidence_type", "paper")].append(it)

    # supports: top 2 paper + top 1 dataset + top 1 repo
    refs: list[EvidenceRef] = []
    for p in by_type["paper"][:2]:
        role = _select_role(p.get("review_status", "pending"), p.get("relevance_score"), "paper", p.get("workspace_lane", "system_found"))
        if role == "supports":
            refs.append(_make_ref(p, "supports", f"路线支撑: {p.get('paper_type')}"))
    for d in by_type["dataset"][:1]:
        role = _select_role(d.get("review_status", "pending"), d.get("quality_score"), "dataset", d.get("workspace_lane", "system_found"))
        if role == "supports":
            refs.append(_make_ref(d, "supports", f"路线数据集: {d.get('dataset_status')}"))
    for r in by_type["repo"][:1]:
        role = _select_role(r.get("review_status", "pending"), r.get("quality_score"), "repo", r.get("workspace_lane", "system_found"))
        if role == "supports":
            refs.append(_make_ref(r, "supports", f"路线 baseline: {r.get('repo_type')}"))

    # risk_reduction_refs: removed_keywords 触发 (heuristic: 看 risk 词对应论文)
    risk_kw = set(route.removed_keywords or [])
    risk_refs: list[EvidenceRef] = []
    for p in by_type["paper"]:
        title_l = (p.get("title") or "").lower()
        if any(k.lower() in title_l for k in risk_kw if k):
            risk_refs.append(_make_ref(p, "background", f"风险降低依据: 去除 {risk_kw & {p.get('title', '')}}"))

    missing = []
    if not by_type["dataset"]:
        missing.append("无公开数据集 (路线需自采或加 dataset 引用)")
    if not by_type["repo"]:
        missing.append("无可复现 baseline (需手动补)")

    confidence = round(min(1.0, sum(_ref_priority(p) for p in pool[:len(refs)]) / max(len(refs), 1)), 3) if refs else 0.0

    route.evidence_refs = refs
    route.risk_reduction_refs = risk_refs
    route.missing_evidence = missing
    route.confidence = confidence
    return route


# ---------- WorkPackage 挂载 (§5.4) ---------- #


def build_wp_refs(
    wp: WorkPackageSuggestion,
    papers: list[Any], datasets: list[Any], repos: list[Any], *,
    extras: list[dict[str, Any]] | None = None,
    project_id: str = "",
) -> WorkPackageSuggestion:
    """§5.4: 给 WorkPackage 挂 paper/dataset/repo/metric refs + open_questions."""

    pool = _collect_evidence_pool(papers, datasets, repos, extras=extras, project_id=project_id)
    pool.sort(key=_ref_priority, reverse=True)
    by_type: dict[str, list[dict]] = {"paper": [], "dataset": [], "repo": []}
    for it in pool:
        by_type[it.get("evidence_type", "paper")].append(it)

    paper_refs: list[EvidenceRef] = []
    dataset_refs: list[EvidenceRef] = []
    baseline_refs: list[EvidenceRef] = []
    metric_refs: list[EvidenceRef] = []
    open_q: list[str] = []

    for p in by_type["paper"][:2]:
        role = _select_role(p.get("review_status", "pending"), p.get("relevance_score"), "paper", p.get("workspace_lane", "system_found"))
        if role == "supports":
            paper_refs.append(_make_ref(p, "supports", f"WP 论文支撑: {p.get('paper_type')}"))

    if by_type["dataset"]:
        d = by_type["dataset"][0]
        role = _select_role(d.get("review_status", "pending"), d.get("quality_score"), "dataset", d.get("workspace_lane", "system_found"))
        if role == "supports":
            dataset_refs.append(_make_ref(d, "supports", f"WP 数据集: {d.get('dataset_status')}"))
        else:
            open_q.append(f"数据集 {d.get('evidence_id')} 状态 {d.get('dataset_status')}, 需人工确认")
    else:
        open_q.append("WP 缺数据集 ref (需自采 100-200 张 或 找公开数据集)")

    if by_type["repo"]:
        r = by_type["repo"][0]
        role = _select_role(r.get("review_status", "pending"), r.get("quality_score"), "repo", r.get("workspace_lane", "system_found"))
        if role == "supports":
            baseline_refs.append(_make_ref(r, "supports", f"WP baseline: {r.get('repo_type')}"))
        else:
            open_q.append(f"Repo {r.get('evidence_id')} 不可复现 (type={r.get('repo_type')}), 需找替代")
    else:
        open_q.append("WP 缺 baseline ref")

    if not paper_refs:
        open_q.append("WP 缺 paper ref (方法依据不足)")

    wp.evidence_refs = paper_refs + dataset_refs + baseline_refs
    wp.dataset_refs = dataset_refs
    wp.baseline_refs = baseline_refs
    wp.metric_refs = metric_refs
    wp.open_questions = open_q
    if open_q and len(open_q) >= 2:
        wp.status = "needs_evidence"
    return wp


# ---------- LightReview 挂载 (§5.6) ---------- #


_REVIEW_DIM_TO_TYPE = {
    "题目边界": "paper",
    "数据集": "dataset",
    "Baseline": "repo",
    "工作量": "paper",
    "开题表达": "paper",
}


def build_review_refs(
    review: LightReview,
    papers: list[Any], datasets: list[Any], repos: list[Any], *,
    extras: list[dict[str, Any]] | None = None,
    project_id: str = "",
) -> LightReview:
    """§5.6: 给 LightReview 5 维 checks 挂 evidence_refs + confidence."""

    pool = _collect_evidence_pool(papers, datasets, repos, extras=extras, project_id=project_id)
    pool.sort(key=_ref_priority, reverse=True)
    by_type: dict[str, list[dict]] = {"paper": [], "dataset": [], "repo": []}
    for it in pool:
        by_type[it.get("evidence_type", "paper")].append(it)

    for check in review.checks:
        dim = check.dimension
        ev_type = _REVIEW_DIM_TO_TYPE.get(dim, "paper")
        items = by_type[ev_type][:2]
        refs: list[EvidenceRef] = []
        for it in items:
            role = _select_role(it.get("review_status", "pending"), it.get("relevance_score") or it.get("quality_score"), ev_type, it.get("workspace_lane", "system_found"))
            refs.append(_make_ref(it, role, f"{dim} 维度引用: {it.get('evidence_type')}"))
        check.evidence_refs = refs
        check.confidence = round(sum(_ref_priority(p) for p in items) / max(len(items), 1), 3) if items else 0.0
    return review


# ---------- ProposalRecommendation 挂载 (§5.5) ---------- #


def build_proposal_refs(
    proposal: ProposalRecommendation,
    papers: list[Any], datasets: list[Any], repos: list[Any], *,
    extras: list[dict[str, Any]] | None = None,
    project_id: str = "",
) -> tuple[ProposalRecommendation, list[str]]:
    """§5.5: 给 ProposalRecommendation 挂 topic_evidence_refs + reason_evidence_refs.

    Returns: (proposal, unsupported_claims) — unsupported_claims 列出没绑证据的理由.
    """

    pool = _collect_evidence_pool(papers, datasets, repos, extras=extras, project_id=project_id)
    pool.sort(key=_ref_priority, reverse=True)
    by_type: dict[str, list[dict]] = {"paper": [], "dataset": [], "repo": []}
    for it in pool:
        by_type[it.get("evidence_type", "paper")].append(it)

    # topic_evidence_refs: 选 1 paper + 1 dataset (推荐题目的主要依据)
    topic_refs: list[EvidenceRef] = []
    if by_type["paper"]:
        p = by_type["paper"][0]
        topic_refs.append(_make_ref(p, "supports", f"题目推荐依据: {p.get('paper_type')}"))
    if by_type["dataset"]:
        d = by_type["dataset"][0]
        topic_refs.append(_make_ref(d, "supports", f"题目推荐数据集: {d.get('dataset_status')}"))
    if by_type["repo"]:
        r = by_type["repo"][0]
        topic_refs.append(_make_ref(r, "supports", f"题目推荐 baseline: {r.get('repo_type')}"))

    # reason_evidence_refs: 每条 reason 至少绑 1 ref, 没绑的进 unsupported_claims
    reason_refs: dict[str, list[EvidenceRef]] = {}
    unsupported: list[str] = []
    pool_keywords = {kw for p in pool for kw in [p.get("title", "")] if p.get("title")}

    for i, reason in enumerate(proposal.recommendation_reason or []):
        # 启发式匹配: reason 里的关键词是否出现在 evidence 标题里
        matched: list[EvidenceRef] = []
        for p in pool:
            title = p.get("title") or ""
            if any(w in title for w in (reason or "").split() if len(w) >= 4):
                matched.append(_make_ref(p, "supports", f"理由 {i+1} 引用: {title[:40]}"))
                if len(matched) >= 2:
                    break
        # fallback: 绑所有 top-3 paper (通用支持)
        if not matched and by_type["paper"]:
            matched = [_make_ref(by_type["paper"][0], "supports", f"理由 {i+1} 通用引用")]
        if matched:
            reason_refs[f"reason_{i+1}"] = matched
        else:
            unsupported.append(f"理由 {i+1}: {reason[:60]}")
            reason_refs[f"reason_{i+1}"] = []

    proposal.topic_evidence_refs = topic_refs
    proposal.reason_evidence_refs = reason_refs
    return proposal, unsupported


# ---------- coverage_score 算 (§7.2) ---------- #


def coverage_score(feasibility: FeasibilitySummary, proposal: ProposalRecommendation | None = None) -> float:
    """§7.2: 算 coverage_score ∈ [0, 1]."""

    # 4 个维度: feasibility, pivot_routes, work_packages, light_review
    # 简化为 feasibility.evidence_refs / topic_refs / reason coverage

    feas_has = 1.0 if feasibility.evidence_refs else 0.0
    feas_n = len(feasibility.evidence_refs) if feasibility.evidence_refs else 0
    feas_score = (feas_has * 0.4) + (min(feas_n, 3) / 3 * 0.6)

    if not proposal:
        return round(feas_score, 3)

    # pivot: 至少有 1 条有 refs
    pivot_score = 0.0
    if proposal.pivot_routes:
        n_with = sum(1 for p in proposal.pivot_routes if p.evidence_refs)
        pivot_score = (n_with / len(proposal.pivot_routes)) * 1.0

    # WP: 至少有 1 个有 refs
    wp_score = 0.0
    if proposal.work_packages:
        n_with = sum(1 for w in proposal.work_packages if w.evidence_refs)
        wp_score = (n_with / len(proposal.work_packages)) * 1.0

    # topic refs
    topic_score = 1.0 if proposal.topic_evidence_refs else 0.0

    # 4 维度平均
    return round((feas_score + pivot_score + wp_score + topic_score) / 4, 3)
