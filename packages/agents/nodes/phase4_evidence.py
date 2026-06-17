"""Phase 04: Evidence ledger builder.

MVP 范围：
- 调 M3 LLM 一次性生成 ``EvidenceLedger`` JSON（论文候选、综述、数据集、
  baseline、指标、实验模板、学位论文模板）
- LLM 失败时 fallback 到纯启发式（基于 TopicSpec 字段推最小可用账本）
- 评级规则：papers < 5 → C；datasets < 2 → C；baselines < 2 → C；
  surveys 缺 → B；metrics 缺 → D
"""

from __future__ import annotations

from packages.domain import (
    BaselineCandidate,
    DatasetCandidate,
    EvidenceLedger,
    ExperimentTemplate,
    MetricSet,
    PaperEvidence,
    SearchQueryPlan,
    ThesisTemplate,
    TopicSpec,
)
from packages.llm import chat_json, LLMUnavailable
from packages.clients.arxiv import ArxivPaper, search_arxiv


_EVIDENCE_PROMPT = """你是中国研究生开题选题助手。给定 TopicSpec 与 SearchQueryPlan，
请生成结构化证据账本 JSON，schema 严格如下：

{{
  "papers": [
    {{"paper_id": "P001", "title": "...", "year": 2024, "source": "OpenAlex",
     "url": null, "abstract": "一句话摘要",
     "task": ["..."], "method": ["..."], "datasets": ["..."], "metrics": ["..."],
     "baseline_mentions": ["..."], "reusable_value": "可借鉴点",
     "evidence_score": 0.8, "wp_binding": ["WP1"]}}
  ],
  "surveys": [...同结构...],
  "datasets": [
    {{"dataset_id": "D001", "name": "...", "task": ["..."], "modality": ["文本"],
     "scale": "10k 论文", "license": "未知", "download": "URL 或 null",
     "fit_to_topic": "高|中|低|未知", "wp_binding": ["WP1"]}}
  ],
  "baselines": [
    {{"baseline_id": "B001", "name": "...", "paper_title": "...",
     "repository_url": "https://github.com/...",
     "has_readme": true, "has_env_file": true, "has_training_script": true,
     "has_eval_script": true, "has_pretrained_weight": false,
     "license": "MIT", "reproduce_difficulty": "中",
     "fit_to_student_resources": "适合", "wp_binding": ["WP1"]}}
  ],
  "metrics": [
    {{"name": "NDCG@10", "task": "推荐排序", "reproducible": true, "source": "..."}}
  ],
  "experiment_templates": [
    {{"template_id": "T001", "type": "对比实验|消融实验|参数实验|案例分析",
     "source_paper": "...", "note": "..."}}
  ],
  "thesis_templates": [
    {{"template_id": "TH001", "source": "...",
     "toc_outline": ["第一章 绪论", "第二章 相关基础"],
     "method_chapter_structure": ["3.1 问题定义", "3.2 方法框架"],
     "note": "..."}}
  ]
}}

要求：
- papers ≥ 5 篇；surveys ≥ 1 篇
- datasets ≥ 2 个候选；baselines ≥ 2 个候选
- metrics ≥ 1 套
- experiment_templates ≥ 1 个对比 + 1 个消融
- thesis_templates ≥ 1 个五章式目录
- 严格 JSON 输出，不要解释
- 论文与 baseline 标题用英文（如 "LightGCN: Simplifying and Powering Graph Convolution Network for Recommendation"）
- 数据集名用英文（如 "Amazon-Book"）
- baseline repository_url 可以是占位 "https://github.com/..."，明确标注可复现性未知

normalized_topic: {normalized_topic}
task_type: {task_type}
method_family: {method_family}
evaluation_metrics: {evaluation_metrics}
work_package_titles: {wp_titles}
raw_topic: {raw_topic}
"""


