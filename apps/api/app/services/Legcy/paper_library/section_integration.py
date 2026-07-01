"""Session 48: FinalPackage integration helpers.

提供两类 hook:
1. extract_section_claims(content) -> list[str]
   - 从 Markdown section content 抽出声明性句子 (含 ". 是/为/达/有" / "达到" / "实现" / 数字 等断言模式).
   - 跳过引用/列表/标题.

2. enforce_section_citation_rules(project_id, section_evidence_refs) -> (refs, warnings)
   - 复用 paper_qa.filter_refs_by_citation_rules 规则.
   - rejected 移除; pending direct 降级 background; failed verification 降级 background.

集成位置 (SOP §6):
   final_package.build_final_package() 调用 _build_sections() 后, 可:
     for sec in sections:
         claims = extract_section_claims(sec.content)
         for c in claims:
             res = claim_grounding.ground_claim(c, project_id, scope="accepted_papers")
             if res.verdict in ("unsupported", "contradiction"):
                 sec.unsupported_claims.append(f"{res.verdict}: {c[:60]}")
         sec.evidence_refs, w = enforce_section_citation_rules(project_id, sec.evidence_refs)

   本轮不直接修改 final_package.py (避免破坏既有 build 流程); 集成点由上游 agent 显式调用.
"""

from __future__ import annotations

import re

from . import claim_grounding, paper_qa


# ---------------------------------------------------------------------------
# Claim 抽取 (heuristic)
# ---------------------------------------------------------------------------


# 跳过列表开头 / 标题
_HEADING_RE = re.compile(r"^#{1,6}\s")
_LIST_RE = re.compile(r"^\s*[-*\d.]+\s")
_QUOTE_RE = re.compile(r"^>\s")
_BRACKET_REF_RE = re.compile(r"\[[EDRN]\d+\]")

# 声明性关键词 (中英)
_ASSERTION_PATTERNS = [
    re.compile(r"[。.]\s*[^。.]*(?:是|为|达|有|实现|取得|采用|使用|提供|支持|达到|提出|表明|证明|显示)[^。.]*[。.]"),
    re.compile(r"^(?:[^。.\n]*?)(?:是|为|达|有|实现|取得|采用|使用|提供|支持|达到|提出|表明|证明|显示)[^。.\n]*[。.]"),
    re.compile(r"\b(?:is|are|was|were|achieves?|attains?|reaches?|proposes?|uses?|shows?|demonstrates?|provides?|introduces?|presents?)\b[^.]*\."),
]

# 数字断言 (例如 "mAP 0.85", "accuracy 95%")
_NUMERIC_RE = re.compile(r"\b\d+(?:\.\d+)?%?\b")


def extract_section_claims(content: str) -> list[str]:
    """从 Markdown section content 抽声明性句子.

    跳过:
      - 标题行 (## / ###)
      - 列表项
      - 引用行 (>)
      - 极短句 (< 10 字)
      - 已被 [E1]/[D1]/[R1]/[N1] 引用的整句 (引用句不再 ground)
    """

    if not content:
        return []
    out: list[str] = []
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _HEADING_RE.match(line):
            continue
        if _LIST_RE.match(line):
            continue
        if _QUOTE_RE.match(line):
            continue
        # 切句 (中英句号)
        sentences = re.split(r"(?<=[。.!？?])\s+", line)
        for s in sentences:
            s = s.strip()
            if len(s) < 10:
                continue
            # 整句都是引用 → 跳过
            if _BRACKET_REF_RE.search(s) and not _NUMERIC_RE.search(s):
                # 仍含数字则视为断言, 不跳
                continue
            # 匹配声明性模式 OR 含数字 → 视为 claim
            if any(p.search(s) for p in _ASSERTION_PATTERNS) or _NUMERIC_RE.search(s):
                out.append(s)
    return out


# ---------------------------------------------------------------------------
# Section 引用规则强制
# ---------------------------------------------------------------------------


def enforce_section_citation_rules(
    project_id: str,
    section_evidence_refs: list,
) -> tuple[list, list[str]]:
    """复用 paper_qa.filter_refs_by_citation_rules 的规则.

    Args:
        section_evidence_refs: list[EvidenceRef] (from paper_qa / claim_grounding)

    Returns:
        (filtered_refs, warnings)
    """

    # 统一转成 EvidenceRef (调用方可能传 dict)
    from ...schemas_paper_rag import EvidenceRef

    refs: list[EvidenceRef] = []
    for r in section_evidence_refs or []:
        if isinstance(r, EvidenceRef):
            refs.append(r)
        elif isinstance(r, dict):
            try:
                refs.append(EvidenceRef(**r))
            except Exception:  # noqa: BLE001
                continue
    return paper_qa.filter_refs_by_citation_rules(project_id, refs)


# ---------------------------------------------------------------------------
# Section grounding (Task 5: FinalPackage 集成)
# ---------------------------------------------------------------------------


def ground_section_claims(
    project_id: str,
    section_content: str,
    scope: str = "accepted_papers",
) -> tuple[list[claim_grounding.ClaimGroundingResult], list[str]]:
    """对一个 section 的 content 抽 claim 并 grounding.

    Returns: (results, unsupported_claims)
      - results: 每个 claim 的 ClaimGroundingResult
      - unsupported_claims: verdict in (unsupported, contradiction) 的 claim (供 FinalPackage 累积)
    """

    claims = extract_section_claims(section_content)
    results: list[claim_grounding.ClaimGroundingResult] = []
    unsupported: list[str] = []
    for c in claims:
        try:
            res = claim_grounding.ground_claim(c, project_id, scope=scope, top_k=3)
        except Exception as exc:  # noqa: BLE001
            logger = __import__("logging").getLogger(__name__)
            logger.warning("ground_claim failed for %r: %s", c[:60], exc)
            continue
        results.append(res)
        if res.verdict in ("unsupported", "contradiction"):
            unsupported.append(f"{res.verdict}: {c[:80]}")
    return results, unsupported


__all__ = [
    "enforce_section_citation_rules",
    "extract_section_claims",
    "ground_section_claims",
]