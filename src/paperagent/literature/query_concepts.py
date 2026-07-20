from __future__ import annotations

import math
import re

_ASCII_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-_/][A-Za-z0-9]+)*")
_CJK_SEQUENCE = re.compile(r"[\u3400-\u9fff]+")
_NON_ALNUM = re.compile(r"[^a-z0-9\u3400-\u9fff]+")

# Corpus-independent stop words. These are generic research nouns, not model,
# dataset, language, or benchmark-domain vocabularies.
_GENERIC_RESEARCH_TERMS = {
    "about",
    "analysis",
    "approach",
    "based",
    "benchmark",
    "comparison",
    "data",
    "dataset",
    "datasets",
    "deep",
    "evaluation",
    "evidence",
    "experiment",
    "framework",
    "learning",
    "literature",
    "method",
    "methods",
    "metric",
    "metrics",
    "model",
    "network",
    "paper",
    "papers",
    "performance",
    "research",
    "result",
    "results",
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

# Generic method, evidence-role, and operation words are excluded only when
# determining task anchors. They remain available in ``concept_tokens`` for
# diagnostics. This prevents a shared method name from making a cross-domain
# paper look relevant while avoiding a domain-specific ontology.
_NON_TASK_TERMS = {
    "alternative",
    "architecture",
    "attention",
    "augmentation",
    "baseline",
    "comparative",
    "contrastive",
    "distillation",
    "efficiency",
    "enhancement",
    "failure",
    "feature",
    "fewshot",
    "finetuning",
    "forecasting",
    "fusion",
    "graph",
    "identification",
    "inference",
    "intervention",
    "lightweight",
    "limitation",
    "limitations",
    "longcontext",
    "mapping",
    "mechanism",
    "metaanalysis",
    "metalearning",
    "modeling",
    "modelling",
    "monitoring",
    "negative",
    "neural",
    "parallel",
    "postprocessing",
    "prediction",
    "prototypical",
    "prototype",
    "pruning",
    "quantization",
    "realtime",
    "reproducible",
    "retrieval",
    "risk",
    "simulation",
    "strong",
    "supervised",
    "surrogate",
    "transformer",
    "uncertainty",
    "unsupervised",
}


def _normalize_token(value: str) -> str:
    return _NON_ALNUM.sub("", value.casefold())


def _looks_like_identifier(raw: str) -> bool:
    return bool(
        any(character.isdigit() for character in raw)
        or (len(raw) >= 3 and any(character.isupper() for character in raw[1:]))
        or (2 <= len(raw) <= 8 and raw.isupper())
    )


def _cjk_terms(value: str) -> list[str]:
    output: list[str] = []
    for sequence in _CJK_SEQUENCE.findall(value):
        if sequence in _GENERIC_RESEARCH_TERMS:
            continue
        terms = (
            [sequence]
            if len(sequence) <= 2
            else [sequence[index : index + 2] for index in range(len(sequence) - 1)]
        )
        for term in terms:
            if term not in _GENERIC_RESEARCH_TERMS and term not in output:
                output.append(term)
    return output


def _ascii_terms(value: str, *, task_only: bool) -> list[str]:
    output: list[str] = []
    for raw in _ASCII_TOKEN.findall(value):
        normalized = _normalize_token(raw)
        if not normalized or len(normalized) < 3:
            continue
        if normalized in _GENERIC_RESEARCH_TERMS:
            continue
        if task_only and (_looks_like_identifier(raw) or normalized in _NON_TASK_TERMS):
            continue
        if normalized not in output:
            output.append(normalized)
    return output


def concept_tokens(value: str) -> frozenset[str]:
    """Extract lexical concepts without a task-specific ontology."""

    return frozenset((*_ascii_terms(value, task_only=False), *_cjk_terms(value)))


def _task_concepts(value: str) -> tuple[str, ...]:
    return tuple((*_ascii_terms(value, task_only=True), *_cjk_terms(value)))


def named_identifiers(value: str) -> tuple[str, ...]:
    """Return model/dataset/code-like identifiers using form, not known-name lists."""

    identifiers: list[str] = []
    for raw in _ASCII_TOKEN.findall(value):
        normalized = _normalize_token(raw)
        if (
            normalized
            and normalized not in _GENERIC_RESEARCH_TERMS
            and _looks_like_identifier(raw)
            and normalized not in identifiers
        ):
            identifiers.append(normalized)
    return tuple(identifiers)


def required_candidate_term_groups(query: str) -> tuple[tuple[str, ...], ...]:
    """Expose generic task anchors as auditable singleton groups."""

    terms = _task_concepts(query) or tuple(sorted(concept_tokens(query)))
    return tuple((token,) for token in terms)


def concept_alignment_score(query: str, candidate_text: str) -> float:
    query_terms = set(_task_concepts(query)) or set(concept_tokens(query))
    if not query_terms:
        return 1.0
    candidate_terms = concept_tokens(candidate_text)
    if not candidate_terms:
        return 0.0
    return len(query_terms & candidate_terms) / len(query_terms)


def matches_required_candidate_terms(query: str, candidate_text: str) -> bool:
    """Require broad coverage of task anchors, not merely shared method words.

    The rule is corpus-independent: task anchors are whatever domain-bearing words
    the query itself contains after generic research, method, and role terms are
    removed. This blocks model-name and technique-only false positives without
    embedding benchmark topic lists in production code.
    """

    query_terms = set(_task_concepts(query)) or set(concept_tokens(query))
    if not query_terms:
        return True
    candidate_terms = concept_tokens(candidate_text)
    if not candidate_terms:
        return False
    matched = len(query_terms & candidate_terms)
    required = 1 if len(query_terms) == 1 else max(2, math.ceil(len(query_terms) * 0.6))
    return matched >= required


__all__ = [
    "concept_alignment_score",
    "concept_tokens",
    "matches_required_candidate_terms",
    "named_identifiers",
    "required_candidate_term_groups",
]
