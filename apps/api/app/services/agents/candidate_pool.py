"""CandidatePool — every paper / dataset / repo / baseline the agent has seen.

Re02 Task 4: instead of dropping candidates the LLM didn't pick, collect
everything that came out of tool calls and the structured follow-up
augmentations. The EvidenceReview step then assigns each candidate a
tier; the LLM is NOT responsible for "what counts as a candidate" — only
"how confident I am it's real + which bucket it goes in".

The pool is keyed by a stable id (`stable_id`) so the same paper returned
by arXiv + OpenAlex + Crossref collapses to one row, with sources merged.

This module is intentionally pure (no LLM, no I/O). `add_*` helpers
extract paper/repo/dataset mentions from raw tool output and from
follow-up augmentation lists; tests assert on the resulting shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Candidate:
    """One paper / dataset / repo / baseline candidate the agent has seen."""
    stable_id: str            # dedup key — lower(title or full_name or url)
    candidate_id: str         # display id — random hex
    evidence_type: str        # paper | dataset | repo | survey | unknown
    role_hint: str            # primary display role (latest assigned)
    title: str                # display title / repo full_name / dataset name
    role_hints: list[str] = field(default_factory=list)   # Re03: every role ever assigned
    role_evidence: list[dict] = field(default_factory=list)  # Re03: per-source {source, role_hint, ts, via}
    sources: list[str] = field(default_factory=list)        # which adapters returned it
    year: int | None = None
    venue: str | None = None
    url: str | None = None
    identifier: str | None = None  # DOI / arxiv_id / owner/repo
    description: str | None = None
    quoted_paper_titles: list[str] = field(default_factory=list)
    abstract: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stable_id": self.stable_id,
            "candidate_id": self.candidate_id,
            "evidence_type": self.evidence_type,
            "role_hint": self.role_hint,
            "role_hints": list(self.role_hints),
            "role_evidence": list(self.role_evidence),
            "title": self.title,
            "sources": list(self.sources),
            "year": self.year,
            "venue": self.venue,
            "url": self.url,
            "identifier": self.identifier,
            "description": self.description,
            "quoted_paper_titles": list(self.quoted_paper_titles),
            "abstract": self.abstract,
            "extra": dict(self.extra),
        }


def _norm_title(t: str) -> str:
    return (t or "").strip().lower()


def _norm_repo_key(full_name: str) -> str:
    return (full_name or "").strip().lower().strip("/")


class CandidatePool:
    """Append-only dedup of Candidate. Stable-id based, sources merged."""

    def __init__(self) -> None:
        self.by_stable: dict[str, Candidate] = {}

    @staticmethod
    def _new_id() -> str:
        import uuid
        return f"c-{uuid.uuid4().hex[:8]}"

    def _add_or_merge(self, cand: Candidate) -> bool:
        existing = self.by_stable.get(cand.stable_id)
        if existing is None:
            # Initialize role history on first sight
            cand.role_hints = [cand.role_hint] if cand.role_hint else []
            self.by_stable[cand.stable_id] = cand
            return True
        for s in cand.sources:
            if s not in existing.sources:
                existing.sources.append(s)
        # Fill in any non-empty field that's blank on the existing row
        for fld in ("year", "venue", "url", "identifier", "description", "abstract"):
            if getattr(existing, fld) in (None, "") and getattr(cand, fld):
                setattr(existing, fld, getattr(cand, fld))
        # Quoted paper titles accumulate
        for q in cand.quoted_paper_titles:
            if q and q not in existing.quoted_paper_titles:
                existing.quoted_paper_titles.append(q)
        # Re03: keep ALL roles ever assigned (history, not just latest)
        if cand.role_hint and cand.role_hint not in existing.role_hints:
            existing.role_hints.append(cand.role_hint)
        # Don't overwrite primary role_hint with downstream role assignments;
        # role_hints list carries the full history for the synthesizer to
        # see what buckets this paper was considered for.
        return False

    def add_role_evidence(self, candidate_id: str, *, source: str, role_hint: str, via: str = "") -> None:
        """Re03: record a role-as-source event without changing primary role_hint.

        Use this when downstream code (e.g. synthesizer, low-bar) wants to
        tag a candidate with a bucket without losing the original role.
        """
        cand = next((c for c in self.by_stable.values() if c.candidate_id == candidate_id), None)
        if cand is None:
            return
        cand.role_evidence.append({
            "source": source,
            "role_hint": role_hint,
            "via": via,
        })
        if role_hint and role_hint not in cand.role_hints:
            cand.role_hints.append(role_hint)

    # --- paper entries ---

    def add_paper(
        self,
        *,
        title: str,
        source: str,
        year: int | None = None,
        venue: str | None = None,
        url: str | None = None,
        identifier: str | None = None,
        abstract: str | None = None,
        extra: dict[str, Any] | None = None,
        role_hint: str = "reference",
        evidence_type: str = "paper",
    ) -> Candidate:
        t = (title or "").strip()
        if not t:
            raise ValueError("add_paper: title is empty")
        cand = Candidate(
            stable_id=_norm_title(t),
            candidate_id=self._new_id(),
            evidence_type=evidence_type,
            role_hint=role_hint,
            title=t,
            sources=[source],
            year=year,
            venue=venue,
            url=url,
            identifier=identifier,
            abstract=abstract,
            extra=extra or {},
        )
        self._add_or_merge(cand)
        return cand

    # --- repo entries ---

    def add_repo(
        self,
        *,
        full_name: str,
        source: str = "github",
        url: str | None = None,
        description: str | None = None,
        stars: int | None = None,
        language: str | None = None,
        quoted_paper_titles: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Candidate:
        nm = (full_name or "").strip()
        if not nm:
            raise ValueError("add_repo: full_name is empty")
        cand = Candidate(
            stable_id=_norm_repo_key(nm),
            candidate_id=self._new_id(),
            evidence_type="repo",
            role_hint="repo",
            title=nm,
            sources=[source],
            url=url,
            description=description,
            quoted_paper_titles=list(quoted_paper_titles or []),
            extra={"stars": stars, "language": language, **(extra or {})},
        )
        self._add_or_merge(cand)
        return cand

    # --- dataset entries ---

    def add_dataset(
        self,
        *,
        name: str,
        source: str,
        url: str | None = None,
        scale: str | None = None,
        license: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Candidate:
        nm = (name or "").strip()
        if not nm:
            raise ValueError("add_dataset: name is empty")
        cand = Candidate(
            stable_id=_norm_title(nm),
            candidate_id=self._new_id(),
            evidence_type="dataset",
            role_hint="dataset",
            title=nm,
            sources=[source],
            url=url,
            extra={"scale": scale, "license": license, **(extra or {})},
        )
        self._add_or_merge(cand)
        return cand

    # --- accessors ---

    def all(self) -> list[Candidate]:
        return list(self.by_stable.values())

    def by_evidence_type(self, et: str) -> list[Candidate]:
        return [c for c in self.by_stable.values() if c.evidence_type == et]

    def stats(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for c in self.by_stable.values():
            out[c.evidence_type] = out.get(c.evidence_type, 0) + 1
        return out

    def as_list(self) -> list[dict[str, Any]]:
        return [c.to_dict() for c in self.by_stable.values()]


# --- helpers used by the orchestrator to populate the pool from raw output ---

def collect_papers_from_raw(raw: dict[str, list[dict[str, Any]]], pool: CandidatePool) -> int:
    """Walk raw tool output, add paper-shaped rows. Returns count added (incl. merged)."""
    n = 0
    for adapter in ("arxiv", "openalex", "crossref"):
        for item in raw.get(adapter) or []:
            t = (item.get("title") or "").strip()
            if not t:
                continue
            pool.add_paper(
                title=t,
                source=adapter,
                year=item.get("year") or item.get("publication_year"),
                venue=item.get("venue") or item.get("container_title") or (item.get("publisher") or None),
                url=item.get("url") or item.get("html_url") or item.get("DOI"),
                identifier=item.get("doi") or item.get("arxiv_id") or item.get("openalex_id"),
                abstract=item.get("abstract"),
            )
            n += 1
    return n


def collect_repos_from_raw(raw: dict[str, list[dict[str, Any]]], pool: CandidatePool) -> int:
    """Walk raw GitHub output, add repo rows + any quoted paper titles."""
    from .research_agent import _extract_quoted_titles  # local import to avoid cycle
    n = 0
    for item in raw.get("github") or []:
        nm = (item.get("full_name") or item.get("name") or item.get("repo") or "").strip()
        if not nm:
            continue
        desc = item.get("description") or ""
        quoted = _extract_quoted_titles(desc)
        pool.add_repo(
            full_name=nm,
            source="github",
            url=item.get("html_url") or item.get("url"),
            description=desc,
            stars=item.get("stars") or item.get("stargazers_count"),
            language=item.get("language"),
            quoted_paper_titles=quoted,
        )
        # Surface quoted paper titles as paper candidates too — they came
        # from real GitHub repo descriptions, so they're real evidence.
        for qt in quoted:
            pool.add_paper(
                title=qt,
                source="github",
                role_hint="reference",
                extra={"via_repo": nm},
            )
        n += 1
    return n


def collect_mentioned_datasets(
    raw: dict[str, list[dict[str, Any]]],
    pool: CandidatePool,
    *,
    whitelist: dict[str, tuple[str, ...]] | None = None,
) -> int:
    """Scan raw tool output for canonical dataset names mentioned in titles
    or abstracts. These are not "fabricated" — they were named by other
    papers in the retrieval. Whitelist keeps the scan bounded.
    """
    if not whitelist:
        whitelist = {}
    n = 0
    blob_parts: list[str] = []
    for adapter in ("arxiv", "openalex", "crossref"):
        for item in raw.get(adapter) or []:
            blob_parts.append(str(item.get("title") or ""))
            blob_parts.append(str(item.get("abstract") or ""))
    blob = " ".join(blob_parts).lower()
    for ds_name in {n for names in whitelist.values() for n in names}:
        if ds_name.lower() in blob:
            pool.add_dataset(name=ds_name, source="whitelist_in_mentions")
            n += 1
    return n
