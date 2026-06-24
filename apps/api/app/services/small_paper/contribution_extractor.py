"""Small paper contribution extractor (Session 49 §4).

LLM 路径: chat_json 抽 contribution_points / method_modules / datasets / baselines /
metrics / experiment_tables / limitations, 然后写回 SmallPaperCard.

heuristic 路径: 基于 chunk_type + 关键词正则抽取 (复用 one_topic._METHOD_HINTS,
_PUBLIC_DATASET_OBJECTS 等).

失败策略: LLM 异常 → fallback heuristic, extraction_confidence=0.4.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ...schemas_paper_library import PaperChunk, PaperRecord
from ...schemas_small_paper import (
    ExtractionMode,
    SmallPaperCard,
)
from .. import paper_library as pl_service
from .. import llm as llm_service
from ..one_topic import (
    _METHOD_HINTS,
    _PUBLIC_DATASET_OBJECTS,
    _TASK_HINTS,
)

logger = logging.getLogger(__name__)


# ---------- heuristic 词典 ---------- #

# 评价指标关键词 (启发式)
_METRIC_HINTS = {
    "map": "mAP", "mAP": "mAP",
    "recall": "Recall", "precision": "Precision", "f1": "F1", "f1-score": "F1",
    "accuracy": "Accuracy", "auc": "AUC", "ap": "AP",
    "psnr": "PSNR", "ssim": "SSIM", "fid": "FID", "is": "IS",
    "bleu": "BLEU", "rouge": "ROUGE", "meteor": "METEOR",
    "rmse": "RMSE", "mae": "MAE", "mse": "MSE",
    "fps": "FPS", "latency": "Latency", "throughput": "Throughput",
    "ndcg": "NDCG", "mrr": "MRR", "hit rate": "Hit Rate",
}

# 抽取贡献点的 regex 触发词
_CONTRIBUTION_TRIGGERS = [
    r"we propose",
    r"we present",
    r"we introduce",
    r"our contribution",
    r"our approach",
    r"our method",
    r"in this (paper|work|study), we",
    r"the main contribution",
    r"本文提出",
    r"我们提出",
    r"本文的主要贡献",
    r"本文贡献",
    r"本文的贡献",
]

# 局限性 regex
_LIMITATION_TRIGGERS = [
    r"limitation",
    r"future work",
    r"does not",
    r"fails to",
    r"remains (a )?challenge",
    r"局限性",
    r"未来工作",
    r"不足之处",
    r"未能",
    r"尚未",
]


# ---------- helper ---------- #


def _safe_text(*pieces: str | None) -> str:
    return "\n".join((p or "") for p in pieces if p).strip()


def _collect_chunks_text(
    chunks: list[PaperChunk],
    chunk_types: tuple[str, ...] | None = None,
) -> str:
    """把指定 chunk_type 的文本拼起来, 限长."""
    out: list[str] = []
    for c in chunks:
        if chunk_types and c.chunk_type not in chunk_types:
            continue
        out.append((c.text or "").strip())
    text = "\n\n".join(t for t in out if t)
    return text[:6000]


def _dedup_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        k = (it or "").strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(it.strip())
    return out


# ---------- LLM 抽取 ---------- #


_LLM_PROMPT = """你是一个学术论文抽取助手. 阅读以下论文摘要 / 引言 / 方法 / 实验 / 结论的 chunk 文本,
抽取以下结构化字段, 严格用 JSON 返回 (不要任何解释/代码块):

- contribution_points: list[str], 1-3 条, 每条一句话总结本论文的核心贡献
- method_modules: list[str], 提到的方法 / 模型 / 框架名称
- datasets: list[str], 使用的数据集名称 (用原文)
- baselines: list[str], 对比的 baseline 名称
- metrics: list[str], 评价指标 (mAP, Recall, F1, BLEU ...)
- experiment_tables: list[str], 1-2 句话描述主要实验表格
- limitations: list[str], 1-3 条局限性 / 未来工作

如果某个字段在论文中没提到, 返回空 list. 不要编造.

论文 chunk 文本:
{context}

