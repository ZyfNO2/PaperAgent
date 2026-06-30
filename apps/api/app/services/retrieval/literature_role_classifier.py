"""Session 64 T3: 文献角色分类器.

把候选论文/仓库分类成 thesis 规划中需要的几种角色:
- baseline_framework: 主流检测/分割框架 (YOLOv8, MMDetection 等)
- baseline_method: 可复现的方法论文 (作为 baseline 用)
- parallel_application_paper: 同任务/同对象, 学习怎么加模块
- module_improvement_paper: 注意力/损失/融合/轻量化等可移植模块
- dataset_paper: 数据集/基准论文
- survey: 综述/调研, 仅作背景
- irrelevant: 标题/任务/对象不匹配, 过滤掉

Ponytail: 纯规则分类, 不依赖 LLM. 一条流水线:
1) 标题快速分类 (baseline_framework / survey / irrelevant)
2) 抽象摘要细判 (parallel_application / module_improvement / dataset)
3) 2-of-4 检查: object / task / data / method 至少 2 项匹配
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------- 常量 ---------- #


Role = Literal[
    "baseline_framework",
    "baseline_method",
    "parallel_application_paper",
    "module_improvement_paper",
    "dataset_paper",
    "survey",
    "irrelevant",
]

Reproducibility = Literal["high", "medium", "low", "unknown"]


BASELINE_FRAMEWORKS: set[str] = {
    "yolov5", "yolov8", "yolov7", "yolov6",
    "mmdetection", "mmdet", "openmmlab",
    "detectron2", "mask rcnn", "faster rcnn",
    "transformers", "huggingface",
    "pytorch", "tensorflow", "keras",
}


_SURVEY_KEYWORDS = (
    "survey", "review", "综述", "调研", "a comprehensive review",
    "systematic review", "literature review", "meta-analysis",
)


_DATASET_KEYWORDS = (
    "dataset", "benchmark", "corpus", "数据集", "基准",
    "image database", "evaluation suite",
)


_MODULE_KEYWORDS = (
    # 注意力
    "attention", "self-attention", "cross-attention", "transformer block",
    "cbam", "se block", "eca", "non-local",
    # 损失
    "loss function", "focal loss", "dice loss", "ciou", "diou",
    # 融合
    "feature fusion", "feature pyramid", "fpn", "panet", "bi-fpn",
    "skip connection", "dense connection",
    # 轻量化
    "lightweight", "model compression", "pruning", "quantization",
    "knowledge distillation", "mobile", "efficientnet",
    # 检测头
    "decoupled head", "anchor-free", "dynamic head",
    # 数据增强
    "data augmentation", "mosaic", "mixup", "cutmix",
)


_IRRELEVANT_KEYWORDS = (
    # 错对象
    "medical", "clinical", "patient", "x-ray", "ct scan", "mri",
    "pathology", "genomics", "protein",
    "autonomous driving", "vehicle", "traffic sign", "lane detection",
    "satellite", "remote sensing", "aerial imagery",
    "face recognition", "facial", "pedestrian",
    # NLP 混入检测
    "sentiment analysis", "text classification", "named entity",
    "machine translation", "question answering", "language model",
    "chatbot", "dialogue", "summarization",
)


# ---------- 数据结构 ---------- #


class LiteratureRoleResult(BaseModel):
    candidate_id: str
    role: Role
    base_framework: str | None = None
    modules_added: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    code_url: str | None = None
    reproducibility: Reproducibility = "unknown"
    borrowable_ideas: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    reason: str = ""


class PaperModuleEntry(BaseModel):
    base: str
    module_a: str
    module_b: str | None = None
    dataset: str
    metrics: list[str] = Field(default_factory=list)
    paper_title: str
    paper_url: str | None = None
    improvement_description: str
    risk_notes: list[str] = Field(default_factory=list)


# ---------- 辅助函数 ---------- #


def _lower(s: Any) -> str:
    return (s or "").lower() if isinstance(s, str) else ""


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(n in t for n in needles)


def _normalize_framework_name(raw: str) -> str | None:
    """从标题/摘要里识别并归一化框架名."""

    t = raw.lower()
    for name in BASELINE_FRAMEWORKS:
        if name in t:
            return name
    return None


def _is_survey(title: str, abstract: str) -> bool:
    return _has_any(title, _SURVEY_KEYWORDS) or _has_any(abstract, _SURVEY_KEYWORDS)


def _is_dataset_paper(title: str, abstract: str) -> bool:
    return _has_any(title, _DATASET_KEYWORDS) or _has_any(abstract, _DATASET_KEYWORDS)


_FRAMEWORK_AS_BASE_HINTS = (
    "improved", "based on", "enhanced", "with", "using",
    "for", "applied to", "modified", "结合", "改进", "基于",
)


def _mentions_framework(blob: str) -> str | None:
    return _normalize_framework_name(blob)


def _is_framework_intro(title: str, abstract: str, fw: str) -> bool:
    """判断一篇论文是 *介绍框架本身* 还是 *用框架作 base 改进*.

    框架介绍特征: 标题首词/冒号前是框架名, 摘要谈 "we introduce / propose".
    Base 改进特征: 标题含 "improved YOLOv5" / "based on YOLOv8".
    """

    title_l = title.lower()
    abstract_l = abstract.lower()
    intro_markers = ("we introduce", "we propose", "we present", "a new ", "new framework")
    if any(m in abstract_l for m in intro_markers):
        # 还要看标题是否以框架名开篇
        if title_l.startswith(fw) or title_l.startswith(f"{fw}:"):
            return True
    # 标题里是 "improved YOLOv5" / "based on YOLOv8"
    if any(h in title_l for h in _FRAMEWORK_AS_BASE_HINTS):
        return False
    # 默认: 标题首词是框架名 -> 框架介绍
    if title_l.startswith(fw):
        return True
    return False


def _count_relevance_signals(
    object_terms: list[str],
    task_terms: list[str],
    method_terms: list[str],
    blob: str,
) -> int:
    """object / task / data / method 至少 2 项匹配. 返回命中数 [0, 4]."""

    hits = 0
    if any(o.lower() in blob for o in object_terms if o):
        hits += 1
    if any(t.lower() in blob for t in task_terms if t):
        hits += 1
    if any(m.lower() in blob for m in method_terms if m):
        hits += 1
    if any(d.lower() in blob for d in ("dataset", "benchmark", "data", "训练集")):
        hits += 1
    return hits


def _extract_modules(abstract: str) -> list[str]:
    if not abstract:
        return []
    t = abstract.lower()
    found: list[str] = []
    for kw in _MODULE_KEYWORDS:
        if kw in t:
            found.append(kw)
    return found[:8]  # ponytail: cap noise


def _extract_datasets(abstract: str, explicit: list[str] | None = None) -> list[str]:
    if explicit:
        return [str(d) for d in explicit][:6]
    if not abstract:
        return []
    # 简单启发: 找 "on XXXX" / "XXXX dataset" 模式
    candidates = re.findall(r"\b([A-Z][A-Za-z0-9\-]{2,20})\s+(?:dataset|benchmark)\b", abstract)
    if not candidates:
        return []
    # 去重保序
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out[:6]


def _extract_metrics(abstract: str, explicit: list[str] | None = None) -> list[str]:
    if explicit:
        return [str(m) for m in explicit][:6]
    if not abstract:
        return []
    metrics_kw = ("map", "mAP", "AP50", "AP75", "accuracy", "precision", "recall",
                  "f1", "f1-score", "iou", "fps", "ms", "latency")
    t = abstract.lower()
    found: list[str] = []
    for m in metrics_kw:
        if m.lower() in t:
            found.append(m)
    return found[:6]


def _infer_reproducibility(candidate: dict) -> Reproducibility:
    """根据 code_url / repo_full_name 字段粗判 reproducibility."""

    blob = " ".join(str(candidate.get(k, "")) for k in ("code_url", "repo_full_name", "url"))
    blob_l = blob.lower()
    if not blob_l.strip():
        return "unknown"
    if "github.com" in blob_l or "gitlab.com" in blob_l:
        return "high"
    if "arxiv.org" in blob_l or "doi.org" in blob_l:
        return "medium"
    return "low"


# ---------- 分类核心 ---------- #


def _classify_by_title(
    candidate: dict,
    topic_atoms: dict,
) -> LiteratureRoleResult:
    """标题快速分流: framework / survey / irrelevant."""

    title = str(candidate.get("title", ""))
    abstract = str(candidate.get("abstract", ""))
    blob = f"{title} {abstract}"
    blob_l = blob.lower()

    cid = str(candidate.get("candidate_id", ""))
    code_url = candidate.get("code_url") or candidate.get("url")

    # 1) Survey 优先 (几乎不当作 baseline)
    if _is_survey(title, abstract):
        return LiteratureRoleResult(
            candidate_id=cid,
            role="survey",
            code_url=code_url if isinstance(code_url, str) else None,
            reason="标题/摘要命中 survey/review 关键词, 仅作背景",
            risk_notes=["综述不应作为 baseline_method 或 baseline_framework"],
        )

    # 2) Baseline framework (硬规则: YOLOv5/v8/v7 等)
    fw = _mentions_framework(blob)
    if fw is not None and _is_framework_intro(title, abstract, fw):
        return LiteratureRoleResult(
            candidate_id=cid,
            role="baseline_framework",
            base_framework=fw,
            code_url=code_url if isinstance(code_url, str) else None,
            reproducibility=_infer_reproducibility(candidate),
            reason=f"命中已知 baseline 框架: {fw} (框架介绍/原始论文)",
            borrowable_ideas=[f"以 {fw} 作为基准模型, 对比改进点"],
        )

    # 3) Irrelevant: 标题/摘要命中错领域关键词
    if _has_any(title, _IRRELEVANT_KEYWORDS) or _has_any(abstract, _IRRELEVANT_KEYWORDS):
        # 但如果同时命中 framework 名, 已在上一步被吃掉
        return LiteratureRoleResult(
            candidate_id=cid,
            role="irrelevant",
            reason="标题/摘要命中错领域关键词 (medical/face/NLP/遥感等)",
            risk_notes=["领域不匹配, 排除"],
        )

    return None  # type: ignore[return-value]


def _classify_relevance_and_role(
    candidate: dict,
    topic_atoms: dict,
) -> LiteratureRoleResult:
    """2-of-4 匹配 + dataset / module / parallel 细分."""

    title = str(candidate.get("title", ""))
    abstract = str(candidate.get("abstract", ""))
    blob = f"{title} {abstract}"

    object_terms = list(topic_atoms.get("object_terms", []) or [])
    task_terms = list(topic_atoms.get("task_terms", []) or [])
    method_terms = list(topic_atoms.get("method_terms", []) or [])

    matches = _count_relevance_signals(object_terms, task_terms, method_terms, blob)

    cid = str(candidate.get("candidate_id", ""))
    code_url = candidate.get("code_url") or candidate.get("url")

    # 不够 2/4 命中, 直接归 irrelevant
    if matches < 2:
        return LiteratureRoleResult(
            candidate_id=cid,
            role="irrelevant",
            reason=f"object/task/data/method 仅命中 {matches}/4, 不相关",
            risk_notes=["领域匹配不足, 排除"],
        )

    # dataset paper: 标题/摘要显式 dataset/benchmark
    if _is_dataset_paper(title, abstract):
        return LiteratureRoleResult(
            candidate_id=cid,
            role="dataset_paper",
            datasets=_extract_datasets(abstract, candidate.get("datasets")),
            code_url=code_url if isinstance(code_url, str) else None,
            reason="标题/摘要命中 dataset/benchmark 关键词",
            borrowable_ideas=["可作为评估基准或训练集来源"],
        )

    modules = _extract_modules(abstract)
    if modules:
        # 有明确模块改进, 归 module_improvement
        return LiteratureRoleResult(
            candidate_id=cid,
            role="module_improvement_paper",
            modules_added=modules,
            datasets=_extract_datasets(abstract, candidate.get("datasets")),
            metrics=_extract_metrics(abstract, candidate.get("metrics")),
            code_url=code_url if isinstance(code_url, str) else None,
            reproducibility=_infer_reproducibility(candidate),
            reason=f"摘要命中 {len(modules)} 个可移植模块关键词",
            borrowable_ideas=[f"可移植模块: {', '.join(modules[:3])}"],
        )

    # 任务匹配 + 提到某框架: parallel_application
    base_fw = _mentions_framework(blob)
    if base_fw:
        return LiteratureRoleResult(
            candidate_id=cid,
            role="parallel_application_paper",
            base_framework=base_fw,
            datasets=_extract_datasets(abstract, candidate.get("datasets")),
            metrics=_extract_metrics(abstract, candidate.get("metrics")),
            code_url=code_url if isinstance(code_url, str) else None,
            reproducibility=_infer_reproducibility(candidate),
            reason=f"同任务同对象, 基于 {base_fw} 加模块应用",
            borrowable_ideas=[f"参考 {base_fw} 上的模块接入方式"],
        )

    # 兜底: 同领域可复现方法论文 (baseline_method)
    return LiteratureRoleResult(
        candidate_id=cid,
        role="baseline_method",
        datasets=_extract_datasets(abstract, candidate.get("datasets")),
        metrics=_extract_metrics(abstract, candidate.get("metrics")),
        code_url=code_url if isinstance(code_url, str) else None,
        reproducibility=_infer_reproducibility(candidate),
        reason=f"object/task/method 命中 {matches}/4, 可作为方法 baseline",
        borrowable_ideas=["作为方法对比基线"],
    )


def classify_literature(
    candidates: list[dict],
    topic_atoms: dict,
) -> list[LiteratureRoleResult]:
    """批量分类候选文献.

    Args:
        candidates: 候选 dict 列表, 每条至少含 candidate_id, title, abstract.
        topic_atoms: TopicParseResult dict 含 object_terms / task_terms / method_terms.

    Returns:
        每条候选一个 ``LiteratureRoleResult``.
    """

    results: list[LiteratureRoleResult] = []
    for cand in candidates:
        title_result = _classify_by_title(cand, topic_atoms)
        if title_result is not None:
            results.append(title_result)
            continue
        results.append(_classify_relevance_and_role(cand, topic_atoms))
    return results


# ---------- 模块矩阵 ---------- #


def _pick_base(entry: LiteratureRoleResult, topic_atoms: dict) -> str:
    if entry.base_framework:
        return entry.base_framework
    method_terms = list(topic_atoms.get("method_terms", []) or [])
    return method_terms[0] if method_terms else "unknown"


def _pick_module_a(entry: LiteratureRoleResult) -> str:
    if entry.modules_added:
        return entry.modules_added[0]
    return entry.borrowable_ideas[0] if entry.borrowable_ideas else "improvement"


def _build_module_matrix(
    parallel_papers: list[LiteratureRoleResult],
) -> list[PaperModuleEntry]:
    """把 parallel_application_paper 列表渲染成 Base + Module A + Module B + Dataset + Metric 矩阵.

    Args:
        parallel_papers: 已分类为 parallel_application_paper 的文献.

    Returns:
        PaperModuleEntry 列表, 缺少 dataset 时填 'unknown'.
    """

    rows: list[PaperModuleEntry] = []
    for entry in parallel_papers:
        modules = entry.modules_added or entry.borrowable_ideas or ["improvement"]
        dataset = entry.datasets[0] if entry.datasets else "unknown"
        rows.append(
            PaperModuleEntry(
                base=entry.base_framework or "unknown",
                module_a=modules[0] if modules else "improvement",
                module_b=modules[1] if len(modules) > 1 else None,
                dataset=dataset,
                metrics=entry.metrics,
                paper_title=str(entry.candidate_id),
                paper_url=entry.code_url,
                improvement_description=entry.reason,
                risk_notes=entry.risk_notes,
            )
        )
    return rows


# ---------- self-check ---------- #


if __name__ == "__main__":
    # ponytail: self-check
    topic = {
        "object_terms": ["steel surface", "defect", "钢材表面"],
        "task_terms": ["detection", "detect", "检测"],
        "method_terms": ["yolov8", "yolov5"],
        "data_terms": ["NEU-DET", "GC10-DET"],
    }

    cases: list[tuple[dict, Role, str]] = [
        # 1) YOLOv8 = baseline_framework, NOT parallel
        (
            {
                "candidate_id": "c1",
                "title": "YOLOv8: Ultralytics State-of-the-Art Real-Time Object Detector",
                "abstract": "We introduce YOLOv8, a unified framework for object detection.",
                "code_url": "https://github.com/ultralytics/ultralytics",
            },
            "baseline_framework",
            "yolov8",
        ),
        # 2) YOLOv5 steel defect parallel
        (
            {
                "candidate_id": "c2",
                "title": "Steel surface defect detection based on improved YOLOv5",
                "abstract": "We propose an improved YOLOv5 with attention for steel surface defect detection on NEU-DET.",
            },
            "parallel_application_paper",
            "yolov5",
        ),
        # 3) Survey = survey
        (
            {
                "candidate_id": "c3",
                "title": "A Survey on Deep Learning for Object Detection",
                "abstract": "This survey reviews recent advances in object detection.",
            },
            "survey",
            None,
        ),
        # 4) Medical = irrelevant (即使有 detection)
        (
            {
                "candidate_id": "c4",
                "title": "X-ray lung nodule detection with YOLOv8",
                "abstract": "Medical imaging for clinical patient diagnosis.",
            },
            "irrelevant",
            None,
        ),
        # 5) NLP 混入 detection = irrelevant
        (
            {
                "candidate_id": "c5",
                "title": "Sentiment analysis with BERT",
                "abstract": "Text classification using transformer for question answering.",
            },
            "irrelevant",
            None,
        ),
        # 6) Dataset paper
        (
            {
                "candidate_id": "c6",
                "title": "NEU-DET: A steel surface defect benchmark dataset",
                "abstract": "We release NEU-DET, a benchmark for surface defect detection.",
            },
            "dataset_paper",
            None,
        ),
        # 7) Module improvement (CBAM on YOLOv8)
        (
            {
                "candidate_id": "c7",
                "title": "Attention-based feature fusion for steel defect detection",
                "abstract": "We add CBAM attention and feature pyramid fusion on YOLOv8 for defect detection, achieving better mAP.",
            },
            "parallel_application_paper",  # 命中 yolov8 -> parallel
            "yolov8",
        ),
    ]

    # 单条分类校验
    for cand, expected_role, expected_fw in cases:
        results = classify_literature([cand], topic)
        r = results[0]
        assert r.role == expected_role, f"{cand['candidate_id']}: expected {expected_role}, got {r.role}"
        if expected_fw is not None:
            assert r.base_framework == expected_fw, (
                f"{cand['candidate_id']}: expected base={expected_fw}, got {r.base_framework}"
            )

    # 模块矩阵: 至少 1 行
    results = classify_literature([c for c, *_ in cases], topic)
    parallels = [r for r in results if r.role == "parallel_application_paper"]
    matrix = _build_module_matrix(parallels)
    assert len(matrix) >= 1, f"expected >=1 matrix row, got {len(matrix)}"
    for row in matrix:
        assert row.base, "matrix row missing base"
        assert row.module_a, "matrix row missing module_a"
        assert row.dataset, "matrix row missing dataset"

    print(f"OK literature_role_classifier self-check passed ({len(cases)} cases, matrix={len(matrix)} rows)")