def _build_default_papers(topic: TopicSpec) -> list[PaperEvidence]:
    """启发式：5 篇占位论文（LLM 不可用时）。"""

    topic_kw = topic.normalized_topic[:24]
    return [
        PaperEvidence(
            paper_id=f"P{i+1:03d}",
            title=f"[placeholder paper {i+1}] {topic_kw}",
            year=2024 - i,
            source="LLM-generated-candidate",
            url=None,
            abstract=f"占位摘要 {i+1}",
            task=list(topic.task_type[:2]),
            method=list(topic.method_family[:2]),
            datasets=[],
            metrics=list(topic.evaluation_metrics[:2]),
            baseline_mentions=[],
            reusable_value=f"占位：可借鉴 {topic.method_family[0] if topic.method_family else '方法'}",
            evidence_score=0.4 + i * 0.05,
            wp_binding=[f"WP{((i % 2) + 1)}"],
        )
        for i in range(5)
    ]


def _arxiv_to_paper(a: ArxivPaper, idx: int, topic: TopicSpec) -> PaperEvidence:
    # LLM 翻译: 调一次 chat_json 拿中文一句话 + 关键词 + 领域
    from packages.clients.arxiv import summarize_paper
    summary = summarize_paper(a.title, a.summary)
    return PaperEvidence(
        paper_id=a.arxiv_id or f"AX{idx:03d}",
        title=a.title,
        year=a.year or None,
        source="arXiv",
        url=a.abs_url,
        abstract=a.summary or None,
        authors=list(a.authors or []),
        task=list(topic.task_type[:2]),
        method=list(topic.method_family[:2]),
        datasets=[],
        metrics=list(topic.evaluation_metrics[:2]),
        baseline_mentions=[],
        reusable_value=f"arXiv 真实论文 ({a.categories[0] if a.categories else 'cs'})",
        evidence_score=0.7,
        wp_binding=[f"WP{((idx % 2) + 1)}"],
        summary_zh=summary.summary_zh,
        keywords_zh=list(summary.keywords_zh or []),
        field=summary.field,
    )


def _merge_arxiv_papers(
    topic: TopicSpec, plan: SearchQueryPlan | None, max_total: int = 5,
    trace_sink=None,
) -> list[PaperEvidence]:
    """从 SearchQueryPlan 抽检索词, 调 arXiv, 转 PaperEvidence. 失败返回 [].

    arXiv API 挂掉或搜不到时, 调用方按 fallback 把这些 slot 填回占位论文.
    trace_sink: 接收 (name, detail, meta) 调用, 用于 SSE 流式 trace.
    """
    def emit(name, detail, **meta):
        if trace_sink:
            trace_sink(name, detail, meta)

    queries: list[str] = []
    # 1. 从 normalized_topic 抽英文 term (中英映射表 + 关键词)
    nt = (topic.normalized_topic or "").lower()
    # 常见中英 term 映射 (主题无关, 通用)
    en_map = {
        "yolo": "YOLOv8", "注意力": "attention mechanism", "轻量化": "lightweight",
        "工业": "industrial", "缺陷": "defect detection", "检测": "detection",
        "推荐": "recommendation", "分类": "classification", "分割": "segmentation",
        "生成": "generation", "图神经": "graph neural network", "transformer": "Transformer",
        "强化学习": "reinforcement learning", "目标检测": "object detection",
        "小样本": "few-shot", "大模型": "large language model", "rag": "RAG",
        "检索增强": "retrieval augmented", "代理": "agent", "多模态": "multimodal",
        "带钢": "steel strip", "表面": "surface",
    }
    for zh, en in en_map.items():
        if zh in nt:
            queries.append(f"{en} {nt.split()[-3:]}" if "YOLO" in en else en)
    # 2. SearchQueryPlan L0 + L1 (不取 L2/L3 抽象词)
    if plan is not None:
        for layer in plan.query_layers[:2]:
            queries.extend(layer.queries[:2])
    # 3. 兜底英文
    if not queries:
        queries = ["YOLOv8 steel defect detection", "industrial object detection"]
    # 4. 过滤中文 + 去重
    en_queries: list[str] = []
    seen_q: set[str] = set()
    for q in queries:
        if not q:
            continue
        if any(ord(c) > 127 for c in q):
            continue
        if q in seen_q:
            continue
        seen_q.add(q)
        en_queries.append(q)
    final = en_queries[:max_total + 3]  # 给点冗余

    emit("step", "📡 arXiv 真检索", queries=len(final), max_total=max_total)
    arxiv_hits = search_arxiv(final, max_per_query=2, max_total=max_total, timeout=8.0)
    emit("step", "✅ 解析 arXiv Atom XML", hits=len(arxiv_hits), queries=len(final))
    return [_arxiv_to_paper(a, i, topic) for i, a in enumerate(arxiv_hits)]


