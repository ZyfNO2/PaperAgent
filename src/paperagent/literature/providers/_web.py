from __future__ import annotations

import re
from hashlib import sha256
from urllib.parse import parse_qs, unquote, urlparse

from paperagent.literature.normalize import canonical_arxiv_id, canonical_doi

_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
_ARXIV_RE = re.compile(
    r"(?:arxiv(?:\.org/(?:abs|pdf)/|:))"
    r"(?P<id>\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)",
    re.IGNORECASE,
)
_TRAILING_PUNCTUATION = ".,;:)]}>\"'"


def extract_identifiers(*values: str | None) -> tuple[str | None, str | None]:
    text = " ".join(value for value in values if value)
    doi_match = _DOI_RE.search(text)
    arxiv_match = _ARXIV_RE.search(text)
    doi = canonical_doi(doi_match.group(0).rstrip(_TRAILING_PUNCTUATION)) if doi_match else None
    arxiv_id = canonical_arxiv_id(arxiv_match.group("id")) if arxiv_match else None
    return doi, arxiv_id


def stable_web_record_id(url: str, title: str) -> str:
    raw = f"{url.strip()}|{title.strip()}"
    return "web-" + sha256(raw.encode("utf-8")).hexdigest()[:20]


def unwrap_duckduckgo_url(value: str) -> str:
    value = value.strip()
    parsed = urlparse(value)
    if parsed.netloc.endswith("duckduckgo.com"):
        target = parse_qs(parsed.query).get("uddg")
        if target:
            return unquote(target[0])
    return value
