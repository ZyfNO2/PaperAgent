"""literature_role_classifier — Re03 SOP §3.5: method/task/object 3-axis
role classification.

Inputs:
  candidate      — dict with title + abstract
  parsed_topic   — dict with method_terms / task_terms / object_terms

Output (per Re03 SOP §3.5):
  {
    "method_match":  "exact | adjacent | none",
    "task_match":    "exact | adjacent | none",
    "object_match":  "exact | adjacent | none",
    "role":          "baseline | parallel | module | reference | dataset | repo | rejected",
    "borrow_value":  "可复现基础 | 模块借鉴 | 数据集借鉴 | 方法论借鉴 | 任务同形 | 跨域无价值",
    "reason":        "≤ 50 words"
  }

Ponytail: ~120 lines, no LLM, no network. Token-level match against
the parsed_topic axes. Returns the same verdict regardless of LLM mood
so the synthesizer can build paper_groups with explicit method/task
match signals.
"""

from __future__ import annotations

import re
from typing import Any


_TOK = re.compile(r"[a-z0-9一-鿿]{2,}")


def _tokens(s: str) -> set[str]:
    return {t.lower() for t in _TOK.findall(s or "")}


def _norm_terms(terms: list[str]) -> set[str]:
    out: set[str] = set()
    for t in terms or []:
        if not t:
            continue
        for w in _TOK.findall(t):
            out.add(w.lower())
    return out


def _match_axis(axis_tokens: set[str], haystack: set[str]) -> str:
    if not axis_tokens:
        return "none"
    overlap = axis_tokens & haystack
    if not overlap:
        return "none"
    ratio = len(overlap) / max(1, len(axis_tokens))
    if ratio >= 0.6:
        return "exact"
    return "adjacent"


def classify_literature_role(
    candidate: dict[str, Any],
    parsed_topic: dict[str, Any],
) -> dict[str, Any]:
    method_tokens = _norm_terms(parsed_topic.get("method_terms") or [])
    task_tokens = _norm_terms(parsed_topic.get("task_terms") or [])
    object_tokens = _norm_terms(parsed_topic.get("object_terms") or [])
    haystack = _tokens(
        (candidate.get("title") or "") + " " + (candidate.get("abstract") or "")
    )
    method_match = _match_axis(method_tokens, haystack)
    task_match = _match_axis(task_tokens, haystack)
    object_match = _match_axis(object_tokens, haystack)

    et_raw = (candidate.get("evidence_type") or "").strip().lower()
    if et_raw in {"repo", "dataset"}:
        et = et_raw
    elif "title" in candidate or et_raw in {"", "paper", "survey", "unknown"}:
        et = "paper"
    else:
        et = et_raw or "paper"

    if et == "repo":
        return {
            "method_match": method_match, "task_match": task_match, "object_match": object_match,
            "role": "repo", "borrow_value": "实现/部署借鉴",
            "reason": "GitHub repo; method match shows implementation feasibility",
        }
    if et == "dataset":
        return {
            "method_match": method_match, "task_match": task_match, "object_match": object_match,
            "role": "dataset", "borrow_value": "数据集借鉴",
            "reason": "Dataset; object/task match shows it's the right benchmark for this task",
        }

    # Paper classification
    if method_match == "none" and task_match == "none" and object_match == "none":
        role = "rejected"
        borrow = "跨域无价值"
        reason = "No overlap on method / task / object; likely off-domain."
    elif method_match == "exact" and task_match == "exact":
        role = "baseline"
        borrow = "可复现基础"
        reason = "Method+task both exact; candidate is a reproducible baseline for the topic."
    elif method_match in ("exact", "adjacent") and task_match in ("exact", "adjacent"):
        if method_match == "exact" and task_match == "adjacent":
            role = "parallel"
            borrow = "方法论借鉴"
            reason = "Method matches; task is adjacent — useful for module / method transfer."
        elif method_match == "adjacent" and task_match == "exact":
            role = "parallel"
            borrow = "任务同形"
            reason = "Same task; adjacent method — useful as a parallel comparison."
        else:
            role = "parallel"
            borrow = "方法论借鉴"
            reason = "Method and task both at least adjacent."
    elif method_match == "adjacent" and task_match == "none":
        role = "module"
        borrow = "模块借鉴"
        reason = "Method adjacent; not directly about this task — can borrow a module."
    elif task_match == "adjacent" and method_match == "none":
        role = "reference"
        borrow = "任务同形"
        reason = "Task adjacent; not this method — useful for related-task context."
    else:
        role = "reference"
        borrow = "方法论借鉴"
        reason = "Only object overlap; treat as background reference."

    return {
        "method_match": method_match,
        "task_match": task_match,
        "object_match": object_match,
        "role": role,
        "borrow_value": borrow,
        "reason": reason,
    }
