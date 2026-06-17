"""Phase 02: Topic decomposition helpers (LLM-driven + pure-function post-processing).

MVP 设计：
- 一个 LLM 调用生成完整 TopicSpec JSON（标准化题目 + 组件 + 风险词 +
  五章映射 + 2 个 WP）。prompt 见 ``_DECOMPOSITION_PROMPT``。
- 用 ``chat_json`` 拿到 dict，再 ``TopicSpec.model_validate`` 校验。
- LLM 失败 / 校验失败：fallback 到 ``decompose_heuristic()``，用纯规则从
  raw_topic + ProjectIntake 推一个能跑通验收的最小 TopicSpec。
- 评级 A/B/C/D：默认 A；若 risk_terms ≥ 4 或 wp 缺数据源或评价指标
  缺失则降级。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from packages.domain import (
    DecompositionRating,
    ProjectIntake,
    RiskTerm,
    ThesisMapping,
    TopicSpec,
    WorkPackageDraft,
)
from packages.llm import chat_json, LLMUnavailable


_DECOMPOSITION_PROMPT = """你是中国研究生开题选题助手。给定学生的项目建档和原始题目，
请输出一份 JSON TopicSpec，字段严格按下面 schema：

{{
  "normalized_topic": "标准化的研究题目（只能收缩边界不能扩大承诺）",
  "research_object": "研究对象（如学生题目 / 学术论文 / 知识图谱）",
  "application_scenario": "应用场景",
  "task_type": ["核心任务1", "核心任务2"],
  "data_modality": ["数据模态1", ...],
  "method_family": ["方法族1", ...],
  "expected_outputs": ["输出1", ...],
  "evaluation_metrics": ["评价指标1", ...],
  "engineering_constraints": ["工程约束1", ...],
  "risk_terms": [
    {{"term": "原题中的高风险词", "risk": "风险点",
     "verifiable_definition": "可验证的定义或改写",
     "handling": "保留并定义|改写|删除|需补证据"}}
  ],
  "thesis_mapping": {{
    "chapter_1_intro": "第一章绪论可写内容",
    "chapter_2_basics": "第二章相关基础可写内容",
    "chapter_3_wp1": "第三章工作包一",
    "chapter_4_wp2": "第四章工作包二",
    "chapter_5_summary": "第五章总结与展望"
  }},
  "work_package_drafts": [
    {{"wp_id": "WP1", "title": "...", "research_question": "...",
     "method_approach": "...", "data_source": "...",
     "experiment_plan": "...", "chapter": "第三章",
     "evidence_required": ["..."]}},
    {{"wp_id": "WP2", ..., "chapter": "第四章"}}
  ]
}}

注意：
- normalized_topic 必须基于原题收缩，不能扩大承诺
- 必须输出 2 个工作包（WP1→第三章，WP2→第四章）
- 风险词改写：'智能'→'基于证据链的辅助分析'；'大模型'→'基于 LLM 的
  文本生成'；'通用'→限定到具体场景；'实时'→'异步 + SSE 进度展示'
- 评价指标必须可量化（Precision/Recall/F1/Latency/Cost 等）
- 严禁 markdown 包裹，严禁多余文字，只输出 JSON

