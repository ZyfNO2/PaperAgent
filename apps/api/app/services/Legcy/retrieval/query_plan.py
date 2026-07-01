"""查询计划生成: raw_topic + extra_keywords -> QueryPlan (SOP §7)."""

from __future__ import annotations

import re
from typing import Iterable

from ...schemas_retrieval import QueryPlan, QueryPlanLayer

try:  # ponytail: T7 可选, 缺则静默退回启发式
    from app.services.research_topic_parser import parse_topic_rule_based
    from app.services.research_query_builder import rule_fill_query_pack
    HAS_RESEARCH_MODULES = True
except ImportError:
    HAS_RESEARCH_MODULES = False


# 简单中英停用词 + 常见方法词 (用于 L2/L3/L4 查询构建)
_METHOD_WORDS = {
    "yolo", "yolov5", "yolov8", "faster", "rcnn", "ssd", "retinanet",
    "transformer", "vit", "bert", "gpt", "llm", "diffusion", "gan",
    "unet", "deeplab", "mask", "pointnet", "pointrcnn",
    "graph", "neural", "network", "cnn", "rnn", "lstm",
    "svm", "random", "forest", "xgboost", "lightgbm",
}

# 常见任务词 (用于 L2 去方法词)
_TASK_WORDS = {
    "detection", "classification", "segmentation", "tracking", "recognition",
    "generation", "translation", "summarization", "extraction", "prediction",
    "estimation", "anomaly", "regression", "clustering", "matching",
    "检索", "分类", "检测", "分割", "识别", "生成", "翻译", "预测", "估计", "聚类", "匹配", "推荐",
}

# 常见对象词 (用于 L2 任务查询)
_OBJECT_HINTS: list[tuple[str, str]] = [
    ("钢材", "steel"),
    ("钢轨", "rail"),
    ("工业", "industrial"),
    ("表面", "surface"),
    ("缺陷", "defect"),
    ("医学", "medical"),
    ("医学影像", "medical"),
    ("ct", "ct"),
    ("mri", "mri"),
    ("x光", "xray"),
    ("卫星", "satellite"),
    ("遥感", "remote sensing"),
    ("自动驾驶", "autonomous driving"),
    ("行人", "pedestrian"),
    ("车辆", "vehicle"),
    ("文本", "text"),
    ("表格", "tabular"),
    ("时间序列", "time series"),
    ("金融", "financial"),
    ("电商", "ecommerce"),
    # S61: 三维成像 / 损伤 / 桥梁 / SHM
    ("三维成像", "3d imaging"),
    ("三维重建", "3d reconstruction"),
    ("三维点云", "3d point cloud"),
    ("深度成像", "depth imaging"),
    ("激光扫描", "laser scanning"),
    ("激光雷达", "lidar"),
    ("损伤检测", "damage detection"),
    ("裂缝检测", "crack detection"),
    ("混凝土裂缝", "concrete crack"),
    ("桥梁损伤", "bridge damage"),
    ("表面缺陷", "surface defect"),
    ("结构缺陷", "structural defect"),
    ("桥梁", "bridge"),
    ("混凝土结构", "concrete structure"),
    ("结构健康监测", "structural health monitoring"),
    ("基础设施", "infrastructure"),
]

# S61: dataset / repo query 必须包含的下游关键词
_DATASET_TOKENS = {"dataset", "benchmark", "public", "kaggle", "huggingface"}
_REPO_TOKENS = {"github", "pytorch", "implementation", "baseline", "code", "train"}


def _split_topic_to_tokens(raw: str) -> list[str]:
    """从中文 raw_topic 抽出英文 token hints, 走启发式."""

    text = (raw or "").strip()
    if not text:
        return []
    tokens: list[str] = []
    # 抽取显式英文字段
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9\-\.]+", text):
        w = m.group(0).lower()
        if w not in _METHOD_WORDS and w not in _TASK_WORDS and len(w) > 1:
            tokens.append(w)
    return tokens


