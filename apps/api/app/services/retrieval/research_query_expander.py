"""Session 61 M1: ResearchQueryExpander.

Pure heuristic expansion of a raw research topic into paper / dataset / repo
queries. No LLM, no network. Extends the ``_OBJECT_HINTS`` style mapping from
``query_plan.py`` with structural-health / 3D-imaging / damage vocabulary.

Ponytail: a single pure function + dataclass, used by gap_report / retry_planner
downstream. Self-check via ``__main__``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# 扩展对象词映射 (基于 query_plan._OBJECT_HINTS 风格)
_OBJECT_HINTS: list[tuple[str, str]] = [
    ("三维成像", "3D imaging"),
    ("三维", "3D"),
    ("3D成像", "3D imaging"),
    ("3d成像", "3D imaging"),
    ("3d reconstruction", "3D reconstruction"),
    ("三维重建", "3D reconstruction"),
    ("三维点云", "3D point cloud"),
    ("点云", "point cloud"),
    ("深度成像", "depth imaging"),
    ("损伤", "damage"),
    ("损坏", "damage"),
    ("损坏检测", "damage detection"),
    ("缺陷", "defect"),
    ("裂缝", "crack"),
    ("桥梁", "bridge"),
    ("桥", "bridge"),
    ("混凝土", "concrete"),
    ("混凝土结构", "concrete"),
    ("结构健康监测", "structural health monitoring"),
    ("结构监测", "structural health monitoring"),
    ("shm", "structural health monitoring"),
    ("检测", "inspection"),
    ("巡检", "inspection"),
]

# 方法词 (英文规范化输出)
_METHOD_WORDS = {
    "yolo", "yolov5", "yolov8", "faster", "rcnn", "ssd", "retinanet",
    "transformer", "vit", "bert", "gpt", "diffusion", "gan",
    "unet", "deeplab", "mask", "pointnet", "pointrcnn",
    "cnn", "lstm",
    "svm", "xgboost", "lightgbm",
}

# 任务词 (中英)
_TASK_WORDS = {
    "detection": "detection",
    "classification": "classification",
    "segmentation": "segmentation",
    "recognition": "recognition",
    "prediction": "prediction",
    "estimation": "estimation",
    "检测": "detection",
    "分类": "classification",
    "分割": "segmentation",
    "识别": "recognition",
    "预测": "prediction",
}

# dataset query 必须命中
_DATASET_REQUIRED = ["dataset", "benchmark", "public", "Kaggle", "HuggingFace"]
_REPO_REQUIRED = ["github", "pytorch", "implementation", "baseline", "code", "train"]


@dataclass
class ExpandedTopic:
    """题目扩展后的结构化查询集."""

    method_terms: list[str] = field(default_factory=list)
    task_terms: list[str] = field(default_factory=list)
    object_terms: list[str] = field(default_factory=list)
    resource_terms: list[str] = field(default_factory=list)
    paper_queries: list[str] = field(default_factory=list)
    dataset_queries: list[str] = field(default_factory=list)
    repo_queries: list[str] = field(default_factory=list)


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        s = (it or "").strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


def _extract_english_tokens(raw: str) -> list[str]:
    """抽 raw_topic 里显式英文 tokens."""
    out: list[str] = []
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9\-]+", raw or ""):
        w = m.group(0).lower()
        if w not in _METHOD_WORDS and w not in _TASK_WORDS and len(w) > 1:
            out.append(w)
    return out


def _detect_methods(raw: str) -> list[str]:
    raw_l = (raw or "").lower()
    return [m for m in _METHOD_WORDS if re.search(rf"\b{re.escape(m)}\b", raw_l)]


def _detect_tasks(raw: str) -> list[str]:
    raw_l = (raw or "").lower()
    out: list[str] = []
    for k, v in _TASK_WORDS.items():
        if k.lower() in raw_l and v not in out:
            out.append(v)
    return out


def _detect_objects(raw: str) -> list[str]:
    raw_l = (raw or "").lower()
    out: list[str] = []
    for zh, en in _OBJECT_HINTS:
        if zh in raw or en.lower() in raw_l:
            if en not in out:
                out.append(en)
    return out


def _ensure_required(query: str, required: list[str]) -> str:
    """如果 query 没有任何 required token, 追加第一个作为兜底."""
    q_l = query.lower()
    if any(tok.lower() in q_l for tok in required):
        return query
    return f"{query} {required[0]}"


def expand_topic(raw_topic: str) -> ExpandedTopic:
    """把 raw_topic 拆成方法/任务/对象/资源词 + paper/dataset/repo queries.

    无 LLM, 无网络. 中文 / 英文 / 混合都支持.
    """

    raw = (raw_topic or "").strip()
    if not raw:
        return ExpandedTopic()

    methods = _detect_methods(raw)
    tasks = _detect_tasks(raw)
    objects = _detect_objects(raw)
    tokens = _extract_english_tokens(raw)

    resource_terms = ["dataset", "benchmark", "github", "pytorch", "code"]
    core = " ".join(_dedup(objects + tasks + tokens)).strip()
    if not core:
        core = raw

    # ---------- paper queries ---------- #
    paper_qs: list[str] = []
    if raw:
        paper_qs.append(raw)
    if core and core.lower() != raw.lower():
        paper_qs.append(core)
    if methods and objects:
        paper_qs.append(" ".join(methods[:2] + objects[:2]))
    if objects:
        paper_qs.append(" ".join(objects[:3] + ["survey"]))

    # ---------- dataset queries (必须含 dataset/benchmark/public/...) ---------- #
    dataset_qs: list[str] = []
    if objects:
        base = " ".join(objects[:2] + tasks[:1])
        dataset_qs.append(_ensure_required(f"{base} dataset", _DATASET_REQUIRED))
    if core:
        dataset_qs.append(_ensure_required(f"{core} benchmark", _DATASET_REQUIRED))
    if methods and objects:
        dataset_qs.append(_ensure_required(
            " ".join(methods[:1] + objects[:1] + ["public", "HuggingFace"]),
            _DATASET_REQUIRED,
        ))

    # ---------- repo queries (必须含 github/pytorch/implementation/...) ---------- #
    repo_qs: list[str] = []
    if objects:
        base = " ".join(objects[:2] + tasks[:1])
        repo_qs.append(_ensure_required(f"{base} github pytorch", _REPO_REQUIRED))
    if methods:
        repo_qs.append(_ensure_required(
            " ".join(methods[:1] + objects[:1] + ["implementation", "baseline"]),
            _REPO_REQUIRED,
        ))
    if core:
        repo_qs.append(_ensure_required(f"{core} train code", _REPO_REQUIRED))

    return ExpandedTopic(
        method_terms=_dedup(methods),
        task_terms=_dedup(tasks),
        object_terms=_dedup(objects),
        resource_terms=resource_terms,
        paper_queries=_dedup(paper_qs)[:6],
        dataset_queries=_dedup(dataset_qs)[:5],
        repo_queries=_dedup(repo_qs)[:5],
    )


if __name__ == "__main__":
    # ponytail: self-check, fail loud if heuristic breaks
    topic = "基于三维成像的损伤智能检测"
    result = expand_topic(topic)

    assert result.paper_queries, "paper_queries empty"
    assert result.dataset_queries, "dataset_queries empty"
    assert result.repo_queries, "repo_queries empty"

    en_paper = " ".join(result.paper_queries).lower()
    assert any(tok in en_paper for tok in ("3d", "damage", "imaging")), (
        f"no 3D/damage/imaging in paper queries: {result.paper_queries}"
    )

    en_dataset = " ".join(result.dataset_queries).lower()
    assert any(tok.lower() in en_dataset for tok in _DATASET_REQUIRED), (
        f"dataset query missing required token: {result.dataset_queries}"
    )

    en_repo = " ".join(result.repo_queries).lower()
    assert any(tok in en_repo for tok in _REPO_REQUIRED), (
        f"repo query missing required token: {result.repo_queries}"
    )

    print(
        f"OK paper={len(result.paper_queries)} "
        f"dataset={len(result.dataset_queries)} repo={len(result.repo_queries)}"
    )