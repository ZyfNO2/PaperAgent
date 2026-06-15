"""Phase 03: Search query plan generator.

MVP 范围（不调 LLM；纯规则从 TopicSpec 推）：

1. 关键词抽取：normalized_topic / task_type / method_family
2. 7 个检索层 L0-L6（§3），每层 ≥1 词
3. 5 类来源路由（§2.3）：英文论文/代码/数据集/中文学位论文/技术模板
4. 每个 WP 绑定 ≥2 组检索词（§4 + §8）
5. 成熟度预判（§4.1）：基于 inherited_resources 与 topic 类型启发式
6. baseline / 数据集 / 指标预判：留空给 Phase 04 补
7. 中文开题模板：固定 5 条（§4.4）

输出 SearchQueryPlan。``build_search_plan(topic_spec)`` 是公开入口。
"""

from __future__ import annotations

import re

from packages.domain import (
    BaselineProbe,
    MaturityProbe,
    QueryLayer,
    SearchQueryPlan,
    SourceTarget,
    ThesisTemplateProbe,
    TopicSpec,
    WorkPackageQuery,
)


_ZH_TERM_MAP: dict[str, list[str]] = {
    "图神经网络": ["graph neural network", "GNN", "GCN", "GAT"],
    "推荐": ["recommendation", "recommender system"],
    "学术论文": ["academic paper", "scholarly article", "research paper"],
    "大模型": ["large language model", "LLM"],
    "多模态": ["multimodal", "vision-language"],
    "知识图谱": ["knowledge graph", "KG"],
    "对比学习": ["contrastive learning"],
    "提示": ["prompt", "prompting", "in-context learning"],
    "检索增强": ["retrieval augmented generation", "RAG"],
    "智能体": ["agent", "LLM agent"],
    "开题": ["thesis proposal", "research proposal"],
    "选题": ["topic selection", "research topic recommendation"],
    "医学影像": ["medical imaging", "radiology"],
    "临床": ["clinical"],
    "校对": ["proofreading", "error detection"],
    "系统": ["system", "framework"],
}


_GENERIC_TASK_PIVOTS: list[tuple[str, list[str], str]] = [
    (
        "academic topic recommendation",
        ["research topic recommendation", "academic paper recommendation"],
        "题目级推荐是更成熟的子任务",
    ),
    (
        "literature-based recommendation",
        ["literature recommendation", "citation recommendation"],
        "文献推荐是研究领域成熟任务",
    ),
    (
        "research idea generation",
        ["research idea generation", "hypothesis generation"],
        "想法生成已被 LLM 普及",
    ),
    (
        "evidence-grounded academic writing",
        ["retrieval augmented academic writing", "evidence-grounded generation"],
        "证据增强写作与 RAG 高度相关",
    ),
]


_TOPIC_PILOT_KEYWORDS: list[str] = [
    "academic topic recommendation",
    "research topic recommendation",
    "research idea generation",
    "literature based recommendation system",
    "evidence grounded generation",
    "retrieval augmented generation academic writing",
    "LLM agent workflow evaluation",
    "human in the loop topic selection",
    "thesis proposal assistant",
    "research proposal generation",
]


_ZH_THESIS_QUERIES: list[str] = [
    "开题报告 选题 辅助 系统",
    "研究生 开题 选题 推荐",
    "学位论文 选题 方法 研究现状",
    "人工智能 开题报告 研究现状",
    "RAG 学位论文",
    "智能推荐系统 硕士论文",
    "选题 风险评估 学位论文",
]


def _extract_en_keywords(topic: TopicSpec) -> list[str]:
    """从 normalized_topic / task_type / method_family 抽英文术语。"""

    out: list[str] = []
    text = topic.normalized_topic
    # 扫所有中文术语
    for zh, en_list in _ZH_TERM_MAP.items():
        if zh in text:
            out.extend(en_list)
    # 任务族直译
    for t in topic.task_type:
        for zh, en_list in _ZH_TERM_MAP.items():
            if zh in t:
                out.extend(en_list)
    for m in topic.method_family:
        for zh, en_list in _ZH_TERM_MAP.items():
            if zh in m:
                out.extend(en_list)
    # 去重保留顺序
    seen: set[str] = set()
    dedup: list[str] = []
    for k in out:
        kl = k.lower()
        if kl not in seen:
            seen.add(kl)
            dedup.append(k)
    return dedup or ["research"]


