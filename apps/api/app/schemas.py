"""OneTopic MVP — Pydantic schemas.

对齐 Plan/TopicPilot-CN_OneTopic_MVP_修改SOP.md §13。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------- 入参 ---------- #

GoalLevel = Literal["保毕业", "稳中求新", "冲高水平"]


class OneTopicRequest(BaseModel):
    """POST /analyze 请求体 — 用户只输入一个题目 (SOP §6.2)."""

    model_config = ConfigDict(extra="forbid")

    raw_topic: str = Field(min_length=1, description="用户原始题目")
    goal_level: GoalLevel = Field(default="保毕业", description="目标档位")
    major: str | None = Field(default=None, description="可选: 专业")
    advisor_direction: str | None = Field(default=None, description="可选: 导师方向")
    degree_type: Literal["本科", "硕士", "博士", "未知"] = Field(default="未知")
    prefer: Literal["auto", "llm", "heuristic"] = Field(
        default="auto",
        description="auto=LLM 优先失败 fallback heuristic; heuristic=强制规则",
    )
    # Session 3: Human Gate 1+2 (SOP §6.2). 用户编辑过的 keywords / 检索词,
    # 传进来时直接用, 不再走自动拆解.
    confirmed_keywords: dict | None = Field(
        default=None,
        description="Gate 1 用户确认后的关键词; 给定后跳过自动拆解 (dict 形如 {method_keywords, task_keywords, ...})",
    )
    confirmed_search_plan: dict | None = Field(
        default=None,
        description="Gate 2 用户确认后的检索词; 给定后跳过自动构建 (dict 形如 {paper_queries, dataset_queries, ...})",
    )
    project_id_override: str | None = Field(
        default=None,
        description="Session 3 regenerate: 沿用已有 project_id, 避免新生成",
    )


# ---------- 题目理解 ---------- #


class TopicUnderstanding(BaseModel):
    """题目意图理解 — 短文 + 标准化题目。"""

    raw_topic: str
    normalized_topic: str
    intent_zh: str = Field(description="中文 1-2 句话讲用户想做什么")
    is_specific_object: bool = Field(description="题目里是否有具体研究对象 (钢材/桥梁/...)")


# ---------- 关键词拆解 (§5) ---------- #


class KeywordBreakdown(BaseModel):
    """OneTopic §5.1 — 关键词拆解 + 风险词。"""

    method_keywords: list[str] = Field(default_factory=list, description="方法词: YOLO / Transformer / ...")
    task_keywords: list[str] = Field(default_factory=list, description="任务词: 检测 / 分类 / ...")
    object_keywords: list[str] = Field(default_factory=list, description="对象词: 钢材表面缺陷 / ...")
    scenario_keywords: list[str] = Field(default_factory=list, description="场景词: 工业质检 / ...")
    metric_keywords: list[str] = Field(default_factory=list, description="指标词: mAP / Recall / ...")
    risk_terms: list[str] = Field(default_factory=list, description="风险词: 智能 / 高精度 / 实时 / ...")
    query_keywords_zh: list[str] = Field(default_factory=list)
    query_keywords_en: list[str] = Field(default_factory=list)


# ---------- 三线检索 (§6) ---------- #


class SearchPlan(BaseModel):
    """OneTopic §6 — 论文 / 数据集 / 工程 三线检索词。"""

    paper_queries: list[str] = Field(default_factory=list)
    dataset_queries: list[str] = Field(default_factory=list)
    engineering_queries: list[str] = Field(default_factory=list)
    query_total: int = 0


class PaperHit(BaseModel):
    model_config = ConfigDict(extra="allow")

    paper_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    url: str | None = None
    summary: str | None = None
    summary_zh: str | None = None
    source: Literal["arXiv", "heuristic", "user-uploaded"] = "heuristic"
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0, description="PaperRelevance 评分 (SOP §7.3)")
    paper_type: str | None = Field(default=None, description="survey / baseline_method / application / dataset_paper / benchmark / case_study / irrelevant / unknown")
    score_breakdown: dict | None = Field(default=None, description="6 维评分明细 (前端可视化)")


class DatasetHit(BaseModel):
    model_config = ConfigDict(extra="allow")

    dataset_id: str
    name: str
    scale: str | None = None
    license: str | None = None
    download: str | None = None
    fit: Literal["高", "中", "低", "未知"] = "中"
    source: Literal["public-known", "heuristic"] = "heuristic"
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0, description="DatasetScore 评分 (SOP §7.4)")
    dataset_status: str | None = Field(default=None, description="ready / needs_preprocess / needs_permission / weak_match / unverified / invalid")
    score_breakdown: dict | None = Field(default=None, description="7 维评分明细")


class BaselineHit(BaseModel):
    model_config = ConfigDict(extra="allow")

    baseline_id: str
    name: str
    paper_title: str | None = None
    repository_url: str | None = None
    license: str | None = None
    reproduce_difficulty: Literal["低", "中", "高", "未知"] = "中"
    source: Literal["github", "paper-claimed", "heuristic"] = "heuristic"
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0, description="RepoScore 评分 (SOP §7.5)")
    repo_type: str | None = Field(default=None, description="official / reproduction / baseline_framework / demo_only / not_reproducible / unknown")
    score_breakdown: dict | None = Field(default=None, description="8 维评分明细")


class EvidenceSummary(BaseModel):
    """OneTopic §7.2 — 三类证据最小要求。"""

    papers: list[PaperHit] = Field(default_factory=list)
    datasets: list[DatasetHit] = Field(default_factory=list)
    baselines: list[BaselineHit] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list, description="评价指标, 例: mAP / Recall / FPS")
    paper_count: int = 0
    arxiv_paper_count: int = 0
    dataset_count: int = 0
    baseline_count: int = 0
    has_public_dataset: bool = False
    has_repro_baseline: bool = False
    has_metrics: bool = False


# ---------- EvidenceRef (Session 7 §5.1) ---------- #


class EvidenceRef(BaseModel):
    """统一的证据引用结构 (SOP §5.1)."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    evidence_type: Literal["paper", "dataset", "repo", "baseline", "note"]
    title: str
    role: Literal["supports", "warns", "blocks", "background", "alternative"]
    reason: str
    score: float | None = None
    review_status: str
    url: str | None = None
    url_verified: bool | None = None
    # Session 10 §7.2: 验证联动字段
    verification_status: str | None = None
    verification_confidence: float | None = None
    verification_warnings: list[str] = Field(default_factory=list)
    # Session 13 §7.2: Skill 来源
    skill_sources: list[str] = Field(default_factory=list)


