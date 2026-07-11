"""Re5.X: SourceCatalog — single source of truth for search source availability.

Replaces the pattern where prompts hardcode tool lists that drift from runtime.
All prompts must call `SourceCatalog.allowed_sources(domain)` to get the actual
set of usable tools. This guarantees:
  - prompt source list == runtime allowlist == adapter registry
  - disabled sources never appear in LLM input
  - 'web' is resolved once (currently removed — no adapter exists)
"""
from __future__ import annotations

from typing import Any

from apps.api.app.services.source_policy import get_source_policy

# Master catalog: all sources that have adapters
_ALL_SOURCES: dict[str, dict[str, Any]] = {
    "arxiv":            {"label": "arXiv", "sensitive": False, "alternate": None},
    "openalex":         {"label": "OpenAlex", "sensitive": True, "alternate": "crossref"},
    "crossref":         {"label": "Crossref", "sensitive": False, "alternate": "openalex"},
    "github":           {"label": "GitHub", "sensitive": False, "alternate": None},
    "semantic_scholar": {"label": "Semantic Scholar", "sensitive": True, "alternate": "crossref"},
    "huggingface":      {"label": "HuggingFace", "sensitive": False, "alternate": None},
    "core":             {"label": "CORE", "sensitive": False, "alternate": "crossref"},
    "datacite":         {"label": "DataCite", "sensitive": False, "alternate": None},
    "pubmed":           {"label": "PubMed", "sensitive": False, "alternate": "crossref",
                          "domain_only": {"medical", "biomedical", "health", "clinical",
                                           "bioinformatic", "biological", "medical_ai"}},
}

# Sources removed from catalog (no adapter exists, must not appear in prompts)
_REMOVED_SOURCES = {"web", "scholar", "google"}


class SourceCatalog:
    """Single source of truth for what search sources are available."""

    def __init__(self) -> None:
        self._policy = get_source_policy()

    def allowed_sources(self, domain: str = "") -> list[dict[str, Any]]:
        """Return list of currently-allowed sources for a given domain.

        Each entry: {name, label, sensitive, alternate}
        Disabled sources are excluded entirely.
        """
        domain_lower = (domain or "").lower()
        result: list[dict[str, Any]] = []
        for name, meta in _ALL_SOURCES.items():
            # Domain-gated sources
            domain_only = meta.get("domain_only")
            if domain_only and not any(d in domain_lower for d in domain_only):
                continue
            # Policy-gated
            if not self._policy.is_enabled(name):
                continue
            result.append({
                "name": name,
                "label": meta["label"],
                "sensitive": meta["sensitive"],
                "alternate": meta.get("alternate"),
            })
        return result

    def allowed_source_names(self, domain: str = "") -> list[str]:
        """Return just the source names."""
        return [s["name"] for s in self.allowed_sources(domain)]

    def is_available(self, source: str, domain: str = "") -> bool:
        """Check if a source is available for a domain."""
        return source in self.allowed_source_names(domain)

    def get_alternate(self, source: str) -> str | None:
        """Get the alternate source for a failed/rate-limited source."""
        meta = _ALL_SOURCES.get(source)
        return meta.get("alternate") if meta else None

    def status(self, source: str) -> str:
        """Get the current status of a source."""
        return self._policy.status(source)

    def source_list_for_prompt(self, domain: str = "") -> str:
        """Generate a human-readable source list for LLM prompts."""
        sources = self.allowed_sources(domain)
        lines = []
        for s in sources:
            lines.append(f'- {s["name"]}: 搜{s["label"]}')
        return "\n".join(lines)


_catalog: SourceCatalog | None = None


def get_source_catalog() -> SourceCatalog:
    global _catalog
    if _catalog is None:
        _catalog = SourceCatalog()
    return _catalog


def reset_source_catalog() -> None:
    """Reset catalog (for tests)."""
    global _catalog
    _catalog = None