原始题目：{raw_topic}
专业：{major}
学位：{degree_type}
目标档位：{goal_level}
导师方向：{advisor_direction}
继承资源：{inherited_resources}
学生资源：{student_resources}
"""


_RISK_TERM_PATTERNS: list[tuple[str, str, str, str]] = [
    # (regex, risk, verifiable_definition, handling)
    (r"智能", "易被理解为通用 AI", "基于证据链的辅助分析", "改写"),
    (r"通用", "边界不清，无法验证", "限定到具体场景", "改写"),
    (r"全自动", "难以保证 100% 正确率", "Agent 辅助 + 人工确认", "改写"),
    (r"实时", "实时无量化标准", "异步 + SSE 进度展示，延迟 < N 秒", "改写"),
    (r"高精度", "无对照基线", "在 [数据集] 上 Precision ≥ X%", "改写"),
    (r"大模型", "易过度承诺", "基于 LiteLLM 网关下的 LLM 调用", "改写"),
    (r"多模态", "范围模糊", "限定模态种类（如文本+图像）", "保留并定义"),
    (r"通用智能", "无可行实验", "聚焦到具体任务与指标", "删除"),
]


def _normalize_topic(raw: str) -> str:
    """启发式：把 '基于 X 的 Y' 句式稍微收紧。"""

    raw = raw.strip()
    if not raw:
        return raw
    # 简单添加"方法研究"后缀
    if not any(kw in raw for kw in ("方法", "研究", "系统", "实现", "评估")):
        return f"{raw}方法研究"
    return raw


def _detect_risk_terms(raw: str) -> list[RiskTerm]:
    out: list[RiskTerm] = []
    for pattern, risk, vd, handling in _RISK_TERM_PATTERNS:
        if re.search(pattern, raw):
            out.append(
                RiskTerm(
                    term=pattern,
                    risk=risk,
                    verifiable_definition=vd,
                    handling=handling,  # type: ignore[arg-type]
                )
            )
    return out


def _default_thesis_mapping(topic: str) -> ThesisMapping:
    return ThesisMapping(
        chapter_1_intro=f"开题选题痛点与{topic}的研究价值",
        chapter_2_basics="LangGraph 状态机、混合检索、结构化输出、风险评估指标",
        chapter_3_wp1="题目解析、文献/数据集/Baseline 检索与证据账本构建",
        chapter_4_wp2="选题风险评分、Pivot 规划、工作包生成与开题委员会审查",
        chapter_5_summary="系统实现、实验结果、局限与后续扩展",
    )


def _default_work_packages(topic: str) -> list[WorkPackageDraft]:
    return [
        WorkPackageDraft(
            wp_id="WP1",
            title="证据链构建",
            research_question="如何在开题选题过程中构建可追溯的证据链？",
            method_approach="混合检索 (lexical + dense) + Reranker + Evidence Ledger",
            data_source="OpenAlex / Semantic Scholar / 院系往届论文",
            experiment_plan="Evidence Precision@K / Baseline Recall@K / Citation Hallucination Rate",
            chapter="第三章",
            evidence_required=[
                "OpenAlex API 元数据",
                "BGE-M3 embedding",
                "BGE Reranker 分数",
            ],
        ),
        WorkPackageDraft(
            wp_id="WP2",
            title="风险与工作包生成",
            research_question="如何用 Agent 自动评估题目能否毕业并给出工作包？",
            method_approach="LangGraph 状态机 + 多维评分 + Pivot 候选 + 工作包生成",
            data_source="Phase 02 输出的 TopicSpec + 院系历史开题",
            experiment_plan="风险分类准确率 / Pivot 接受率 / 工作包覆盖率",
            chapter="第四章",
            evidence_required=[
                "至少 20 个历史开题案例（脱敏）",
                "评审专家标注的风险等级",
            ],
        ),
    ]


def decompose_heuristic(intake: ProjectIntake) -> TopicSpec:
    """纯规则 fallback TopicSpec。LLM 不可用时跑这条路径。"""

    norm = _normalize_topic(intake.raw_topic)
    risks = _detect_risk_terms(intake.raw_topic)
    if intake.must_keep:
        carried = list(intake.must_keep)
    else:
        carried = []

    # 评级：如果风险词过多或资源严重不足 → C/D
    if not intake.inherited_resources and intake.student_resources.weekly_hours < 10:
        rating: DecompositionRating = "C"
    elif len(risks) >= 4:
        rating = "B"
    else:
        rating = "A"

    return TopicSpec(
        project_id="",
        source_intake_case_id=intake.case_id,
        goal_level=intake.goal_level,
        first_result_deadline=intake.first_result_deadline,
        raw_topic=intake.raw_topic,
        normalized_topic=norm,
        research_object="学术开题选题场景下的题目证据链与风险评估",
        application_scenario="中国研究生开题报告准备阶段",
        task_type=["题目解析", "证据检索", "风险评分", "工作包生成"],
        data_modality=["Markdown 文档", "论文元数据", "代码仓库元数据"],
        method_family=["Agent 状态机", "RAG", "混合检索", "结构化输出"],
        expected_outputs=["风险报告", "证据账本", "工作包", "开题报告草案"],
        evaluation_metrics=[
            "Evidence Precision@K",
            "Baseline Recall@K",
            "Citation Hallucination Rate",
            "Workflow Success Rate",
        ],
        engineering_constraints=[
            "成本 < $5 / 案例",
            "端到端延迟 < 60s",
            "证据可追溯到原始来源",
            "人工确认关键节点",
        ],
        risk_terms=risks,
        thesis_mapping=_default_thesis_mapping(norm),
        work_package_drafts=_default_work_packages(norm),
        carried_constraints=carried,
        decomposition_rating=rating,
    )


def decompose_with_llm(intake: ProjectIntake) -> TopicSpec:
    """调 LLM 生成 TopicSpec JSON；失败抛 LLMUnavailable。"""

    inherited_desc = "; ".join(
        f"{r.kind}: {r.description}" for r in intake.inherited_resources
    ) or "无"
    student_desc = (
        f"编程 {intake.student_resources.programming_level}, "
        f"算法 {intake.student_resources.dl_or_algorithm_foundation}, "
        f"算力 {intake.student_resources.compute_resource}, "
        f"每周 {intake.student_resources.weekly_hours}h"
    )

    prompt = _DECOMPOSITION_PROMPT.format(
        raw_topic=intake.raw_topic,
        major=intake.major or "未指定",
        degree_type=intake.degree_type,
        goal_level=intake.goal_level,
        advisor_direction=intake.advisor_direction or "未指定",
        inherited_resources=inherited_desc,
        student_resources=student_desc,
    )

    raw = chat_json(
        [
            {"role": "system", "content": "你严格按 schema 输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=3000,
    )
    return _build_topicspec(intake, raw)


def decompose(intake: ProjectIntake, *, prefer: str = "auto", trace_sink=None) -> TopicSpec:
    """对外入口. ``prefer='llm'`` 强制 LLM; ``'heuristic'`` 强制规则;
    ``'auto'`` 优先 LLM, 失败则 fallback. trace_sink: 可选 (name, detail, meta) sink.
    """

    def emit(name, detail, **meta):
        if trace_sink:
            trace_sink(name, detail, meta)

    if prefer == "heuristic":
        emit("step", "走纯启发式 (无 LLM)", mode="heuristic")
        emit("step", "正则扫 8 个高风险词 + 拼装 TopicSpec", topic_len=len(intake.raw_topic))
        spec = decompose_heuristic(intake)
        emit("step", "评分", rating=spec.decomposition_rating)
        return spec
    if prefer == "llm":
        return _decompose_with_llm_emitting(intake, trace_sink)
    # auto
    try:
        return _decompose_with_llm_emitting(intake, trace_sink)
    except (LLMUnavailable, ValueError) as exc:
        emit("warn", f"LLM 失败, 走启发式 fallback: {type(exc).__name__}")
        spec = decompose_heuristic(intake)
        spec.carried_constraints.append(f"[fallback] heuristic used: {type(exc).__name__}")
        emit("step", "评分", rating=spec.decomposition_rating)
        return spec


def _decompose_with_llm_emitting(intake: ProjectIntake, trace_sink) -> TopicSpec:
    """LLM 路径, 沿途 emit. 失败抛 LLMUnavailable."""
    import time as _t

    def emit(name, detail, **meta):
        if trace_sink:
            trace_sink(name, detail, meta)

    emit("step", "📝 拼装拆解 prompt", max_tokens=3000)
    t0 = _t.time()
    emit("llm", "🤖 调 M3 拆解题目结构", max_tokens=3000)
    spec = decompose_with_llm(intake)
    emit("llm", "✅ LLM 返回", duration_ms=int((_t.time() - t0) * 1000))
    emit("step", "校验 + 启发式补齐", rating=spec.decomposition_rating)
    return spec


# ----------------- 内部: 把 LLM 输出组装为 TopicSpec ----------------- #


def _build_topicspec(intake: ProjectIntake, raw: dict) -> TopicSpec:
    """把 LLM 返回的 dict 校验成 TopicSpec。缺字段用启发式补齐。"""

    risks_raw = raw.get("risk_terms") or []
    risks: list[RiskTerm] = []
    for r in risks_raw:
        try:
            risks.append(
                RiskTerm(
                    term=str(r.get("term", "")).strip() or "未知",
                    risk=str(r.get("risk", "")).strip() or "未说明",
                    verifiable_definition=str(r.get("verifiable_definition", "")).strip()
                    or "需补",
                    handling=r.get("handling", "改写") if r.get("handling") in
                    {"保留并定义", "改写", "删除", "需补证据"} else "改写",
                )
            )
        except Exception:
            continue

    tm_raw = raw.get("thesis_mapping") or {}
    tm = ThesisMapping(
        chapter_1_intro=tm_raw.get("chapter_1_intro") or f"开题选题痛点与{intake.raw_topic}",
        chapter_2_basics=tm_raw.get("chapter_2_basics") or "相关基础方法综述",
        chapter_3_wp1=tm_raw.get("chapter_3_wp1") or "工作包一",
        chapter_4_wp2=tm_raw.get("chapter_4_wp2") or "工作包二",
        chapter_5_summary=tm_raw.get("chapter_5_summary") or "总结与展望",
    )

    wp_raw = raw.get("work_package_drafts") or []
    wps: list[WorkPackageDraft] = []
    for i, w in enumerate(wp_raw[:2]):
        try:
            wps.append(
                WorkPackageDraft(
                    wp_id=w.get("wp_id") or f"WP{i+1}",
                    title=w.get("title") or f"工作包 {i+1}",
                    research_question=w.get("research_question") or "待定义",
                    method_approach=w.get("method_approach") or "待定义",
                    data_source=w.get("data_source") or "待定义",
                    experiment_plan=w.get("experiment_plan") or "待定义",
                    chapter="第三章" if i == 0 else "第四章",
                    evidence_required=list(w.get("evidence_required") or []),
                )
            )
        except Exception:
            continue
    if not wps:
        wps = _default_work_packages(intake.raw_topic)

    norm = raw.get("normalized_topic") or _normalize_topic(intake.raw_topic)
    rating: DecompositionRating = "A"
    if len(risks) >= 4:
        rating = "B"

    return TopicSpec(
        project_id="",
        source_intake_case_id=intake.case_id,
        goal_level=intake.goal_level,
        first_result_deadline=intake.first_result_deadline,
        raw_topic=intake.raw_topic,
        normalized_topic=norm,
        research_object=raw.get("research_object"),
        application_scenario=raw.get("application_scenario"),
        task_type=list(raw.get("task_type") or []),
        data_modality=list(raw.get("data_modality") or []),
        method_family=list(raw.get("method_family") or []),
        expected_outputs=list(raw.get("expected_outputs") or []),
        evaluation_metrics=list(raw.get("evaluation_metrics") or []),
        engineering_constraints=list(raw.get("engineering_constraints") or []),
        risk_terms=risks,
        thesis_mapping=tm,
        work_package_drafts=wps,
        carried_constraints=list(intake.must_keep),
        decomposition_rating=rating,
    )


# ----------------- 评级：判定是否允许进入 Phase 03 ----------------- #


def allow_proceed_to_phase03(spec: TopicSpec) -> tuple[bool, str]:
    if spec.decomposition_rating == "D":
        return False, "decomposition_rating=D"
    if not spec.work_package_drafts or len(spec.work_package_drafts) < 2:
        return False, "工作包不足 2 个"
    if not spec.thesis_mapping.chapter_3_wp1 or not spec.thesis_mapping.chapter_4_wp2:
        return False, "五章式映射缺失第三章或第四章"
    if not spec.evaluation_metrics:
        return False, "无评价指标"
    return True, "ok"