# ---------- 可行性判断 (§7) ---------- #


class FeasibilitySummary(BaseModel):
    """OneTopic §9.4 — 可行性 5 档 (GO/NARROW/PIVOT/PARK/STOP)."""

    verdict: Literal["可做", "收缩后可做", "可转向", "暂缓", "不建议"]
    reason: str
    paper_status: str
    dataset_status: str
    baseline_status: str
    engineering_status: str
    missing_evidence: list[str] = Field(default_factory=list)
    recommended_next_action: str
    # Session 7: 证据引用
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    blocking_refs: list[EvidenceRef] = Field(default_factory=list)
    missing_ref_reasons: list[str] = Field(default_factory=list)
    confidence: float = 0.0


# ---------- 开题建议 (§8) ---------- #


class WorkPackageSuggestion(BaseModel):
    wp_id: str
    title: str
    research_question: str
    method_approach: str
    data_source: str
    experiment_plan: str
    chapter: str
    # Session 7: 证据引用
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    dataset_refs: list[EvidenceRef] = Field(default_factory=list)
    baseline_refs: list[EvidenceRef] = Field(default_factory=list)
    metric_refs: list[EvidenceRef] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    status: Literal["ready", "needs_evidence"] = "ready"


class PivotRoute(BaseModel):
    """OneTopic §10 — 退化路线 (保守/平衡/激进)."""

    level: Literal["conservative", "balanced", "aggressive"]
    new_topic: str
    preserved_keywords: list[str] = Field(default_factory=list)
    removed_keywords: list[str] = Field(default_factory=list)
    tradeoff: str
    work_packages: list[WorkPackageSuggestion] = Field(default_factory=list)
    # Session 7: 证据引用
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    risk_reduction_refs: list[EvidenceRef] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class ProposalRecommendation(BaseModel):
    """OneTopic §8 + §10 — 推荐题目 + 工作包 + 退化路线."""

    recommended_topic: str
    recommendation_reason: list[str] = Field(default_factory=list)
    work_packages: list[WorkPackageSuggestion] = Field(default_factory=list)
    proposal_outline: list[str] = Field(default_factory=list)
    pivot_routes: list[PivotRoute] = Field(default_factory=list, description="§10 三条退化路线")
    # Session 7: 证据引用
    topic_evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    reason_evidence_refs: dict[str, list[EvidenceRef]] = Field(default_factory=dict)


# ---------- 低门槛审核 (§9) ---------- #


class ReviewCheck(BaseModel):
    dimension: str
    result: Literal["通过", "需补充", "有条件通过", "不通过"]
    comment: str
    # Session 7: 证据引用
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    confidence: float = 0.0


class LightReview(BaseModel):
    """OneTopic §9.3 — 五维轻审核。"""

    verdict: Literal["通过", "有条件通过", "需修改", "不建议"]
    summary: str
    checks: list[ReviewCheck] = Field(default_factory=list)
    revision_checklist: list[str] = Field(default_factory=list)


# ---------- 完整响应 ---------- #