def _replace_with_arxiv(
    base: list[PaperEvidence], arxiv_rows: list[PaperEvidence]
) -> list[PaperEvidence]:
    """前 N 条用 arXiv 真实论文, 不足的 slot 保留 base 占位."""
    if not arxiv_rows:
        return base
    merged = list(arxiv_rows) + base[len(arxiv_rows):]
    return merged[: len(base)] if len(base) >= len(arxiv_rows) else merged


def _build_default_surveys(topic: TopicSpec) -> list[PaperEvidence]:
    return [
        PaperEvidence(
            paper_id="S001",
            title=f"A Survey on {topic.method_family[0] if topic.method_family else 'the Method'}",
            year=2023,
            source="LLM-generated-candidate",
            url=None,
            abstract="占位综述。",
            task=list(topic.task_type[:2]),
            method=list(topic.method_family[:2]),
            datasets=[],
            metrics=[],
            baseline_mentions=[],
            reusable_value="可作为开题报告国内外研究现状的骨架",
            evidence_score=0.6,
            wp_binding=["WP1", "WP2"],
        )
    ]


def _build_default_datasets(topic: TopicSpec) -> list[DatasetCandidate]:
    """真 arXiv 检索: 找 YOLO/工业缺陷 公开数据集. 失败 fallback 占位."""

    queries: list[str] = []
    for kw in (topic.method_family or [])[:2]:
        queries.append(kw + " dataset benchmark")
    for kw in (topic.task_type or [])[:2]:
        queries.append(kw + " public dataset")
    # 通用兜底: 工业缺陷题常考这几个数据集
    queries.extend([
        "NEU-DET steel surface defect",
        "GC10-DET steel strip dataset",
        "Severstal steel defect",
    ])

    arxiv_hits = search_arxiv(queries, max_per_query=1, max_total=6, timeout=8.0)

    out: list[DatasetCandidate] = []
    for i, p in enumerate(arxiv_hits[:4]):
        name = _extract_dataset_name(p.title) or f"YOLO-Dataset-{i+1}"
        out.append(DatasetCandidate(
            dataset_id=f"D{i+1:03d}",
            name=name,
            task=list(topic.task_type[:2]) or ["object detection"],
            modality=["RGB"],
            scale="公开 (arXiv 命中)",
            license="公开学术",
            download=p.abs_url,
            fit_to_topic="高" if i == 0 else "中",
            wp_binding=[f"WP{((i % 2) + 1)}"],
        ))

    if len(out) < 2:
        for i in range(len(out), 2):
            out.append(DatasetCandidate(
                dataset_id=f"D{i+1:03d}",
                name=f"Placeholder-Dataset-{i+1}",
                task=list(topic.task_type[:2]),
                modality=["文本"],
                scale="未知",
                license="未知",
                download=None,
                fit_to_topic="中",
                wp_binding=[f"WP{((i % 2) + 1)}"],
            ))
    return out[:4]


def _extract_dataset_name(title: str) -> str | None:
    """从 arxiv 标题抽数据集/方法名, 优先 known, 否则用 arxiv_id + 标题前 30 字符."""
    if not title:
        return None
    t = title.strip()
    known = ["NEU-DET", "GC10-DET", "Severstal", "DAGM", "KolektorSDD",
             "MT-FCC", "Rail-5K", "Surface Defect", "COCO", "VisA",
             "MVTec AD", "BTAD", "VisDrone", "DeepInspect", "DAMO-YOLO",
             "YOLOv8", "YOLOv7", "YOLOv5", "Faster R-CNN"]
    for n in known:
        if n.lower() in t.lower():
            return n
    # 兜底: 用标题前 30 字 (截断 ... 标识)
    cleaned = title.replace("\n", " ").strip()
    return cleaned[:30] + ("..." if len(cleaned) > 30 else "")