def _build_l0(topic: TopicSpec) -> QueryLayer:
    return QueryLayer(
        layer="L0",
        title="原始题目精确检索",
        purpose="确认是否已有高度相似题目或成熟论文",
        queries=[
            topic.raw_topic,
            topic.normalized_topic,
            f'"{topic.normalized_topic}"',
        ],
        target_sources=["OpenAlex", "Semantic Scholar", "CNKI"],
    )


def _build_l1(en_kw: list[str], zh: list[str]) -> QueryLayer:
    return QueryLayer(
        layer="L1",
        title="术语对齐",
        purpose="解决中文题目与英文检索词不一致",
        queries=[f"{a} | {b}" for a, b in zip(zh, en_kw)] if zh else en_kw,
        target_sources=["OpenAlex", "Wikipedia", "DBLP"],
    )


def _build_l2(en_kw: list[str]) -> QueryLayer:
    return QueryLayer(
        layer="L2",
        title="通用任务退化",
        purpose="精确场景资料少时退到更成熟任务",
        queries=[pivot for pivot, _, _ in _GENERIC_TASK_PIVOTS] + en_kw,
        target_sources=["OpenAlex", "arXiv cs.IR", "arXiv cs.CL"],
    )


def _build_l3(en_kw: list[str]) -> QueryLayer:
    return QueryLayer(
        layer="L3",
        title="方法族检索",
        purpose="为第二章相关基础与第三/四章技术路线准备材料",
        queries=[f"{kw} {extra}" for kw in en_kw for extra in
                 ("survey", "review", "tutorial", "state-of-the-art")],
        target_sources=["arXiv", "ACM", "OpenAlex"],
    )


def _build_l4(en_kw: list[str]) -> QueryLayer:
    return QueryLayer(
        layer="L4",
        title="数据集 / Baseline / Benchmark",
        purpose="为 Phase 04 找实验入口",
        queries=[f"{kw} {extra}" for kw in en_kw for extra in
                 ("dataset", "benchmark", "baseline", "github", "papers with code")],
        target_sources=["Papers with Code", "Hugging Face", "GitHub"],
    )


def _build_l5() -> QueryLayer:
    return QueryLayer(
        layer="L5",
        title="学位论文与实验模板",
        purpose="为开题报告与毕业论文目录提供结构证据",
        queries=_ZH_THESIS_QUERIES,
        target_sources=["CNKI", "Wanfang", "学校仓储", "arXiv"],
    )


def _build_l6(en_kw: list[str]) -> QueryLayer:
    return QueryLayer(
        layer="L6",
        title="Pivot 备选方向",
        purpose="原题过大或证据不足时准备可收缩方向",
        queries=[pivot for pivot, _, _ in _GENERIC_TASK_PIVOTS] + _TOPIC_PILOT_KEYWORDS,
        target_sources=["arXiv", "OpenAlex", "Hugging Face Trending"],
    )


def _build_source_targets() -> list[SourceTarget]:
    return [
        SourceTarget(
            evidence_type="英文论文",
            primary_sources=["OpenAlex", "Semantic Scholar"],
            fallback_sources=["Crossref", "arXiv", "DBLP"],
        ),
        SourceTarget(
            evidence_type="代码/baseline",
            primary_sources=["GitHub", "Papers with Code"],
            fallback_sources=["Hugging Face"],
        ),
        SourceTarget(
            evidence_type="数据集",
            primary_sources=["Hugging Face Datasets", "Kaggle"],
            fallback_sources=["Papers with Code", "项目主页"],
        ),
        SourceTarget(
            evidence_type="中文学位论文",
            primary_sources=["学校仓储", "CNKI 摘要"],
            fallback_sources=["Wanfang", "公开论文库"],
        ),
        SourceTarget(
            evidence_type="技术模板",
            primary_sources=["同方向硕博论文", "综述论文"],
            fallback_sources=["经典 benchmark 论文"],
        ),
    ]


