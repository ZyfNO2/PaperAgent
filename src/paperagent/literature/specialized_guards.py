from __future__ import annotations

import re

from paperagent.literature.query_concepts import named_identifiers

_IDENTITY_INTENT = re.compile(
    r"(?:\boriginal\b|\bintroduced?\b|\bproposed\s+in\b|\bsource\s+paper\b|"
    r"\barchitecture\s+paper\b|\bidentity\b|\bsearching\s+for\b|"
    r"原始论文|首篇论文|提出(?:该|此)?方法|论文身份)",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9\u3400-\u9fff]+")


def _normalized(value: str) -> str:
    return _NON_ALNUM.sub("", value.casefold())


def matches_specialized_candidate_terms(query: str, candidate_text: str) -> bool:
    """Apply only form-based identity constraints.

    Domain and task consistency is handled by the generic concept-alignment layer. This
    guard has no benchmark topic lists: it requires exact named identifiers only when the
    query explicitly asks for the originating or identity paper.
    """

    if _IDENTITY_INTENT.search(query) is None:
        return True
    identifiers = named_identifiers(query)
    if not identifiers:
        return True
    candidate = _normalized(candidate_text)
    return all(identifier in candidate for identifier in identifiers)


__all__ = ["matches_specialized_candidate_terms"]
