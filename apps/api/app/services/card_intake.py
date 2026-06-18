"""Agent Card Intake 最小入口 (Session 9 §4.4).

从 URL / 文字 / hint 识别类型 (paper / dataset / repo), 生成 assistant_intake
的 pending EvidenceItem. 不抓网页, 不调外部 API.
"""

from __future__ import annotations

import re
import uuid
from typing import Literal

from ..schemas_evidence import EvidenceItem, EvidenceLedgerResponse
from . import evidence as ev_store


CardType = Literal["paper", "dataset", "repo", "note"]


# ---------- URL / hint 识别规则 (§4.4) ---------- #


_GH_RE = re.compile(r"github\.com/([\w.-]+)/([\w.-]+)", re.IGNORECASE)
_ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([\w./-]+)", re.IGNORECASE)
_HF_DATASET_RE = re.compile(r"huggingface\.co/datasets/([\w.-]+)", re.IGNORECASE)
_HF_MODEL_RE = re.compile(r"huggingface\.co/([\w.-]+)/([\w.-]+)", re.IGNORECASE)
_KAGGLE_DATASET_RE = re.compile(r"kaggle\.com/datasets/([\w./-]+)", re.IGNORECASE)
_KAGGLE_COMP_RE = re.compile(r"kaggle\.com/competitions/([\w./-]+)", re.IGNORECASE)


def identify_card_type(content: str, hint: str | None, input_type: str) -> tuple[CardType, str, str | None, str | None, list[str]]:
    """识别 card type, 返回 (card_type, title, url, download, warnings)."""

    content = (content or "").strip()
    hint_l = (hint or "").lower()
    warnings: list[str] = []

    # URL 类
    if input_type in ("url", "github", "paper_page", "dataset_page") or content.startswith("http"):
        m = _GH_RE.search(content)
        if m:
            owner, repo = m.group(1), m.group(2)
            return "repo", f"{owner}/{repo}", content, None, _repo_warnings(content)
        m = _ARXIV_RE.search(content)
        if m:
            arxiv_id = m.group(1).rstrip(".pdf")
            return "paper", f"arXiv:{arxiv_id}", content, None, _paper_warnings(content)
        m = _HF_DATASET_RE.search(content)
        if m:
            name = m.group(1)
            return "dataset", f"HF:{name}", content, content, _dataset_warnings(content)
        m = _HF_MODEL_RE.search(content)
        if m:
            owner, model = m.group(1), m.group(2)
            return "repo", f"{owner}/{model}", content, None, _repo_warnings(content)
        m = _KAGGLE_DATASET_RE.search(content)
        if m:
            name = m.group(1)
            return "dataset", f"Kaggle:{name}", content, content, _dataset_warnings(content)
        m = _KAGGLE_COMP_RE.search(content)
        if m:
            return "dataset", f"Kaggle-Comp:{m.group(1)}", content, content, _dataset_warnings(content)

    # hint 关键词匹配
    if any(k in hint_l for k in ("论文", "paper", "文献", "research")):
        return "paper", _short_title_from_text(content) or "(待补标题)", None, None, _paper_warnings(content)
    if any(k in hint_l for k in ("数据集", "dataset", "数据")):
        return "dataset", _short_title_from_text(content) or "(待补标题)", None, None, _dataset_warnings(content)
    if any(k in hint_l for k in ("代码", "工程", "repo", "baseline", "实现", "github")):
        return "repo", _short_title_from_text(content) or "(待补标题)", None, None, _repo_warnings(content)

    # 纯文本 → note
    if input_type == "text" or not content.startswith("http"):
        return "note", _short_title_from_text(content) or "(待补标题)", None, None, ["纯文本未识别具体类型, 默认 note"]

    # 默认 paper
    return "paper", _short_title_from_text(content) or "(待补标题)", content, None, _paper_warnings(content)


def _short_title_from_text(s: str, n: int = 60) -> str:
    if not s:
        return ""
    s = s.splitlines()[0].strip()
    return s if len(s) <= n else s[:n] + "..."


def _paper_warnings(content: str) -> list[str]:
    w = []
    if not _ARXIV_RE.search(content):
        w.append("未识别为 arXiv URL, 可能缺少 DOI / 引用信息")
    if "doi" not in content.lower():
        w.append("缺少 DOI")
    return w


def _dataset_warnings(content: str) -> list[str]:
    w = []
    if not (_HF_DATASET_RE.search(content) or _KAGGLE_DATASET_RE.search(content)):
        w.append("未识别为 HF/Kaggle 数据集 URL, license 状态未确认")
    if "license" not in content.lower():
        w.append("缺少 license 信息")
    return w


def _repo_warnings(content: str) -> list[str]:
    w = []
    if not _GH_RE.search(content):
        w.append("未识别为 GitHub URL, 可能只是文档/博客")
    w.append("未实际验证 train/eval 脚本")
    return w


# ---------- 生成 EvidenceItem ---------- #


def intake_card(
    project_id: str,
    input_type: str,
    content: str,
    hint: str | None,
    target_lane: str = "user_preferred",
) -> tuple[EvidenceItem, str, float, list[str]]:
    """从 input_type + content + hint 生成 pending EvidenceItem.

    Returns: (evidence_item, card_type, extraction_confidence, warnings)
    """

    card_type, title, url, download, warnings = identify_card_type(content, hint, input_type)
    eid = f"asst_{card_type}_{uuid.uuid4().hex[:8]}"

    # 提取置信度: URL 类高, 文本类低
    if input_type in ("url", "github", "paper_page", "dataset_page") or content.startswith("http"):
        confidence = 0.80 if warnings == [] else 0.55
    else:
        confidence = 0.40

    raw_input_type_map = {
        "url": "url",
        "github": "github",
        "paper_page": "paper_page",
        "dataset_page": "dataset_page",
        "text": "text",
        "image": "image",
        "pdf": "pdf",
    }

    item_kwargs: dict = dict(
        evidence_id=eid, project_id=project_id,
        evidence_type=card_type, source_mode="assistant_intake",
        title=title, url=url,
        review_status="pending",  # Session 9 §4.4: 全部默认 pending
        workspace_lane=target_lane if target_lane in ("user_preferred", "system_found") else "user_preferred",
        raw_input_type=raw_input_type_map.get(input_type, "url"),
        raw_input_ref=content,
        extraction_confidence=confidence,
        extraction_warnings=warnings,
    )

    if card_type == "dataset" and download:
        item_kwargs["download"] = download

    item = EvidenceItem(**item_kwargs)

    # 写入 evidence pool
    with ev_store._LEDGER_LOCK:
        proj = ev_store._get_project(project_id)
        proj.items[eid] = item

    return item, card_type, confidence, warnings