def _build_default_baselines(topic: TopicSpec) -> list[BaselineCandidate]:
    """真 arXiv 检索: 找 YOLO/工业检测 baseline. 失败 fallback."""

    queries: list[str] = []
    for kw in (topic.method_family or [])[:2]:
        queries.append(kw + " object detection")
    queries.extend([
        "YOLOv8 steel defect detection",
        "YOLOv5 industrial defect",
        "Faster R-CNN steel surface",
    ])

    arxiv_hits = search_arxiv(queries, max_per_query=1, max_total=6, timeout=8.0)
    out: list[BaselineCandidate] = []
    for i, p in enumerate(arxiv_hits[:3]):
        bname = _extract_baseline_name(p.title) or f"[arXiv:{p.arxiv_id}]"
        out.append(BaselineCandidate(
            baseline_id=f"B{i+1:03d}",
            name=bname,
            paper_title=p.title[:120],
            repository_url=p.abs_url,
            has_readme=True,
            has_env_file=False,
            has_training_script=False,
            has_eval_script=False,
            has_pretrained_weight=True,
            license="公开学术",
            reproduce_difficulty="中",
            fit_to_student_resources="适合",
            wp_binding=[f"WP{((i % 2) + 1)}"],
        ))

    if len(out) < 2:
        for i in range(len(out), 2):
            out.append(BaselineCandidate(
                baseline_id=f"B{i+1:03d}",
                name=f"Placeholder-Baseline-{i+1}",
                paper_title=f"[placeholder paper {i+1}]",
                repository_url=f"https://github.com/placeholder/{i+1}",
                has_readme=True,
                has_env_file=True,
                has_training_script=True,
                has_eval_script=True,
                has_pretrained_weight=False,
                license="MIT",
                reproduce_difficulty="中",
                fit_to_student_resources="适合",
                wp_binding=[f"WP{((i % 2) + 1)}"],
            ))
    return out[:3]


def _extract_baseline_name(title: str) -> str | None:
    """从 arxiv 标题抽模型名 (YOLOv8, Faster R-CNN 等)."""
    if not title:
        return None
    t = title.strip()
    known = ["YOLOv8", "YOLOv5", "YOLOv7", "YOLOv9", "YOLOv10",
             "Faster R-CNN", "DETR", "RT-DETR", "CenterNet", "EfficientDet",
             "PP-YOLOE", "DAMO-YOLO"]
    for n in known:
        if n.lower() in t.lower():
            return n
    return None



def _build_default_metrics(topic: TopicSpec) -> list[MetricSet]:
    return [
        MetricSet(name=m, task=topic.task_type[0] if topic.task_type else "task", reproducible=True)
        for m in topic.evaluation_metrics
    ]


def _build_default_templates() -> tuple[list[ExperimentTemplate], list[ThesisTemplate]]:
    exp = [
        ExperimentTemplate(
            template_id="T001",
            type="对比实验",
            source_paper="[placeholder]",
            note="主表 + 横向 baseline 对比",
        ),
        ExperimentTemplate(
            template_id="T002",
            type="消融实验",
            source_paper="[placeholder]",
            note="逐模块 remove/keep 验证",
        ),
    ]
    thesis = [
        ThesisTemplate(
            template_id="TH001",
            source="[placeholder 五章式目录]",
            toc_outline=[
                "第一章 绪论", "第二章 相关基础",
                "第三章 方法一", "第四章 方法二", "第五章 总结与展望",
            ],
            method_chapter_structure=[
                "3.1 问题定义", "3.2 方法框架", "3.3 核心模块", "3.4 实验结果",
            ],
        )
    ]
    return exp, thesis


