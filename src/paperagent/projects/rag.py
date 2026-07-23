from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Iterable

from paperagent.projects.models import SearchHit
from paperagent.projects.repository import SQLiteProjectRepository

_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_+.-]{1,}|[\u4e00-\u9fff]")
_VECTOR_SIZE = 128


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in _TOKEN_PATTERN.findall(text))


def _hashed_vector(tokens: Iterable[str]) -> tuple[float, ...]:
    vector = [0.0] * _VECTOR_SIZE
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:2], "big") % _VECTOR_SIZE
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return tuple(vector)
    return tuple(value / norm for value in vector)


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return max(0.0, sum(a * b for a, b in zip(left, right, strict=True)))


class HybridAcademicRetriever:
    def __init__(self, repository: SQLiteProjectRepository) -> None:
        self.repository = repository

    def search(
        self,
        *,
        project_id: str,
        query: str,
        limit: int = 8,
        paper_ids: Iterable[str] | None = None,
    ) -> tuple[SearchHit, ...]:
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("query must not be empty")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        units = self.repository.list_evidence_units(project_id, paper_ids=paper_ids)
        if not units:
            return ()
        paper_titles = {
            paper.paper_id: paper.title for paper in self.repository.list_latest_papers(project_id)
        }
        query_tokens = _tokens(clean_query)
        query_counts = Counter(query_tokens)
        query_vector = _hashed_vector(query_tokens)
        document_frequency: Counter[str] = Counter()
        unit_tokens: dict[str, tuple[str, ...]] = {}
        for unit in units:
            tokens = _tokens(f"{unit.section or ''} {unit.content}")
            unit_tokens[unit.unit_id] = tokens
            document_frequency.update(set(tokens))

        scored: list[SearchHit] = []
        total_documents = len(units)
        for unit in units:
            tokens = unit_tokens[unit.unit_id]
            lexical = self._lexical_score(
                query_counts=query_counts,
                document_tokens=tokens,
                document_frequency=document_frequency,
                total_documents=total_documents,
            )
            semantic = _cosine(query_vector, _hashed_vector(tokens))
            phrase_bonus = 0.2 if clean_query.casefold() in unit.content.casefold() else 0.0
            keyword_bonus = 0.05 * len(set(query_tokens) & set(unit.keywords))
            score = max(0.0, 0.65 * lexical + 0.35 * semantic + phrase_bonus + keyword_bonus)
            if score <= 0:
                continue
            scored.append(
                SearchHit(
                    unit=unit,
                    score=score,
                    lexical_score=lexical,
                    semantic_score=semantic,
                    paper_title=paper_titles.get(unit.paper_id, unit.paper_id),
                )
            )
        scored.sort(
            key=lambda hit: (
                -hit.score,
                hit.unit.paper_id,
                hit.unit.page or 0,
                hit.unit.paragraph or 0,
                hit.unit.unit_id,
            )
        )
        return tuple(scored[:limit])

    @staticmethod
    def _lexical_score(
        *,
        query_counts: Counter[str],
        document_tokens: tuple[str, ...],
        document_frequency: Counter[str],
        total_documents: int,
    ) -> float:
        if not query_counts or not document_tokens:
            return 0.0
        document_counts = Counter(document_tokens)
        score = 0.0
        for token, query_count in query_counts.items():
            frequency = document_counts[token]
            if frequency == 0:
                continue
            inverse_document_frequency = math.log(
                1.0 + (total_documents + 1) / (document_frequency[token] + 1)
            )
            score += min(frequency, 4) * inverse_document_frequency * query_count
        normalizer = math.sqrt(len(document_tokens)) * max(
            1.0, math.sqrt(sum(query_counts.values()))
        )
        return score / normalizer
