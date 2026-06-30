"""候选清洗器 (SOP §11.5).

在用户可见展示之前剔除明显不相关的候选:
- AGN / 天文 / 德语 survey / 医学影像 / MLPerf 基准 等明显跑题
- retrieval_score 极低且无 matched_atoms
- URL 无法打开或跳转无关页面
- 仅 survey 且不含任务对象 (concrete / crack / bridge / damage 等)

硬规则先判, LLM 仅做细化. 规则与 LLM 冲突时以规则为准, 标 needs_manual.
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from pydantic import BaseModel

from ..llm import LLMUnavailable, chat_json

logger = logging.getLogger(__name__)


# 题目对象关键词 (硬规则触发条件之一)
CIVIL_OBJECT_TOKENS = (
    "concrete", "crack", "bridge", "damage", "concrete crack",
    "concrete surface", "civil engineering", "structural",
    "混凝土", "裂缝", "桥梁", "损伤",
)

# 明显跑题的标题模式 (大小写不敏感)
IRRELEVANT_TITLE_PATTERNS = [
    r"\bAGN\b",
    r"active galactic nuclei",
    r"\bastronomy\b",
    r"\bastrophysics\b",
    r"\bgalaxy\b",
    r"\bcosmology\b",
    r"\bgerman\b.*\bsurvey\b",
    r"\bgerman\b.*\bcoding\b",
    r"survey motivation",
    r"\bmlperf\b",
    r"benchmarking ml",
    r"medical imaging",
    r"\bx-?ray\b",
    r"\bct scan\b",
    r"\bmri\b",
    r"\bradiolog",
    r"\bprotein\b.*\bfold",
    r"\bdrug discovery\b",
]

# MLPerf / 通用 ML benchmark (任何 civil 题目都算跑题)
BENCHMARK_PATTERNS = [
    r"\bmlperf\b",
    r"\bbenchmarking ml\b",
    r"\bleaderboard\b",
]

# Survey-only 判定 (无具体方法名/任务对象)
SURVEY_TITLE_HINTS = (
    "a survey", "a review", "an overview", "systematic review",
    "literature review", "taxonomy of", "comprehensive survey",
)


class CandidateCleanResult(BaseModel):
    """单个候选的清洗结果."""

    model_config = {"extra": "forbid"}

    candidate_id: str
    clean_status: Literal["keep", "quarantine", "reject", "needs_manual"]
    mismatch_type: Literal[
        "none",
        "wrong_domain",
        "wrong_task",
        "wrong_url",
        "not_paper",
        "metadata_mismatch",
        "low_relevance",
        "source_failed",
    ]
    matched_atoms: list[str]
    missing_required_atoms: list[str]
    reason: str
    confidence: float


def is_irrelevant_title(title: str) -> bool:
    """标题是否匹配明显的跑题模式 (AGN / 天文 / 德语 survey / 医学 / MLPerf)."""
    if not title:
        return False
    low = title.lower()
    for pat in IRRELEVANT_TITLE_PATTERNS:
        if re.search(pat, low):
            return True
    return False


def _has_civil_object(text: str) -> bool:
    low = (text or "").lower()
    return any(tok in low for tok in CIVIL_OBJECT_TOKENS)


def _is_survey_only(title: str, abstract: str | None) -> bool:
    low_title = (title or "").lower()
    if not any(hint in low_title for hint in SURVEY_TITLE_HINTS):
        return False
    # survey 但摘要中有 civil object → 保留; 否则视为 survey-only
    if abstract and _has_civil_object(abstract):
        return False
    return True


def _is_benchmark_paper(title: str, abstract: str | None) -> bool:
    low = f"{title} {abstract or ''}".lower()
    return any(re.search(p, low) for p in BENCHMARK_PATTERNS)


def _hard_rule_check(
    candidate: dict,
    topic_atoms: dict,
    domain: str,
) -> CandidateCleanResult | None:
    """应用硬规则. 返回 None 表示无规则命中, 由 LLM 细化."""
    cid = candidate.get("candidate_id", "")
    title = candidate.get("title", "") or ""
    abstract = candidate.get("abstract")
    score = float(candidate.get("retrieval_score", 0.0) or 0.0)
    matched = list(candidate.get("matched_atoms") or candidate.get("matched_keywords") or [])
    url = candidate.get("url") or ""
    source_status = candidate.get("source_status") or "ok"

    required_atoms = list(topic_atoms.get("required") or [])

    # 规则 1: retrieval_score 极低且无 matched_atoms → reject
    if score < 0.20 and not matched:
        return CandidateCleanResult(
            candidate_id=cid,
            clean_status="reject",
            mismatch_type="low_relevance",
            matched_atoms=[],
            missing_required_atoms=required_atoms,
            reason=f"retrieval_score={score:.3f}<0.20 且 matched_atoms 为空",
            confidence=0.95,
        )

    # 规则 2: 题目对象是 civil (concrete/crack/bridge/damage) 且标题跑题 → reject
    domain_lower = (domain or "").lower()
    topic_has_civil = (
        _has_civil_object(topic_atoms.get("raw", ""))
        or _has_civil_object(topic_atoms.get("domain_hint", ""))
        or "vision_2d" in domain_lower
        or "civil" in domain_lower
        or domain_lower in {"concrete_crack", "bridge_damage"}
    )
    if topic_has_civil and is_irrelevant_title(title):
        return CandidateCleanResult(
            candidate_id=cid,
            clean_status="reject",
            mismatch_type="wrong_domain",
            matched_atoms=matched,
            missing_required_atoms=required_atoms,
            reason=f"civil 题目命中明显跑题标题模式: {title[:80]!r}",
            confidence=0.92,
        )

    # 规则 3: URL 打不开或跳转无关页面 → quarantine
    if source_status in {"fetch_failed", "redirect_offtopic", "dead"} or not url:
        return CandidateCleanResult(
            candidate_id=cid,
            clean_status="quarantine",
            mismatch_type="wrong_url",
            matched_atoms=matched,
            missing_required_atoms=required_atoms,
            reason=f"source_status={source_status}, url={url[:60]!r}",
            confidence=0.85,
        )

    # 规则 4: survey-only 且无任务对象 → quarantine
    if _is_survey_only(title, abstract):
        if topic_has_civil and not _has_civil_object(abstract or ""):
            return CandidateCleanResult(
                candidate_id=cid,
                clean_status="quarantine",
                mismatch_type="not_paper",
                matched_atoms=matched,
                missing_required_atoms=required_atoms,
                reason="survey-only 且无任务对象 (abstract 中无 civil 关键词)",
                confidence=0.80,
            )

    # 规则 4b: benchmark 论文 (MLPerf 等) → reject
    if _is_benchmark_paper(title, abstract):
        return CandidateCleanResult(
            candidate_id=cid,
            clean_status="reject",
            mismatch_type="wrong_domain",
            matched_atoms=matched,
            missing_required_atoms=required_atoms,
            reason=f"benchmark 论文与 civil 任务无关: {title[:80]!r}",
            confidence=0.90,
        )

    return None


def _llm_refine(candidate: dict, topic_atoms: dict) -> CandidateCleanResult:
    """LLM 细化分类 (规则未命中时调用). 失败则降级为 keep."""
    cid = candidate.get("candidate_id", "")
    title = candidate.get("title", "")
    abstract = (candidate.get("abstract") or "")[:1200]
    matched = list(candidate.get("matched_atoms") or candidate.get("matched_keywords") or [])
    required = list(topic_atoms.get("required") or [])
    raw_topic = topic_atoms.get("raw", "")

    system = "你是论文相关性审核员, 严格输出 JSON dict."
    prompt = (
        f"题目: {raw_topic}\n"
        f"论文标题: {title}\n"
        f"摘要: {abstract}\n"
        f"已匹配 atoms: {matched}\n"
        f"必需 atoms: {required}\n\n"
        "判断这篇论文是否与题目相关. 输出 JSON:\n"
        '{"clean_status": "keep|quarantine", "mismatch_type": "none|wrong_domain|wrong_task|'
        'metadata_mismatch|low_relevance", "matched_atoms": [...], '
        '"missing_required_atoms": [...], "reason": "...", "confidence": 0.0-1.0}'
    )

    try:
        data = chat_json(prompt, system=system, temperature=0.1, max_tokens=400, timeout=20.0)
    except LLMUnavailable as exc:
        logger.warning("candidate_cleaner: LLM 不可用, 降级为 keep: %s", exc)
        return CandidateCleanResult(
            candidate_id=cid,
            clean_status="keep",
            mismatch_type="none",
            matched_atoms=matched,
            missing_required_atoms=[a for a in required if a not in matched],
            reason="LLM 不可用, 默认 keep",
            confidence=0.5,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("candidate_cleaner: LLM 调用异常, 降级为 keep: %s", exc)
        return CandidateCleanResult(
            candidate_id=cid,
            clean_status="keep",
            mismatch_type="none",
            matched_atoms=matched,
            missing_required_atoms=[a for a in required if a not in matched],
            reason=f"LLM 调用异常: {exc!r}, 默认 keep",
            confidence=0.5,
        )

    status = data.get("clean_status", "keep")
    if status not in {"keep", "quarantine"}:
        status = "keep"
    mismatch = data.get("mismatch_type", "none")
    if mismatch not in {
        "none", "wrong_domain", "wrong_task", "wrong_url",
        "not_paper", "metadata_mismatch", "low_relevance", "source_failed",
    }:
        mismatch = "none"

    return CandidateCleanResult(
        candidate_id=cid,
        clean_status=status,
        mismatch_type=mismatch,
        matched_atoms=list(data.get("matched_atoms") or matched),
        missing_required_atoms=list(data.get("missing_required_atoms") or []),
        reason=str(data.get("reason") or ""),
        confidence=float(data.get("confidence") or 0.6),
    )


def clean_candidates(
    candidates: list[dict],
    topic_atoms: dict,
    domain: str = "vision_2d",
) -> list[CandidateCleanResult]:
    """清洗候选列表. 返回按 keep → quarantine → reject → needs_manual 排序的结果."""
    results: list[CandidateCleanResult] = []
    for cand in candidates:
        cid = cand.get("candidate_id", "")
        # 规则 1 先跑
        ruled = _hard_rule_check(cand, topic_atoms, domain)
        if ruled is not None:
            results.append(ruled)
            logger.info(
                "clean_candidate[%s] status=%s reason=%s",
                cid, ruled.clean_status, ruled.reason,
            )
            continue

        # 规则未命中 → LLM 细化
        refined = _llm_refine(cand, topic_atoms)

        # 规则 5: 硬规则未触发, LLM 不能 reject; 若 LLM 输出 reject 改 needs_manual
        if refined.clean_status == "reject":
            refined = refined.model_copy(update={
                "clean_status": "needs_manual",
                "reason": f"LLM 判定 reject 但无硬规则命中: {refined.reason}",
                "confidence": min(refined.confidence, 0.6),
            })

        results.append(refined)
        logger.info(
            "clean_candidate[%s] status=%s reason=%s",
            cid, refined.clean_status, refined.reason,
        )

    status_order = {"keep": 0, "quarantine": 1, "needs_manual": 2, "reject": 3}
    results.sort(key=lambda r: (status_order.get(r.clean_status, 9), -r.confidence))
    return results


__all__ = [
    "CandidateCleanResult",
    "clean_candidates",
    "is_irrelevant_title",
]