def build_evidence_ledger_heuristic(
    spec: TopicSpec, plan: SearchQueryPlan
) -> EvidenceLedger:
    base_papers = _build_default_papers(spec)
    arxiv_rows = _merge_arxiv_papers(spec, plan, max_total=len(base_papers))
    papers = _replace_with_arxiv(base_papers, arxiv_rows)
    surveys = _build_default_surveys(spec)
    datasets = _build_default_datasets(spec)
    baselines = _build_default_baselines(spec)
    metrics = _build_default_metrics(spec)
    exp, thesis = _build_default_templates()

    rating, flags = _rate(
        papers=papers, surveys=surveys, datasets=datasets,
        baselines=baselines, metrics=metrics, exp=exp, thesis=thesis,
    )

    return EvidenceLedger(
        project_id=spec.project_id,
        query_plan_id="",
        goal_level=spec.goal_level,
        papers=papers,
        surveys=surveys,
        datasets=datasets,
        baselines=baselines,
        metrics=metrics,
        experiment_templates=exp,
        thesis_templates=thesis,
        risk_flags=flags,
        evidence_rating=rating,  # type: ignore[arg-type]
    )


def build_evidence_ledger_with_llm(
    spec: TopicSpec, plan: SearchQueryPlan
) -> EvidenceLedger:
    prompt = _EVIDENCE_PROMPT.format(
        normalized_topic=spec.normalized_topic,
        task_type=", ".join(spec.task_type),
        method_family=", ".join(spec.method_family),
        evaluation_metrics=", ".join(spec.evaluation_metrics),
        wp_titles="; ".join(wp.title for wp in spec.work_package_drafts),
        raw_topic=spec.raw_topic,
    )

    raw = chat_json(
        [
            {"role": "system", "content": "严格按 schema 输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=4000,
    )

    papers = _safe_papers(raw.get("papers"), spec)
    # 真 arXiv 论文优先, 然后 LLM 候选, 不足时回退占位
    arxiv_rows = _merge_arxiv_papers(spec, plan, max_total=5)
    base_default = _build_default_papers(spec)
    merged_papers: list[PaperEvidence] = []
    seen_ids: set[str] = set()
    for p in arxiv_rows + papers + base_default:
        if p.paper_id in seen_ids:
            continue
        seen_ids.add(p.paper_id)
        merged_papers.append(p)
        if len(merged_papers) >= max(5, len(papers)):
            break
    papers = merged_papers
    surveys = _safe_papers(raw.get("surveys"), spec, prefix="S")
    datasets = _safe_datasets(raw.get("datasets"), spec)
    baselines = _safe_baselines(raw.get("baselines"), spec)
    metrics = _safe_metrics(raw.get("metrics"), spec)
    exp = _safe_templates(raw.get("experiment_templates"))
    thesis = _safe_thesis(raw.get("thesis_templates"))

    rating, flags = _rate(
        papers=papers, surveys=surveys, datasets=datasets,
        baselines=baselines, metrics=metrics, exp=exp, thesis=thesis,
    )

    return EvidenceLedger(
        project_id=spec.project_id,
        query_plan_id="",
        goal_level=spec.goal_level,
        papers=papers,
        surveys=surveys,
        datasets=datasets,
        baselines=baselines,
        metrics=metrics,
        experiment_templates=exp,
        thesis_templates=thesis,
        risk_flags=flags,
        evidence_rating=rating,  # type: ignore[arg-type]
    )


def build_evidence_ledger(
    spec: TopicSpec, plan: SearchQueryPlan, *, prefer: str = "auto",
    trace_sink=None,
) -> EvidenceLedger:
    def emit(name, detail, **meta):
        if trace_sink:
            trace_sink(name, detail, meta)

    if prefer == "heuristic":
        emit("step", "走纯启发式路径 (无 LLM)", mode="heuristic")
        # 把 sink 传进去让 _merge_arxiv_papers emit
        base_papers = _build_default_papers(spec)
        arxiv_rows = _merge_arxiv_papers(spec, plan, max_total=len(base_papers), trace_sink=trace_sink)
        papers = _replace_with_arxiv(base_papers, arxiv_rows)
        surveys = _build_default_surveys(spec)
        datasets = _build_default_datasets(spec)
        baselines = _build_default_baselines(spec)
        metrics = _build_default_metrics(spec)
        exp, thesis = _build_default_templates()
        rating, flags = _rate(papers=papers, surveys=surveys, datasets=datasets,
                              baselines=baselines, metrics=metrics, exp=exp, thesis=thesis)
        emit("step", "评分", rating=rating, flags=len(flags))
        return EvidenceLedger(
            project_id=spec.project_id, query_plan_id="", goal_level=spec.goal_level,
            papers=papers, surveys=surveys, datasets=datasets, baselines=baselines,
            metrics=metrics, experiment_templates=exp, thesis_templates=thesis,
            risk_flags=flags, evidence_rating=rating,  # type: ignore[arg-type]
        )
    if prefer == "llm":
        return _build_with_llm_emitting(spec, plan, trace_sink)
    # auto
    try:
        return _build_with_llm_emitting(spec, plan, trace_sink)
    except (LLMUnavailable, ValueError) as exc:
        emit("warn", f"LLM 失败, 走启发式 fallback: {type(exc).__name__}")
        base_papers = _build_default_papers(spec)
        arxiv_rows = _merge_arxiv_papers(spec, plan, max_total=len(base_papers), trace_sink=trace_sink)
        papers = _replace_with_arxiv(base_papers, arxiv_rows)
        surveys = _build_default_surveys(spec)
        datasets = _build_default_datasets(spec)
        baselines = _build_default_baselines(spec)
        metrics = _build_default_metrics(spec)
        exp, thesis = _build_default_templates()
        rating, flags = _rate(papers=papers, surveys=surveys, datasets=datasets,
                              baselines=baselines, metrics=metrics, exp=exp, thesis=thesis)
        flags.append(f"[fallback] heuristic used: {type(exc).__name__}")
        emit("step", "评分", rating=rating, flags=len(flags))
        return EvidenceLedger(
            project_id=spec.project_id, query_plan_id="", goal_level=spec.goal_level,
            papers=papers, surveys=surveys, datasets=datasets, baselines=baselines,
            metrics=metrics, experiment_templates=exp, thesis_templates=thesis,
            risk_flags=flags, evidence_rating=rating,  # type: ignore[arg-type]
        )


def _build_with_llm_emitting(
    spec: TopicSpec, plan: SearchQueryPlan, trace_sink
) -> EvidenceLedger:
    """走 LLM 路径, 沿途 emit trace. 失败抛 LLMUnavailable 让上层 fallback."""
    def emit(name, detail, **meta):
        if trace_sink:
            trace_sink(name, detail, meta)

    import time as _t
    emit("step", "📝 拼装证据 prompt", max_tokens=4000)
    prompt = _EVIDENCE_PROMPT.format(
        normalized_topic=spec.normalized_topic,
        task_type=", ".join(spec.task_type),
        method_family=", ".join(spec.method_family),
        evaluation_metrics=", ".join(spec.evaluation_metrics),
        wp_titles="; ".join(wp.title for wp in spec.work_package_drafts),
        raw_topic=spec.raw_topic,
    )
    t0 = _t.time()
    emit("llm", "🤖 调 M3 生成论文 / 数据 / baseline 候选", max_tokens=4000)
    raw = chat_json(
        [
            {"role": "system", "content": "严格按 schema 输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=4000,
    )
    emit("llm", "✅ LLM 返回", duration_ms=int((_t.time() - t0) * 1000))

    papers = _safe_papers(raw.get("papers"), spec)
    # 真 arXiv 论文优先, 然后 LLM 候选, 不足时回退占位 (emit arxiv trace)
    arxiv_rows = _merge_arxiv_papers(spec, plan, max_total=5, trace_sink=trace_sink)
    base_default = _build_default_papers(spec)
    merged_papers: list[PaperEvidence] = []
    seen_ids: set[str] = set()
    for p in arxiv_rows + papers + base_default:
        if p.paper_id in seen_ids:
            continue
        seen_ids.add(p.paper_id)
        merged_papers.append(p)
        if len(merged_papers) >= max(5, len(papers)):
            break
    papers = merged_papers
    surveys = _safe_papers(raw.get("surveys"), spec, prefix="S")
    datasets = _safe_datasets(raw.get("datasets"), spec)
    baselines = _safe_baselines(raw.get("baselines"), spec)
    metrics = _safe_metrics(raw.get("metrics"), spec)
    exp = _safe_templates(raw.get("experiment_templates"))
    thesis = _safe_thesis(raw.get("thesis_templates"))

    rating, flags = _rate(
        papers=papers, surveys=surveys, datasets=datasets,
        baselines=baselines, metrics=metrics, exp=exp, thesis=thesis,
    )
    emit("step", "评分", rating=rating, flags=len(flags))
    return EvidenceLedger(
        project_id=spec.project_id, query_plan_id="", goal_level=spec.goal_level,
        papers=papers, surveys=surveys, datasets=datasets, baselines=baselines,
        metrics=metrics, experiment_templates=exp, thesis_templates=thesis,
        risk_flags=flags, evidence_rating=rating,  # type: ignore[arg-type]
    )


# ----------------- helpers ----------------- #


def _safe_papers(items, spec: TopicSpec, prefix: str = "P") -> list[PaperEvidence]:
    out: list[PaperEvidence] = []
    # 延迟 import 避免循环
    try:
        from packages.clients.arxiv import summarize_paper
    except ImportError:
        summarize_paper = None
    for i, p in enumerate(items or []):
        try:
            title = str(p.get("title", "")).strip() or f"placeholder-{i+1}"
            abstract = p.get("abstract") or ""
            # 给每条 paper 加中文摘要 (LLM 翻译), 失败时 None (前端 fallback 英文)
            zh = None
            if summarize_paper and title and not title.startswith("placeholder"):
                try:
                    zh = summarize_paper(title, abstract)
                except Exception:
                    zh = None
            out.append(
                PaperEvidence(
                    paper_id=p.get("paper_id") or f"{prefix}{i+1:03d}",
                    title=title,
                    year=p.get("year"),
                    source=p.get("source", "LLM-generated-candidate")
                    if p.get("source") in {"OpenAlex", "Semantic Scholar", "arXiv", "Crossref",
                                            "DBLP", "GitHub", "Papers with Code",
                                            "Hugging Face", "CNKI", "Wanfang", "学校仓储",
                                            "user-uploaded",
                                            "模板复用", "LLM-generated-candidate", "无法追溯"}
                    else "LLM-generated-candidate",
                    url=p.get("url"),
                    abstract=abstract,
                    authors=list(p.get("authors") or []),
                    task=list(p.get("task") or []),
                    method=list(p.get("method") or []),
                    datasets=list(p.get("datasets") or []),
                    metrics=list(p.get("metrics") or []),
                    baseline_mentions=list(p.get("baseline_mentions") or []),
                    reusable_value=str(p.get("reusable_value", "")).strip() or "可借鉴点未说明",
                    evidence_score=float(p.get("evidence_score", 0.5)),
                    wp_binding=list(p.get("wp_binding") or []),
                    summary_zh=(zh.summary_zh if zh else None),
                    keywords_zh=list(zh.keywords_zh if zh else []),
                    field=(zh.field if zh else None),
                )
            )
        except Exception:
            continue
    if not out:
        out = _build_default_papers(spec) if prefix == "P" else _build_default_surveys(spec)
    return out


def _safe_datasets(items, spec: TopicSpec) -> list[DatasetCandidate]:
    out: list[DatasetCandidate] = []
    for i, d in enumerate(items or []):
        try:
            out.append(
                DatasetCandidate(
                    dataset_id=d.get("dataset_id") or f"D{i+1:03d}",
                    name=str(d.get("name", "")).strip() or f"dataset-{i+1}",
                    task=list(d.get("task") or []),
                    modality=list(d.get("modality") or []),
                    scale=d.get("scale"),
                    license=d.get("license"),
                    download=d.get("download"),
                    fit_to_topic=d.get("fit_to_topic", "中")
                    if d.get("fit_to_topic") in {"高", "中", "低", "未知"} else "中",
                    wp_binding=list(d.get("wp_binding") or []),
                )
            )
        except Exception:
            continue
    return out or _build_default_datasets(spec)


def _safe_baselines(items, spec: TopicSpec) -> list[BaselineCandidate]:
    out: list[BaselineCandidate] = []
    for i, b in enumerate(items or []):
        try:
            out.append(
                BaselineCandidate(
                    baseline_id=b.get("baseline_id") or f"B{i+1:03d}",
                    name=str(b.get("name", "")).strip() or f"baseline-{i+1}",
                    paper_title=b.get("paper_title"),
                    repository_url=b.get("repository_url"),
                    has_readme=bool(b.get("has_readme", False)),
                    has_env_file=bool(b.get("has_env_file", False)),
                    has_training_script=bool(b.get("has_training_script", False)),
                    has_eval_script=bool(b.get("has_eval_script", False)),
                    has_pretrained_weight=bool(b.get("has_pretrained_weight", False)),
                    license=b.get("license"),
                    reproduce_difficulty=b.get("reproduce_difficulty", "中")
                    if b.get("reproduce_difficulty") in {"低", "中", "高", "未知"} else "中",
                    fit_to_student_resources=b.get("fit_to_student_resources", "未知")
                    if b.get("fit_to_student_resources") in {"适合", "勉强", "不适合", "未知"}
                    else "未知",
                    wp_binding=list(b.get("wp_binding") or []),
                )
            )
        except Exception:
            continue
    return out or _build_default_baselines(spec)


def _safe_metrics(items, spec: TopicSpec) -> list[MetricSet]:
    out: list[MetricSet] = []
    for m in items or []:
        try:
            out.append(
                MetricSet(
                    name=str(m.get("name", "")).strip() or "metric",
                    task=str(m.get("task", "")).strip() or "task",
                    reproducible=bool(m.get("reproducible", True)),
                    source=m.get("source"),
                )
            )
        except Exception:
            continue
    return out or _build_default_metrics(spec)


def _safe_templates(items) -> list[ExperimentTemplate]:
    out: list[ExperimentTemplate] = []
    for i, t in enumerate(items or []):
        try:
            tp = t.get("type", "对比实验")
            if tp not in {"对比实验", "消融实验", "参数实验", "案例分析"}:
                tp = "对比实验"
            out.append(
                ExperimentTemplate(
                    template_id=t.get("template_id") or f"T{i+1:03d}",
                    type=tp,  # type: ignore[arg-type]
                    source_paper=t.get("source_paper"),
                    note=str(t.get("note", "")).strip() or "占位说明",
                )
            )
        except Exception:
            continue
    return out


def _safe_thesis(items) -> list[ThesisTemplate]:
    out: list[ThesisTemplate] = []
    for i, th in enumerate(items or []):
        try:
            out.append(
                ThesisTemplate(
                    template_id=th.get("template_id") or f"TH{i+1:03d}",
                    source=str(th.get("source", "")).strip() or "占位源",
                    toc_outline=list(th.get("toc_outline") or []),
                    method_chapter_structure=list(th.get("method_chapter_structure") or []),
                    note=th.get("note"),
                )
            )
        except Exception:
            continue
    return out


def _rate(
    *,
    papers: list[PaperEvidence],
    surveys: list[PaperEvidence],
    datasets: list[DatasetCandidate],
    baselines: list[BaselineCandidate],
    metrics: list[MetricSet],
    exp: list[ExperimentTemplate],
    thesis: list[ThesisTemplate],
) -> tuple[str, list[str]]:
    flags: list[str] = []
    rating = "A"
    if len(papers) < 5:
        rating = "C"
        flags.append(f"论文证据不足 5 篇（当前 {len(papers)}）")
    if not surveys:
        rating = "B" if rating == "A" else rating
        flags.append("缺综述")
    if len(datasets) < 2:
        rating = "C" if rating == "A" else rating
        flags.append(f"数据集候选不足 2 个（当前 {len(datasets)}）")
    if len(baselines) < 2:
        rating = "C" if rating == "A" else rating
        flags.append(f"baseline 候选不足 2 个（当前 {len(baselines)}）")
    if not metrics:
        rating = "D"
        flags.append("无评价指标")
    if not exp:
        rating = "B" if rating == "A" else rating
        flags.append("无实验模板")
    if not thesis:
        rating = "B" if rating == "A" else rating
        flags.append("无学位论文模板")
    return rating, flags
