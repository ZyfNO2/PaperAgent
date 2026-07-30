"""Multi-query decomposition planner for Academic RAG."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from paperagent.academic.contracts import (
    AcademicChannel,
    AcademicObjectType,
)

_DOI = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b", re.IGNORECASE)
_ARXIV = re.compile(r"\b(arXiv:\d{4}\.\d{4,5})\b", re.IGNORECASE)

_COMPARISON_KEYWORDS = re.compile(
    r"\b(compare|comparison|对比|比较|versus|vs\.?|difference)\b", re.IGNORECASE
)
_BASELINE_KEYWORDS = re.compile(
    r"\b(baseline|基线|state.of.the.art|sota|bench ?mark)\b", re.IGNORECASE
)
_MODULE_KEYWORDS = re.compile(
    r"\b(module|模块|component|组件|architecture|架构|backbone)\b", re.IGNORECASE
)
_IDENTITY_KEYWORDS = re.compile(
    r"\b(who|what paper|which paper|哪篇|作者|author|cite|引用)\b", re.IGNORECASE
)
_FIGURE_KEYWORDS = re.compile(r"\b(figure|diagram|architecture diagram)\b|图", re.IGNORECASE)
_TABLE_KEYWORDS = re.compile(r"\b(table|tabular)\b|表格", re.IGNORECASE)
_EQUATION_KEYWORDS = re.compile(r"\b(equation|formula)\b|公式", re.IGNORECASE)


@dataclass(frozen=True)
class AcademicSubQuery:
    sub_query_id: str
    purpose: str
    rewritten_query: str
    channels: tuple[AcademicChannel, ...] = ("lexical", "dense")
    object_types: tuple[AcademicObjectType, ...] = ()
    paper_ids: tuple[str, ...] = ()
    corrective_reason: str | None = None
    section_scope: tuple[str, ...] = ()
    result_budget: int = 10
    character_budget: int = 12_000
    token_budget: int = 3_000
    stop_condition: str = "sufficient_or_budget_exhausted"
    identity_constraints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 1 <= self.result_budget <= 100:
            raise ValueError("result_budget must be in [1, 100]")
        if self.character_budget < 1 or self.token_budget < 1:
            raise ValueError("character and token budgets must be positive")
        folded = self.rewritten_query.casefold()
        if any(identity.casefold() not in folded for identity in self.identity_constraints):
            raise ValueError("rewrite lost an identity constraint")


@dataclass(frozen=True)
class AcademicQueryDecomposition:
    original_question: str
    sub_queries: tuple[AcademicSubQuery, ...]
    strategy: str = "parallel"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AcademicQueryDecomposition:
        return cls(
            original_question=str(value["original_question"]),
            sub_queries=tuple(AcademicSubQuery(**item) for item in value["sub_queries"]),
            strategy=str(value.get("strategy", "parallel")),
        )


def decompose_question(
    question: str,
    *,
    paper_ids: tuple[str, ...] = (),
) -> AcademicQueryDecomposition:
    if not question.strip():
        raise ValueError("question must not be empty")

    dois = _DOI.findall(question)
    arxivs = _ARXIV.findall(question)
    identifiers = tuple(dois) + tuple(arxivs)

    if identifiers:
        return AcademicQueryDecomposition(
            original_question=question,
            sub_queries=(
                AcademicSubQuery(
                    sub_query_id="sq-identity",
                    purpose="identity",
                    rewritten_query=question,
                    channels=("exact", "lexical"),
                    paper_ids=paper_ids,
                    corrective_reason=None,
                    identity_constraints=identifiers,
                ),
            ),
            strategy="parallel",
        )

    object_routes: tuple[
        tuple[
            re.Pattern[str],
            str,
            tuple[AcademicChannel, ...],
            tuple[AcademicObjectType, ...],
        ],
        ...,
    ] = (
        (
            _FIGURE_KEYWORDS,
            "figure",
            ("visual", "lexical", "dense"),
            ("figure", "caption", "page"),
        ),
        (
            _TABLE_KEYWORDS,
            "table",
            ("exact", "lexical", "dense", "visual"),
            ("table", "table_cell", "caption", "page"),
        ),
        (
            _EQUATION_KEYWORDS,
            "equation",
            ("lexical", "dense", "visual"),
            ("equation", "paragraph", "page"),
        ),
    )
    for pattern, purpose, channels, object_types in object_routes:
        if pattern.search(question):
            return AcademicQueryDecomposition(
                original_question=question,
                sub_queries=(
                    AcademicSubQuery(
                        sub_query_id=f"sq-{purpose}",
                        purpose=purpose,
                        rewritten_query=question,
                        channels=channels,
                        object_types=object_types,
                        paper_ids=paper_ids,
                        corrective_reason=(
                            f"{purpose} evidence requires grounded object retrieval"
                        ),
                        identity_constraints=identifiers,
                    ),
                ),
                strategy="parallel",
            )

    if _COMPARISON_KEYWORDS.search(question) and len(paper_ids) >= 2:
        subs = []
        for i, pid in enumerate(paper_ids):
            subs.append(
                AcademicSubQuery(
                    sub_query_id=f"sq-paper-{i}",
                    purpose="per_paper_identity",
                    rewritten_query=question,
                    channels=("lexical", "dense"),
                    object_types=("section", "paragraph", "table"),
                    paper_ids=(pid,),
                    corrective_reason=f"extract evidence from paper {pid} for comparison",
                    identity_constraints=identifiers,
                )
            )
        subs.append(
            AcademicSubQuery(
                sub_query_id="sq-cross",
                purpose="cross_paper_comparison",
                rewritten_query=question,
                channels=("lexical", "dense"),
                object_types=("table", "paragraph", "equation"),
                paper_ids=paper_ids,
                corrective_reason="cross-paper comparison requires joint retrieval",
                identity_constraints=identifiers,
            )
        )
        return AcademicQueryDecomposition(
            original_question=question,
            sub_queries=tuple(subs),
            strategy="fan_out_by_paper",
        )

    if _BASELINE_KEYWORDS.search(question):
        return AcademicQueryDecomposition(
            original_question=question,
            sub_queries=(
                AcademicSubQuery(
                    sub_query_id="sq-baseline",
                    purpose="baseline_identity",
                    rewritten_query=question,
                    channels=("lexical", "dense", "exact"),
                    object_types=("section", "paragraph", "table", "equation"),
                    paper_ids=paper_ids,
                    corrective_reason="baseline selection requires method and metric evidence",
                    identity_constraints=identifiers,
                ),
            ),
            strategy="parallel",
        )

    if _MODULE_KEYWORDS.search(question):
        return AcademicQueryDecomposition(
            original_question=question,
            sub_queries=(
                AcademicSubQuery(
                    sub_query_id="sq-module",
                    purpose="module_capability",
                    rewritten_query=question,
                    channels=("lexical", "dense"),
                    object_types=("section", "paragraph", "figure", "caption"),
                    paper_ids=paper_ids,
                    corrective_reason="module extraction requires architecture and figure evidence",
                    identity_constraints=identifiers,
                ),
            ),
            strategy="parallel",
        )

    return AcademicQueryDecomposition(
        original_question=question,
        sub_queries=(
            AcademicSubQuery(
                sub_query_id="sq-method",
                purpose="method",
                rewritten_query=question,
                channels=("lexical", "dense"),
                object_types=("section", "paragraph", "equation", "table"),
                paper_ids=paper_ids,
                corrective_reason=None,
                identity_constraints=identifiers,
            ),
        ),
        strategy="parallel",
    )