def _has_zh(s: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in s or "")


def _en_translation_hints(raw: str) -> list[str]:
    """基于内置映射给出英文 hint 词."""

    out: list[str] = []
    raw_l = raw.lower()
    for zh, en in _OBJECT_HINTS:
        if zh in raw:
            out.append(en)
        elif en in raw_l:
            out.append(en)
    # 任务词直译
    for zh, en in [
        ("检测", "detection"),
        ("分类", "classification"),
        ("分割", "segmentation"),
        ("识别", "recognition"),
        ("预测", "prediction"),
        ("估计", "estimation"),
    ]:
        if zh in raw and en not in out:
            out.append(en)
    return out


def _method_in_topic(raw: str) -> list[str]:
    """从题目中识别提到的方法词."""

    raw_l = raw.lower()
    return [m for m in _METHOD_WORDS if re.search(rf"\b{re.escape(m)}\b", raw_l)]


def _task_in_topic(raw: str) -> list[str]:
    raw_l = raw.lower()
    return [t for t in _TASK_WORDS if t in raw_l]


def _de_method_task_only(raw: str) -> str:
    """L2: 去方法词后, 保留任务 + 对象词."""

    raw_l = raw.lower()
    # 把所有方法词去掉
    cleaned = raw_l
    for m in _METHOD_WORDS:
        cleaned = re.sub(rf"\b{re.escape(m)}\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _dedup_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        s = (it or "").strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def build_query_plan(
    project_id: str,
    raw_topic: str,
    extra_keywords: list[str] | None = None,
    *,
    max_paper_queries: int = 6,
    max_dataset_queries: int = 5,
    max_repo_queries: int = 5,
) -> QueryPlan:
    """按 SOP §7 生成 L0..L5 查询计划.

    中文 / 英文 / 混合题目均能生成有意义的查询, 但空 raw_topic 也能返回空计划.
    T7: 若 research 模块可用, 用 domain-aware research_pack 注入到 plan 顶部;
    启发式层始终保留作 fallback/补搜.
    """

    raw = (raw_topic or "").strip()
    extras = [k.strip() for k in (extra_keywords or []) if k and k.strip()]
    en_hints = _en_translation_hints(raw)
    en_tokens = _split_topic_to_tokens(raw)
    methods = _method_in_topic(raw)
    tasks = _task_in_topic(raw)
    l2_core = _de_method_task_only(raw)

    paper_layers: list[QueryPlanLayer] = []
    dataset_layers: list[QueryPlanLayer] = []
    repo_layers: list[QueryPlanLayer] = []

    # ---------- T7: research 模块可选注入 ---------- #
    # ponytail: 顶层放一条 "research" 层 (domain-aware), 启发式层仍作为后备补搜
    if HAS_RESEARCH_MODULES and raw:
        try:
            topic_parse = parse_topic_rule_based(raw)
            research_pack = rule_fill_query_pack(topic_parse)
            rq_paper = _dedup_keep_order(research_pack.get("paper_queries") or [])[:max_paper_queries]
            rq_dataset = _dedup_keep_order(research_pack.get("dataset_queries") or [])[:max_dataset_queries]
            rq_repo = _dedup_keep_order(research_pack.get("repo_queries") or [])[:max_repo_queries]
            if rq_paper:
                paper_layers.append(QueryPlanLayer(layer="research", queries=rq_paper))
            if rq_dataset:
                dataset_layers.append(QueryPlanLayer(layer="research", queries=rq_dataset))
            if rq_repo:
                repo_layers.append(QueryPlanLayer(layer="research", queries=rq_repo))
        except Exception:  # noqa: BLE001
            pass  # 静默退回纯启发式

    # ---------- 论文查询 (L0..L5) ---------- #
    paper_queries: list[str] = []

    # L0: 原题精确
    if raw:
        paper_queries.append(raw)

    # L1: 中英关键词组合
    if en_hints or en_tokens:
        l1 = " ".join(_dedup_keep_order(en_hints + en_tokens))
        if l1:
            paper_queries.append(l1)

    # L2: 去方法词的任务 + 对象查询
    if l2_core and l2_core != raw.lower():
        paper_queries.append(l2_core)
    elif en_hints and tasks:
        l2_alt = " ".join(en_hints + tasks[:2])
        if l2_alt:
            paper_queries.append(l2_alt)

    # L3: 方法 + 任务泛化
    if methods and en_hints:
        l3 = " ".join(methods[:2] + [t for t in tasks if t][:2] + en_hints[:2])
        if l3:
            paper_queries.append(l3)
    elif en_hints:
        paper_queries.append(" ".join(en_hints + ["survey", "benchmark"]))

    # L4: baseline / github
    if methods or en_hints:
        l4 = " ".join((methods[:1] or ["github"]) + en_hints[:2] + ["GitHub"])
        if l4:
            paper_queries.append(l4)

    # L5: survey / benchmark
    if en_hints or tasks:
        l5 = " ".join((en_hints[:2] or tasks[:2]) + ["survey", "benchmark"])
        if l5:
            paper_queries.append(l5)

    # 拼接 extras
    if extras:
        paper_queries.extend(extras[:2])

    paper_queries = _dedup_keep_order(paper_queries)[:max_paper_queries]
    paper_layers.append(QueryPlanLayer(layer="L0-L5", queries=paper_queries))

    # ---------- 数据集查询 (L2/L5 风格) ---------- #
    dataset_queries: list[str] = []
    if en_hints:
        dataset_queries.append(" ".join(en_hints + ["dataset"]))
    if l2_core:
        dataset_queries.append(l2_core + " dataset")
    if en_hints and tasks:
        dataset_queries.append(" ".join(en_hints[:1] + tasks[:1] + ["benchmark"]))
    if extras:
        dataset_queries.extend(extras[:1])
    # S61: 没有 en_hints 时退化到 "public dataset", 保证 dataset query 至少含一个下游 token
    if not dataset_queries:
        dataset_queries.append("public dataset")
    else:
        # 任何一条 dataset query 都至少要含 dataset/benchmark/public/kaggle/huggingface 之一
        for i, q in enumerate(dataset_queries):
            if not any(tok in q.lower() for tok in _DATASET_TOKENS):
                dataset_queries[i] = (q + " benchmark").strip()
    dataset_queries = _dedup_keep_order(dataset_queries)[:max_dataset_queries]
    dataset_layers.append(QueryPlanLayer(layer="dataset", queries=dataset_queries))

    # ---------- Repo 查询 (L4 风格) ---------- #
    repo_queries: list[str] = []
    if methods or en_hints:
        repo_queries.append(" ".join((methods[:1] or ["github"]) + en_hints[:2] + ["GitHub"]))
    if methods and en_hints:
        repo_queries.append(" ".join(methods[:1] + en_hints[:1] + ["implementation"]))
    if en_hints:
        repo_queries.append(" ".join(en_hints[:2] + ["baseline", "pytorch"]))
    if extras:
        repo_queries.extend(extras[:1])
    # S61: methods 与 en_hints 都为空时, 补一条泛 github/pytorch baseline
    if not (methods or en_hints):
        repo_queries.append("github pytorch baseline")
    else:
        # 任何一条 repo query 都至少要含 github/pytorch/implementation/baseline/code/train 之一
        for i, q in enumerate(repo_queries):
            if not any(tok in q.lower() for tok in _REPO_TOKENS):
                repo_queries[i] = (q + " github").strip()
    repo_queries = _dedup_keep_order(repo_queries)[:max_repo_queries]
    repo_layers.append(QueryPlanLayer(layer="repo", queries=repo_queries))

    return QueryPlan(
        project_id=project_id,
        raw_topic=raw,
        paper_queries=paper_layers,
        dataset_queries=dataset_layers,
        repo_queries=repo_layers,
    )
