"""关键词命中解释器 (Session 65 T1).

把数字 retrieval_score 替换为用户可读的关键词命中解释:
- 命中: 题目核心方法/对象词在候选标题/摘要中出现
- 相关: 题目关联词 (modality/baseline 等) 出现, 但非核心对象
- 缺失: 题目必需词在候选中找不到
- 疑似无关: 候选中出现的、与题目毫无关系的特征词

设计要点:
- 纯本地逻辑, 不发请求, 不调 LLM, 不输出 0-1 分数
- 每个 atom 当作短词串, 用词边界匹配 (避免整句当单词的误命中)
- 只做解释, 不改变排序顺序的来源
- 集成点: candidate_cleaner 之后, RetrievalCandidatePanel 之前
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field


# 嫌疑无关特征词: 在 civil/nlp/vision 题目里, 这些词常常出现在 survey / 跨领域论文
UNRELATED_HINT_TOKENS = (
    "survey motivation", "german coding", "german open-ended",
    "active galactic", "galaxy formation", "protein fold",
    "drug discovery", "mlperf", "x-ray", "ct scan", "mri",
    "cosmology", "astrophysics",
)


class KeywordMatchExplanation(BaseModel):
    """单个候选的关键词命中解释."""

    model_config = {"extra": "forbid"}

    candidate_id: str
    matched_topic_keywords: list[str] = Field(default_factory=list)
    matched_related_keywords: list[str] = Field(default_factory=list)
    missing_required_keywords: list[str] = Field(default_factory=list)
    unrelated_keywords: list[str] = Field(default_factory=list)
    match_summary: str
    evidence_gap: Literal[
        "none",
        "object_missing",
        "task_missing",
        "method_missing",
        "dataset_missing",
        "repo_missing",
        "url_unverified",
        "wrong_domain",
    ] = "none"


def _atom_pattern(atom: str) -> re.Pattern[str]:
    """编译一个原子词的不区分大小写、词边界感知正则."""
    escaped = re.escape(atom.strip())
    # 中文字符不需要 \b 边界, 用 lookaround 兜底
    return re.compile(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])", re.IGNORECASE)


def _count_atoms_in_text(atoms: list[str], text: str) -> list[str]:
    """返回出现在 text 中的 atoms (保持原大小写, 去重保序)."""
    if not atoms or not text:
        return []
    seen: set[str] = set()
    hits: list[str] = []
    for atom in atoms:
        a = atom.strip()
        if not a or a.lower() in seen:
            continue
        if _atom_pattern(a).search(text):
            hits.append(a)
            seen.add(a.lower())
    return hits


def _detect_unrelated(text: str) -> list[str]:
    """返回 text 中出现的疑似无关特征词."""
    if not text:
        return []
    low = text.lower()
    hits: list[str] = []
    for tok in UNRELATED_HINT_TOKENS:
        if tok in low:
            hits.append(tok)
    return hits


def _detect_evidence_gap(
    matched_method: list[str],
    matched_task: list[str],
    matched_object: list[str],
    unmatched_required: list[str],
    source_status: str | None,
    unrelated_count: int = 0,
    has_text: bool = True,
) -> str:
    """根据命中分布判断主要缺失维度."""
    if source_status in {"fetch_failed", "redirect_offtopic", "dead"}:
        return "url_unverified"
    if not has_text:
        # 没有任何正文可读, 谈不了命中/缺失 — 视作 wrong_domain 占位
        return "wrong_domain"
    nothing_matched = not matched_method and not matched_task and not matched_object
    # 完全没命中, 且没有任何 required 线索 → wrong_domain
    if nothing_matched and not unmatched_required:
        return "wrong_domain"
    # 强跨领域信号: 命中为 0 且 unrelated >= 2 → 强烈疑似无关
    if nothing_matched and unrelated_count >= 2:
        return "wrong_domain"
    if unmatched_required:
        # 优先按 object → method → task 顺序报告
        low = [u.lower() for u in unmatched_required]
        if any("data" in u or "set" in u or "数据集" in u for u in low):
            return "dataset_missing"
        if any("code" in u or "github" in u or "repo" in u or "代码" in u for u in low):
            return "repo_missing"
        if not matched_object:
            return "object_missing"
        if not matched_method:
            return "method_missing"
        if not matched_task:
            return "task_missing"
    return "none"


def _format_match_summary(
    matched: list[str],
    related: list[str],
    missing: list[str],
    unrelated: list[str],
) -> str:
    """生成用户可见的中文摘要."""
    parts: list[str] = []
    if matched:
        parts.append(f"命中: {', '.join(matched[:6])}")
    if related:
        parts.append(f"相关: {', '.join(related[:6])}")
    if missing:
        parts.append(f"缺失: {', '.join(missing[:6])}")
    if unrelated:
        parts.append(f"疑似无关: {', '.join(unrelated[:4])}")

    # 结论: 综合判断
    if matched and not missing and not unrelated:
        conclusion = "对象匹配, 可作为核心证据"
    elif matched and missing and not unrelated:
        conclusion = "任务相关, 但存在缺口, 需人工确认或补搜"
    elif matched and unrelated:
        conclusion = "部分命中, 但含跨领域特征, 需人工确认"
    elif not matched and unrelated:
        conclusion = "未命中核心词, 且含跨领域特征, 疑似不相关"
    else:
        conclusion = "未命中题目核心关键词"

    parts.append(f"结论: {conclusion}.")
    return " | ".join(parts)


def explain_keyword_match(
    candidate: dict,
    topic_atoms: dict,
) -> KeywordMatchExplanation:
    """为单个候选生成关键词命中解释.

    Args:
        candidate: 候选 dict, 至少包含 candidate_id, title, abstract (可空)
        topic_atoms: 题目原子 dict, 包含 method_terms/task_terms/object_terms/modality_terms,
                     可选 required 列表 (来自 topic_understand)

    Returns:
        KeywordMatchExplanation
    """
    cid = str(candidate.get("candidate_id", ""))
    title = candidate.get("title") or ""
    abstract = candidate.get("abstract") or ""
    text = f"{title}\n{abstract}".strip()
    source_status = candidate.get("source_status") or candidate.get("clean_source_status")

    method_terms = list(topic_atoms.get("method_terms") or topic_atoms.get("method") or [])
    task_terms = list(topic_atoms.get("task_terms") or topic_atoms.get("task") or [])
    object_terms = list(topic_atoms.get("object_terms") or topic_atoms.get("object") or [])
    modality_terms = list(topic_atoms.get("modality_terms") or topic_atoms.get("modality") or [])
    required = list(topic_atoms.get("required") or [])

    matched_method = _count_atoms_in_text(method_terms, text)
    matched_task = _count_atoms_in_text(task_terms, text)
    matched_object = _count_atoms_in_text(object_terms, text)
    matched_modality = _count_atoms_in_text(modality_terms, text)

    matched_topic = matched_method + matched_task + matched_object
    matched_related = matched_modality

    # missing = required 中没有出现在 text 的
    missing_required = [r for r in required if r.strip() and r not in matched_topic]
    # 如果没有显式 required, 用 object/method/task 中未命中的当 missing
    if not missing_required:
        missing_required = [
            *([t for t in object_terms if t not in matched_object]),
            *([t for t in method_terms if t not in matched_method]),
            *([t for t in task_terms if t not in matched_task]),
        ]

    unrelated = _detect_unrelated(text)

    gap = _detect_evidence_gap(
        matched_method=matched_method,
        matched_task=matched_task,
        matched_object=matched_object,
        unmatched_required=missing_required,
        source_status=source_status,
        unrelated_count=len(unrelated),
        has_text=bool(text.strip()),
    )

    summary = _format_match_summary(
        matched=matched_topic,
        related=matched_related,
        missing=missing_required,
        unrelated=unrelated,
    )

    return KeywordMatchExplanation(
        candidate_id=cid,
        matched_topic_keywords=matched_topic,
        matched_related_keywords=matched_related,
        missing_required_keywords=missing_required,
        unrelated_keywords=unrelated,
        match_summary=summary,
        evidence_gap=gap,
    )


def explain_candidates(
    candidates: list[dict],
    topic_atoms: dict,
) -> list[KeywordMatchExplanation]:
    """批量生成候选的关键词命中解释."""
    return [explain_keyword_match(c, topic_atoms) for c in candidates]


__all__ = [
    "KeywordMatchExplanation",
    "explain_keyword_match",
    "explain_candidates",
]