def _build_maturity_probe(topic: TopicSpec) -> MaturityProbe:
    """启发式：继承资源丰富 → 高；多任务族 → 中。"""

    carried = topic.carried_constraints or []
    if carried and len(carried) >= 2:
        density = "高"
    elif topic.evaluation_metrics and len(topic.evaluation_metrics) >= 3:
        density = "中"
    else:
        density = "低"

    has_benchmark = any(
        kw in topic.normalized_topic
        for kw in ("推荐", "分类", "检测", "生成", "分割", "校对")
    )
    has_dataset = has_benchmark
    has_code = bool(topic.method_family)

    return MaturityProbe(
        has_survey=has_benchmark,
        has_benchmark=has_benchmark,
        has_public_dataset=has_dataset,
        has_open_code=has_code,
        has_thesis_template=bool(topic.thesis_mapping.chapter_3_wp1),
        expected_paper_density=density,  # type: ignore[arg-type]
        notes=[f"goal_level={topic.goal_level}", f"risk_terms={len(topic.risk_terms)}"],
    )


def _build_baseline_probe(topic: TopicSpec) -> BaselineProbe:
    return BaselineProbe(
        candidate_baselines=[],
        expected_datasets=[],
        expected_metrics=topic.evaluation_metrics,
    )


def _build_wp_queries(topic: TopicSpec, en_kw: list[str]) -> list[WorkPackageQuery]:
    out: list[WorkPackageQuery] = []
    for wp in topic.work_package_drafts:
        queries: list[str] = []
        # 至少 2 组
        for kw in en_kw[:2] or ["research"]:
            queries.append(f"{kw} {wp.method_approach.split()[0] if wp.method_approach else 'method'}")
        for req in wp.evidence_required[:2]:
            queries.append(req)
        out.append(
            WorkPackageQuery(
                wp_id=wp.wp_id,
                required_evidence=wp.evidence_required,
                query_groups=queries,
                priority_sources=["OpenAlex", "GitHub", "CNKI"],
            )
        )
    return out


def build_search_plan(topic: TopicSpec) -> SearchQueryPlan:
    """对外入口。从 TopicSpec 推出 SearchQueryPlan。"""

    en_kw = _extract_en_keywords(topic)
    zh_kw = [k for k in _ZH_TERM_MAP.keys() if k in topic.normalized_topic]

    layers = [
        _build_l0(topic),
        _build_l1(en_kw, zh_kw),
        _build_l2(en_kw),
        _build_l3(en_kw),
        _build_l4(en_kw),
        _build_l5(),
        _build_l6(en_kw),
    ]

    rating: str = "A"
    risk_flags: list[str] = []
    if not en_kw or en_kw == ["research"]:
        rating = "C"
        risk_flags.append("无法抽取英文关键词")
    if len(topic.risk_terms) >= 4:
        rating = "B"
        risk_flags.append("原题含 ≥4 个高风险词，建议先收缩")
    if not topic.evaluation_metrics:
        rating = "C"
        risk_flags.append("无评价指标，无法做 baseline 对比")

    return SearchQueryPlan(
        project_id=topic.project_id,
        topic_spec_id="",
        goal_level=topic.goal_level,
        carried_constraints=topic.carried_constraints,
        query_layers=layers,
        source_targets=_build_source_targets(),
        work_package_queries=_build_wp_queries(topic, en_kw),
        maturity_probe=_build_maturity_probe(topic),
        baseline_probe=_build_baseline_probe(topic),
        thesis_template_probe=ThesisTemplateProbe(
            template_queries_zh=_ZH_THESIS_QUERIES,
            ablation_templates=[
                "消融实验 模板 硕士",
                "ablation study 论文 结构",
            ],
            comparison_templates=[
                "对比实验 表格 模板 硕士论文",
                "baseline comparison table structure",
            ],
        ),
        risk_flags=risk_flags,
        maturity_rating=rating,  # type: ignore[arg-type]
    )


def allow_proceed_to_phase04(plan: SearchQueryPlan) -> tuple[bool, str]:
    if plan.maturity_rating == "D":
        return False, "maturity_rating=D"
    if len(plan.query_layers) < 6:
        return False, f"query_layers 不足 6 个（当前 {len(plan.query_layers)}）"
    total_queries = sum(len(l.queries) for l in plan.query_layers)
    if total_queries < 10:
        return False, f"总检索词不足 10（当前 {total_queries}）"
    if not plan.work_package_queries:
        return False, "无工作包检索映射"
    return True, "ok"
