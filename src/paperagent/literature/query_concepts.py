from __future__ import annotations

import math
import re

_ASCII_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-_/][A-Za-z0-9]+)*")
_CJK_SEQUENCE = re.compile(r"[\u3400-\u9fff]+")
_NON_ALNUM = re.compile(r"[^a-z0-9\u3400-\u9fff]+")

# Corpus-independent stop words. These are deliberately generic and must not encode
# benchmark domains, model families, datasets, or expected evidence roles.
_GENERIC_RESEARCH_TERMS = {
    "about",
    "analysis",
    "approach",
    "based",
    "benchmark",
    "comparison",
    "data",
    "dataset",
    "deep",
    "evaluation",
    "evidence",
    "experiment",
    "framework",
    "learning",
    "literature",
    "method",
    "model",
    "network",
    "paper",
    "performance",
    "research",
    "result",
    "review",
    "study",
    "survey",
    "system",
    "task",
    "using",
    "classification",
    "classifier",
    "detection",
    "detector",
    "prediction",
    "recognition",
    "segmentation",
    "optimization",
    "研究",
    "方法",
    "模型",
    "论文",
    "数据",
    "实验",
    "性能",
    "系统",
    "任务",
}


def _normalize_token(value: str) -> str:
    return _NON_ALNUM.sub("", value.casefold())


def _cjk_terms(value: str) -> set[str]:
    output: set[str] = set()
    for sequence in _CJK_SEQUENCE.findall(value):
        if sequence in _GENERIC_RESEARCH_TERMS:
            continue
        output.add(sequence)
        if len(sequence) >= 3:
            output.update(sequence[index : index + 2] for index in range(len(sequence) - 1))
    return output


def concept_tokens(value: str) -> frozenset[str]:
    """Extract domain-bearing lexical concepts without a task-specific ontology."""

    output = {
        normalized
        for raw in _ASCII_TOKEN.findall(value)
        if (normalized := _normalize_token(raw))
        and len(normalized) >= 3
        and normalized not in _GENERIC_RESEARCH_TERMS
    }
    output.update(_cjk_terms(value))
    return frozenset(output)


def named_identifiers(value: str) -> tuple[str, ...]:
    """Return model/dataset/code-like identifiers using form, not known-name lists."""

    identifiers: list[str] = []
    for raw in _ASCII_TOKEN.findall(value):
        normalized = _normalize_token(raw)
        if not normalized or normalized in _GENERIC_RESEARCH_TERMS:
            continue
        looks_named = (
            any(character.isdigit() for character in raw)
            or "-" in raw
            or "_" in raw
            or "/" in raw
            or (len(raw) >= 3 and any(character.isupper() for character in raw[1:]))
            or (2 <= len(raw) <= 8 and raw.isupper())
        )
        if looks_named and normalized not in identifiers:
            identifiers.append(normalized)
    return tuple(identifiers)


def required_candidate_term_groups(query: str) -> tuple[tuple[str, ...], ...]:
    """Expose generic query concepts as auditable singleton groups.

    This compatibility API intentionally contains no domain synonym tables. Matching uses
    aggregate coverage rather than requiring every group, so unseen domains fail safely
    without receiving benchmark-specific treatment.
    """

    return tuple((token,) for token in sorted(concept_tokens(query)))


def concept_alignment_score(query: str, candidate_text: str) -> float:
    query_terms = concept_tokens(query)
    if not query_terms:
        return 1.0
    candidate_terms = concept_tokens(candidate_text)
    if not candidate_terms:
        return 0.0
    return len(query_terms & candidate_terms) / len(query_terms)


def matches_required_candidate_terms(query: str, candidate_text: str) -> bool:
    query_terms = concept_tokens(query)
    if not query_terms:
        return True
    matched = len(query_terms & concept_tokens(candidate_text))
    required = (
        len(query_terms) if len(query_terms) <= 2 else max(2, math.ceil(len(query_terms) * 0.4))
    )
    return matched >= required


__all__ = [
    "concept_alignment_score",
    "concept_tokens",
    "matches_required_candidate_terms",
    "named_identifiers",
    "required_candidate_term_groups",
]