class OneTopicResponse(BaseModel):
    """OneTopic §12.1 — 完整返回 (6 段)。"""

    project_id: str = Field(default="", description="本次分析对应的 project_id, 用于后续手动添加证据")
    request: OneTopicRequest
    topic_understanding: TopicUnderstanding
    keyword_breakdown: KeywordBreakdown
    search_plan: SearchPlan
    evidence_summary: EvidenceSummary
    feasibility: FeasibilitySummary
    proposal_recommendation: ProposalRecommendation
    light_review: LightReview
    elapsed_ms: int = 0


# ---------- FinalPackage (Session 8 §4.1) ---------- #


class FinalPackageBuildOptions(BaseModel):
    """POST /final-package/build 请求体."""

    model_config = ConfigDict(extra="forbid")

    include_low_confidence_refs: bool = Field(
        default=False,
        description="是否包含 needs_check 状态的证据 (默认排除)",
    )
    include_rejected_as_appendix: bool = Field(
        default=False,
        description="是否把 rejected 证据作为附录展示 (默认排除)",
    )
    style: Literal["proposal_mvp", "proposal_full"] = Field(
        default="proposal_mvp",
        description="proposal_mvp = 13 章节初稿; proposal_full = 后续扩展",
    )
    language: Literal["zh", "en"] = Field(default="zh", description="报告语言")


class ReportSection(BaseModel):
    """Markdown 报告的一个章节."""

    key: str
    title: str
    content: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)


class ReportCitation(BaseModel):
    """Markdown 末尾的证据引用清单条目."""

    ref_no: str = Field(description="E1 / D1 / R1 / N1")
    evidence_id: str
    evidence_type: str
    title: str
    url: str | None = None
    review_status: str
    role: str
    score: float | None = None
    used_in_sections: list[str] = Field(default_factory=list)
    # Session 10 §8: 验证联动字段
    verification_status: str | None = None
    verification_confidence: float | None = None
    verification_warnings: list[str] = Field(default_factory=list)
    # Session 13 §7.3: Skill 来源
    skill_sources: list[str] = Field(default_factory=list)


class FinalPackageSummary(BaseModel):
    """GET /final-package  响应: 摘要 (不含 markdown 全文)."""

    project_id: str
    final_topic: str
    ready_for_proposal: bool
    coverage_score: float
    low_coverage_warning: bool
    backend_verification: Literal["PASS", "WARN", "FAIL"] = "PASS"
    ui_verification: Literal["PASS", "WARN", "FAIL", "NOT_RUN"] = "NOT_RUN"
    playwright_verification: Literal["PASS", "WARN", "FAIL", "NOT_RUN"] = "NOT_RUN"
    proposal_markdown_chars: int
    section_count: int
    citation_count: int
    unsupported_claims_count: int
    revision_checklist_count: int
    generated_at: str
    cached: bool = Field(default=False, description="是否命中缓存 (未重新生成)")


class FinalPackage(FinalPackageSummary):
    """POST /final-package/build 完整响应 (含 markdown 全文 + sections + citations)."""

    proposal_markdown: str
    sections: list[ReportSection] = Field(default_factory=list)
    citation_list: list[ReportCitation] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    revision_checklist: list[str] = Field(default_factory=list)


# ---------- Workspace Board (Session 9 §4.2-§4.3) ---------- #


class EvidenceWorkspaceBoard(BaseModel):
    """单类型 (paper / dataset / repo) 的双栏 board."""

    model_config = ConfigDict(extra="forbid")

    board_type: Literal["paper", "dataset", "repo"]
    left_lane_title: str = "用户希望使用"
    right_lane_title: str = "系统检索候选"
    left_items: list[dict] = Field(default_factory=list, description="EvidenceItem.model_dump() 列表 (lane=user_preferred)")
    right_items: list[dict] = Field(default_factory=list, description="EvidenceItem.model_dump() 列表 (lane=system_found 或 background)")
    selected_items: list[dict] = Field(default_factory=list, description="EvidenceItem.model_dump() 列表 (lane=selected, review_status=core)")
    rejected_items: list[dict] = Field(default_factory=list, description="EvidenceItem.model_dump() 列表 (lane=rejected)")


class WorkspaceBoardResponse(BaseModel):
    """GET /workspace/board 响应: 三类 board 同时返回."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    papers: EvidenceWorkspaceBoard
    datasets: EvidenceWorkspaceBoard
    repos: EvidenceWorkspaceBoard


class WorkspaceItemPatch(BaseModel):
    """PATCH /workspace/item 请求体."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    workspace_lane: Literal["user_preferred", "system_found", "selected", "rejected"] | None = None
    review_status: Literal["pending", "accepted", "core", "background", "rejected", "needs_check"] | None = None
    reason: str | None = Field(default=None, description="用户操作理由, 写入 Trace")


class WorkspaceItemPatchResponse(BaseModel):
    """PATCH /workspace/item 响应."""

    ok: bool
    evidence_id: str
    workspace_lane: str
    review_status: str
    message: str = ""
    trace_event: dict | None = None