返回 JSON (严格遵循字段名):
"""


def _llm_extract(
    chunks_text: str,
) -> dict[str, Any] | None:
    """调 LLM 抽字段, 失败返回 None."""

    if not chunks_text.strip():
        return None
    try:
        result = llm_service.chat_json(
            _LLM_PROMPT.format(context=chunks_text[:5000]),
            system="你是一个学术论文结构化抽取助手, 严格返回 JSON, 不要解释.",
            temperature=0.1,
            max_tokens=1200,
        )
    except llm_service.LLMUnavailable as exc:
        logger.info("LLM 抽取失败, fallback heuristic: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM 抽取异常, fallback heuristic: %s", exc)
        return None

    if not isinstance(result, dict):
        return None
    return result


# ---------- heuristic 抽取 ---------- #


def _heuristic_extract(
    chunks: list[PaperChunk],
    paper: PaperRecord,
) -> dict[str, Any]:
    """基于 chunk_type + 关键词正则的轻量抽取."""

    abstract = _collect_chunks_text(chunks, ("abstract",))
    intro = _collect_chunks_text(chunks, ("introduction",))
    method = _collect_chunks_text(chunks, ("method",))
    experiment = _collect_chunks_text(chunks, ("experiment", "result"))
    conclusion = _collect_chunks_text(chunks, ("conclusion", "limitation"))

    # contribution_points
    contributions: list[str] = []
    for src in (abstract, intro):
        for pat in _CONTRIBUTION_TRIGGERS:
            for m in re.finditer(pat, src, re.IGNORECASE):
                # 取该 match 所在的整句
                start = max(src.rfind(".", 0, m.start()) + 1, 0)
                end = src.find(".", m.end())
                if end < 0:
                    end = min(m.end() + 200, len(src))
                sent = src[start:end].strip()
                if 12 <= len(sent) <= 200:
                    contributions.append(sent)
                if len(contributions) >= 3:
                    break
            if len(contributions) >= 3:
                break
        if len(contributions) >= 3:
            break
    if not contributions:
        # 兜底: abstract 前 3 句
        sents = re.split(r"(?<=[.。])\s+", abstract)
        contributions = [s.strip() for s in sents[:3] if 12 <= len(s.strip()) <= 200]

    # method_modules: 复用 _METHOD_HINTS
    methods: list[str] = []
    for hint, label in _METHOD_HINTS.items():
        if re.search(rf"\b{re.escape(hint)}\b", method, re.IGNORECASE):
            if label not in methods:
                methods.append(label)
    if not methods:
        # 兜底: 从 method chunk 抽大写名词短语
        for m in re.finditer(r"\b([A-Z][A-Za-z0-9]{2,15})\b", method):
            tok = m.group(1)
            if tok.lower() not in {"the", "and", "for", "with", "from", "this"}:
                methods.append(tok)
            if len(methods) >= 5:
                break

    # datasets: 复用 _PUBLIC_DATASET_OBJECTS (中文键) + 英文公开数据集关键词
    datasets: list[str] = []
    full = abstract + "\n" + method + "\n" + experiment
    for hint, name in _PUBLIC_DATASET_OBJECTS.items():
        if hint.lower() in full.lower():
            if name not in datasets:
                datasets.append(name)
    # 英文公开数据集直接匹配
    for eng in ("NEU-DET", "DeepPCB", "CODEBRIM", "HAM10000", "LUNA16",
                "KITTI", "CityPersons", "CellNuclei", "PlantDoc", "FruitVeg"):
        if eng in full and eng not in datasets:
            datasets.append(eng)

    # baselines: 启发式 — "vs / compared with / baseline" 后的 1-3 个大写词
    baselines: list[str] = []
    for m in re.finditer(
        r"(?:vs\.?|compared\s+(?:to|with)|baseline[s]?[:\s]|state[- ]of[- ]the[- ]art)\s*"
        r"([A-Z][A-Za-z0-9\-]{2,}(?:\s*,\s*[A-Z][A-Za-z0-9\-]{2,}){0,3})",
        experiment, re.IGNORECASE,
    ):
        for tok in re.split(r"\s*,\s*", m.group(1)):
            t = tok.strip()
            if t and t not in baselines and t.lower() not in {"the", "and"}:
                baselines.append(t)
            if len(baselines) >= 5:
                break
        if len(baselines) >= 5:
            break

    # metrics
    metrics: list[str] = []
    for hint, label in _METRIC_HINTS.items():
        if re.search(rf"\b{re.escape(hint)}\b", experiment, re.IGNORECASE):
            if label not in metrics:
                metrics.append(label)
        if len(metrics) >= 8:
            break

    # experiment_tables: 启发式 — "Table 1" 等
    tables: list[str] = []
    for m in re.finditer(r"Table\s+(\d+)[:\.\s]+([^\n.]{8,100})", experiment):
        cap = f"Table {m.group(1)}: {m.group(2).strip()}"
        if cap not in tables:
            tables.append(cap)
        if len(tables) >= 3:
            break

    # limitations
    limitations: list[str] = []
    for src in (conclusion, experiment):
        for pat in _LIMITATION_TRIGGERS:
            for m in re.finditer(pat, src, re.IGNORECASE):
                start = max(src.rfind(".", 0, m.start()) + 1, 0)
                end = src.find(".", m.end())
                if end < 0:
                    end = min(m.end() + 200, len(src))
                sent = src[start:end].strip()
                if 12 <= len(sent) <= 200:
                    limitations.append(sent)
                if len(limitations) >= 3:
                    break
            if len(limitations) >= 3:
                break
        if len(limitations) >= 3:
            break

    return {
        "contribution_points": _dedup_preserve_order(contributions)[:3],
        "method_modules": _dedup_preserve_order(methods)[:6],
        "datasets": _dedup_preserve_order(datasets)[:6],
        "baselines": _dedup_preserve_order(baselines)[:6],
        "metrics": _dedup_preserve_order(metrics)[:8],
        "experiment_tables": tables[:3],
        "limitations": _dedup_preserve_order(limitations)[:3],
    }


# ---------- 公共 API ---------- #


def extract_small_paper_card(
    project_id: str,
    paper_id: str,
    *,
    prefer: str = "auto",
) -> SmallPaperCard:
    """抽取小论文结构化卡片.

    prefer:
      - "auto"      LLM 优先, 失败 fallback heuristic
      - "llm"       强制 LLM, 失败抛 LLMUnavailable
      - "heuristic" 强制规则

    Raises:
        ValueError: paper_id 不存在
    """

    paper = pl_service.get_paper(project_id, paper_id)
    if paper is None:
        raise ValueError(f"paper_id {paper_id} 不存在")
    chunks = pl_service.get_paper_chunks(project_id, paper_id)
    full_text = pl_service.get_paper_text_excerpt(project_id, paper_id)

    # evidence_refs: 关联 chunk evidence (S48 已为 chunk 写过 ledger)
    evidence_refs: list[str] = []
    try:
        from .. import evidence as ev_store
        # 找 ledger 里 type=paper_library_chunk 且 paper_id=... 的项
        pool = ev_store.get_pool_items(project_id)
        for it in pool:
            if getattr(it, "paper_id", None) == paper_id and getattr(it, "chunk_id", None):
                evidence_refs.append(it.evidence_id)
                if len(evidence_refs) >= 8:
                    break
    except Exception as exc:  # noqa: BLE001
        logger.info("evidence_refs 关联失败 (non-fatal): %s", exc)

    chunks_text = _collect_chunks_text(chunks) or full_text

    # 决策
    fields: dict[str, Any]
    mode: ExtractionMode
    confidence: float

    if prefer == "heuristic":
        fields = _heuristic_extract(chunks, paper)
        mode = "heuristic"
        confidence = 0.4
    elif prefer == "llm":
        llm_result = _llm_extract(chunks_text)
        if not llm_result:
            raise llm_service.LLMUnavailable("LLM 强制模式: 抽取失败")
        fields = llm_result
        mode = "llm"
        confidence = 0.8
    else:  # auto
        llm_result = _llm_extract(chunks_text)
        if llm_result:
            fields = llm_result
            mode = "llm"
            confidence = 0.8
        else:
            fields = _heuristic_extract(chunks, paper)
            mode = "heuristic"
            confidence = 0.4

    # 健壮性: 缺失字段填充
    def _list(name: str) -> list[str]:
        v = fields.get(name) or []
        if not isinstance(v, list):
            return []
        return [str(x).strip() for x in v if str(x).strip()]

    # 章节复用 / 缺口
    reusable = _list("reusable_chapter_sections")
    if not reusable:
        # heuristic: 按 chunk_type 推断可复用章节
        types = {c.chunk_type for c in chunks if c.chunk_type != "unknown"}
        if "method" in types:
            reusable.append("方法主体可作为大论文第 3 章基础")
        if "experiment" in types or "result" in types:
            reusable.append("实验表格可作为大论文第 4 章基础 (需扩展数据集/baseline)")
        if "limitation" in types:
            reusable.append("局限性可作为大论文第 5 章延伸起点")

    missing = _list("missing_for_thesis")
    if not missing:
        # heuristic: 标准 5 章
        has_types = {c.chunk_type for c in chunks}
        if "related_work" not in has_types:
            missing.append("缺少相关工作章节 (建议补国内外研究现状)")
        if "experiment" not in has_types and "result" not in has_types:
            missing.append("缺少实验结果章节 (建议补多数据集泛化 / 消融)")
        if "conclusion" not in has_types and "limitation" not in has_types:
            missing.append("缺少结论 / 局限性讨论 (建议补失败案例 / 边界研究)")

    return SmallPaperCard(
        paper_id=paper.paper_id,
        project_id=paper.project_id,
        title=paper.title,
        publication_status="unknown",
        venue=paper.venue,
        contribution_points=_list("contribution_points"),
        method_modules=_list("method_modules"),
        datasets=_list("datasets"),
        baselines=_list("baselines"),
        metrics=_list("metrics"),
        experiment_tables=_list("experiment_tables"),
        limitations=_list("limitations"),
        reusable_chapter_sections=reusable,
        missing_for_thesis=missing,
        evidence_refs=evidence_refs,
        extraction_confidence=confidence,
        extraction_mode=mode,
    )
