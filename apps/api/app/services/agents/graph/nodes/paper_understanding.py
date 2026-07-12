"""Re8.0 WP2: Paper Understanding — PDF section/table parsing + LLM extraction.

This module fills the WP2 gap left by ``seed_resolver_node``: when a seed
paper has a local PDF (or downloaded fulltext), we parse it into sections,
extract tables, then call the LLM to fill ``method_summary``,
``dataset_and_metrics``, ``reproduction_environment``, and ``limitations``
on the ``SeedPaperCard``.

Section detection uses PyMuPDF (fitz) font-size analysis — headings are
typically 1-3pt larger than body text. Table extraction uses pdfplumber.
Both are deterministic; the LLM is only used for semantic field extraction.

The node is a no-op when no seed card has fulltext available, so existing
``topic_only`` callers see no behaviour change.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from apps.api.app.services.agents.graph.re80_schema import (
    make_evidence_gap,
    validate_evidence_gap,
)
from apps.api.app.services.agents.graph.state import ResearchState
from ._util import emit_trace as _emit

logger = logging.getLogger(__name__)


# ── Canonical section names ─────────────────────────────────────────────────

_SECTION_ALIASES: list[tuple[str, re.Pattern[str]]] = [
    ("abstract",          re.compile(r"^abstract\b", re.I)),
    ("introduction",      re.compile(r"^(1\.?\s*)?introduction\b", re.I)),
    ("related_work",      re.compile(r"^(related\s+work|background|preliminar)", re.I)),
    ("method",            re.compile(r"^(\d+\.?\s*)?(method|approach|model|architecture|framework|methodology|proposed)", re.I)),
    ("experiments",       re.compile(r"^(\d+\.?\s*)?(experiment|evaluation|result|ablation)", re.I)),
    ("conclusion",        re.compile(r"^(\d+\.?\s*)?conclusion", re.I)),
    ("limitations",       re.compile(r"limitation", re.I)),
    ("appendix",          re.compile(r"^appendix", re.I)),
    ("references",        re.compile(r"^reference", re.I)),
]


def _canonical_section_name(heading: str) -> str | None:
    """Map a raw heading to a canonical section name, or None if unknown."""
    h = heading.strip()
    for canon, pat in _SECTION_ALIASES:
        if pat.search(h):
            return canon
    return None


# ── PDF section parsing (PyMuPDF) ───────────────────────────────────────────

def extract_sections(pdf_bytes: bytes) -> dict[str, str]:
    """Extract text grouped by section from a PDF.

    Uses PyMuPDF font-size analysis to detect headings. Returns a dict
    mapping canonical section names (``abstract``, ``introduction``, ...)
    to their body text. Sections without a recognised heading are grouped
    under ``"_unknown"``.

    Falls back to pypdf flat extraction if PyMuPDF is unavailable or fails.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF not available; falling back to flat extraction")
        return _flat_extract(pdf_bytes)

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        logger.warning("PyMuPDF open failed: %s; falling back to flat", exc)
        return _flat_extract(pdf_bytes)

    # Pass 1: collect all text spans with font sizes + y position.
    # PyMuPDF may return blocks out of reading order; we sort by y to
    # reconstruct top-to-bottom reading sequence.
    all_spans: list[tuple[str, float, float]] = []  # (text, size, y)
    for page in doc:
        d = page.get_text("dict")
        for block in d.get("blocks", []):
            if block.get("type") != 0:  # 0 = text block
                continue
            for line in block.get("lines", []):
                line_bbox = line.get("bbox") or [0, 0, 0, 0]
                y = line_bbox[1] if len(line_bbox) >= 2 else 0.0
                for span in line.get("spans", []):
                    text = (span.get("text") or "").strip()
                    if not text:
                        continue
                    size = round(span.get("size", 12.0), 1)
                    all_spans.append((text, size, y))

    doc.close()

    if not all_spans:
        return _flat_extract(pdf_bytes)

    # Sort by y coordinate (top-to-bottom reading order)
    all_spans.sort(key=lambda t: t[2])

    # Compute dominant body font size (mode of all sizes).
    # On tie, prefer the smaller size — body text is typically smaller than
    # headings, and choosing the larger size would mask all headings.
    size_counts: dict[float, int] = {}
    for _, sz, _ in all_spans:
        size_counts[sz] = size_counts.get(sz, 0) + 1
    max_count = max(size_counts.values())
    body_size = min(sz for sz, cnt in size_counts.items() if cnt == max_count)

    # Pass 2: identify headings (font size > body_size + 0.5) and group text
    sections: dict[str, list[str]] = {}
    current_section = "_unknown"

    for text, sz, _ in all_spans:
        is_heading = sz > body_size + 0.5 and len(text) < 200
        if is_heading:
            canon = _canonical_section_name(text)
            if canon:
                current_section = canon
                sections.setdefault(current_section, [])
                continue
            # Unrecognised heading — start a new unknown group only if
            # the text looks like a numbered section header
            if re.match(r"^\d+\.?\s+\S", text):
                current_section = "_unknown"
                sections.setdefault(current_section, [])
                continue
        sections.setdefault(current_section, []).append(text)

    # Join span fragments into section text
    result: dict[str, str] = {}
    for name, fragments in sections.items():
        text = " ".join(fragments)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            result[name] = text

    return result


def _flat_extract(pdf_bytes: bytes) -> dict[str, str]:
    """Fallback: pypdf flat extraction (no section detection)."""
    from apps.api.app.services.rag.pdf_extractor import extract_text
    try:
        text = extract_text(pdf_bytes)
        return {"_fulltext": text} if text else {}
    except Exception as exc:
        logger.warning("flat extraction also failed: %s", exc)
        return {}


# ── PDF table extraction (pdfplumber) ───────────────────────────────────────

def extract_tables(pdf_bytes: bytes, *, max_tables: int = 10) -> list[dict[str, Any]]:
    """Extract tables from PDF using pdfplumber.

    Returns a list of ``{"page": int, "rows": list[list[str]]}`` dicts.
    Empty tables and tables with < 2 rows are skipped.
    """
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not available; skipping table extraction")
        return []

    tables: list[dict[str, Any]] = []
    try:
        with pdfplumber.open(pdf_bytes) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                if len(tables) >= max_tables:
                    break
                try:
                    raw_tables = page.extract_tables() or []
                except Exception:
                    continue
                for tbl in raw_tables:
                    if not tbl or len(tbl) < 2:
                        continue
                    # Clean cell text
                    rows = []
                    for row in tbl:
                        cleaned = [
                            (cell or "").strip().replace("\n", " ") for cell in row
                        ]
                        if any(cleaned):
                            rows.append(cleaned)
                    if len(rows) >= 2:
                        tables.append({"page": page_idx + 1, "rows": rows})
                        if len(tables) >= max_tables:
                            break
    except Exception as exc:
        logger.warning("pdfplumber table extraction failed: %s", exc)

    return tables


# ── LLM-based semantic extraction ───────────────────────────────────────────

_UNDERSTANDING_SYSTEM = (
    "You are a research paper analysis assistant. Extract structured "
    "information from the provided paper sections. Return ONLY a valid "
    "JSON object — no prose, no markdown fences."
)

_UNDERSTANDING_USER_TEMPLATE = """Analyze the following paper sections and extract structured information.

Paper title: {title}

Sections:
{sections_text}

Tables (first {n_tables} tables shown):
{tables_text}

[OUTPUT CONTRACT] After your analysis, your ENTIRE final message must be
exactly ONE valid JSON object with these fields:
{{
  "task_definition": "1-2 sentence description of the task/problem",
  "method_summary": "3-5 sentence summary of the proposed method/architecture",
  "dataset_and_metrics": {{
    "datasets": ["dataset names"],
    "metrics": ["metric names with values if available, e.g. mAP=0.85"]
  }},
  "reproduction_environment": {{
    "framework": "e.g. PyTorch 2.0",
    "hardware": "e.g. 4x RTX 3090",
    "hyperparameters": "key training params: lr, batch_size, epochs"
  }},
  "limitations": ["list of limitations stated or implied"]
}}

If a field cannot be determined from the text, use null for strings/objects
or [] for arrays. Do not fabricate information."""


def _format_sections_for_prompt(sections: dict[str, str]) -> str:
    """Format sections dict into a readable string for the LLM prompt."""
    parts: list[str] = []
    for name, text in sections.items():
        # Truncate very long sections to fit token budget
        max_len = 3000
        truncated = text[:max_len]
        if len(text) > max_len:
            truncated += " [...] [truncated]"
        parts.append(f"[{name}]\n{truncated}")
    return "\n\n".join(parts) if parts else "(no sections extracted)"


def _format_tables_for_prompt(tables: list[dict[str, Any]]) -> str:
    """Format tables into a readable string for the LLM prompt."""
    if not tables:
        return "(no tables extracted)"
    parts: list[str] = []
    for i, tbl in enumerate(tables[:5]):  # Limit to first 5 tables
        rows = tbl.get("rows", [])
        if not rows:
            continue
        lines = [f"Table {i+1} (page {tbl.get('page', '?')}):"]
        for row in rows[:8]:  # Limit to 8 rows per table
            lines.append(" | ".join(row))
        if len(rows) > 8:
            lines.append(f"  ... ({len(rows) - 8} more rows)")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _call_understanding_llm(
    title: str,
    sections: dict[str, str],
    tables: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Call the LLM to extract structured paper understanding.

    Returns the parsed JSON dict or None on failure.
    """
    user_prompt = _UNDERSTANDING_USER_TEMPLATE.format(
        title=title or "(unknown)",
        sections_text=_format_sections_for_prompt(sections),
        n_tables=len(tables),
        tables_text=_format_tables_for_prompt(tables),
    )

    try:
        from apps.api.app.services import llm_router
        out = llm_router.call_json(
            user_prompt,
            system=_UNDERSTANDING_SYSTEM,
            profile="fast_json",
            max_tokens=2000,
            timeout=60,
            expected="dict",
            schema_hint='JSON object with keys: task_definition (str|null), method_summary (str|null), dataset_and_metrics (object|null), reproduction_environment (object|null), limitations (array|null)',
        )
        if isinstance(out, dict):
            return out
        logger.warning("paper understanding LLM returned non-dict: %s", type(out))
        return None
    except Exception as exc:
        logger.warning("paper understanding LLM call failed: %s", exc)
        return None


# ── Evidence Gap generation ─────────────────────────────────────────────────

_GAP_QUESTIONS = {
    "method_summary": "What is the core method/architecture of this seed paper?",
    "dataset_and_metrics": "What datasets and metrics are used for evaluation?",
    "reproduction_environment": "What framework, hardware, and hyperparameters are needed to reproduce this paper?",
    "limitations": "What are the stated or implied limitations of this method?",
}


def _generate_gaps_for_missing_fields(
    card: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate EvidenceGap objects for unfilled WP2 fields."""
    gaps: list[dict[str, Any]] = []
    for field, question in _GAP_QUESTIONS.items():
        val = card.get(field)
        is_empty = (
            val is None
            or (isinstance(val, str) and not val.strip())
            or (isinstance(val, dict) and not val)
            or (isinstance(val, list) and not val)
        )
        if is_empty:
            gap = make_evidence_gap(
                gap_id=f"gap-{card['seed_id']}-{field}",
                question=question,
                gap_type="mechanism" if field == "method_summary" else "environment",
                why_needed=f"Field '{field}' could not be extracted from the PDF; "
                           f"downstream reasoning needs this to assess compatibility.",
                related_claim_ids=[card["seed_id"]],
                success_condition=f"Paper understanding fills '{field}' with non-null value",
            )
            errs = validate_evidence_gap(gap)
            if not errs:
                gaps.append(gap)
    return gaps


# ── LangGraph node ──────────────────────────────────────────────────────────

def paper_understanding_node(state: ResearchState) -> dict[str, Any]:
    """Re8.0 WP2: parse PDFs and fill SeedPaperCard understanding fields.

    For each seed card with a local PDF (``raw_input.pdf_path`` or
    ``raw_input.pdf_bytes``), this node:
      1. Extracts sections via PyMuPDF
      2. Extracts tables via pdfplumber
      3. Calls the LLM to fill method/dataset/metric/limitation/env fields
      4. Generates EvidenceGap objects for fields that remain empty

    No-op when no seed card has a PDF, so ``topic_only`` callers are
    unaffected.
    """
    t0 = time.time()
    entry_mode = state.get("entry_mode", "topic_only")
    seed_cards: list[dict[str, Any]] = list(state.get("seed_cards") or [])

    if entry_mode == "topic_only" or not seed_cards:
        trace = _emit(
            "paper_understanding", t0,
            {"entry_mode": entry_mode, "n_seed_cards": len(seed_cards)},
            {"skipped": True, "reason": "topic_only or no seed_cards"},
            [], "local", [],
            state_keys=["seed_cards", "evidence_gaps", "trace_events"],
        )
        return {"trace_events": [trace]}

    # Filter to cards with PDF input
    pdf_cards = [
        c for c in seed_cards
        if c.get("input_form") == "pdf"
        or (c.get("raw_input", {}).get("pdf_path"))
        or (c.get("raw_input", {}).get("pdf_bytes"))
    ]

    if not pdf_cards:
        trace = _emit(
            "paper_understanding", t0,
            {"entry_mode": entry_mode, "n_seed_cards": len(seed_cards),
             "n_pdf_cards": 0},
            {"skipped": True, "reason": "no PDF seed cards"},
            [], "local", [],
            state_keys=["seed_cards", "evidence_gaps", "trace_events"],
        )
        return {"trace_events": [trace]}

    updated_cards: list[dict[str, Any]] = []
    all_gaps: list[dict[str, Any]] = []
    n_parsed = 0
    n_failed = 0

    for card in seed_cards:
        raw = card.get("raw_input") or {}
        pdf_path = raw.get("pdf_path")
        pdf_bytes = raw.get("pdf_bytes")

        # Read PDF bytes
        if pdf_bytes and isinstance(pdf_bytes, (bytes, bytearray)):
            pass  # already have bytes
        elif pdf_path:
            try:
                from pathlib import Path
                pdf_bytes = Path(pdf_path).read_bytes()
            except Exception as exc:
                logger.warning("failed to read PDF %s: %s", pdf_path, exc)
                card["fulltext_status"] = "parse_failed"
                card["repair_hint"] = f"PDF read error: {exc}"
                updated_cards.append(card)
                all_gaps.extend(_generate_gaps_for_missing_fields(card))
                n_failed += 1
                continue
        else:
            # No PDF for this card — skip
            updated_cards.append(card)
            continue

        # Extract sections + tables
        try:
            sections = extract_sections(pdf_bytes)
            tables = extract_tables(pdf_bytes)
        except Exception as exc:
            logger.warning("PDF parsing failed for %s: %s", card.get("seed_id"), exc)
            card["fulltext_status"] = "parse_failed"
            card["repair_hint"] = f"PDF parse error: {exc}"
            updated_cards.append(card)
            all_gaps.extend(_generate_gaps_for_missing_fields(card))
            n_failed += 1
            continue

        if not sections:
            card["fulltext_status"] = "parse_failed"
            card["repair_hint"] = "no text extracted from PDF"
            updated_cards.append(card)
            all_gaps.extend(_generate_gaps_for_missing_fields(card))
            n_failed += 1
            continue

        # LLM extraction
        title = card.get("resolved_title") or raw.get("title") or ""
        extracted = _call_understanding_llm(title, sections, tables)

        if extracted:
            # Fill card fields (only non-null values overwrite defaults)
            if extracted.get("task_definition"):
                card["task_definition"] = extracted["task_definition"]
            if extracted.get("method_summary"):
                card["method_summary"] = extracted["method_summary"]
            if extracted.get("dataset_and_metrics"):
                card["dataset_and_metrics"] = extracted["dataset_and_metrics"]
            if extracted.get("reproduction_environment"):
                card["reproduction_environment"] = extracted["reproduction_environment"]
            if extracted.get("limitations"):
                card["limitations"] = extracted["limitations"]
            card["fulltext_status"] = "downloaded"
            n_parsed += 1
        else:
            card["fulltext_status"] = "parse_failed"
            card["repair_hint"] = "LLM extraction returned no result"
            n_failed += 1

        # Generate gaps for any remaining empty fields
        all_gaps.extend(_generate_gaps_for_missing_fields(card))
        updated_cards.append(card)

    trace = _emit(
        "paper_understanding", t0,
        {"entry_mode": entry_mode, "n_seed_cards": len(seed_cards),
         "n_pdf_cards": len(pdf_cards)},
        {"n_parsed": n_parsed, "n_failed": n_failed,
         "n_gaps_generated": len(all_gaps)},
        [{"tool": "pdf.extract_sections", "engine": "pymupdf"},
         {"tool": "pdf.extract_tables", "engine": "pdfplumber"},
         {"tool": "llm_router.call_json", "profile": "fast_json"}],
        "llm_router", [],
        state_keys=["seed_cards", "evidence_gaps", "trace_events"],
    )

    result: dict[str, Any] = {
        "seed_cards": updated_cards,
        "trace_events": [trace],
    }
    if all_gaps:
        result["evidence_gaps"] = list(state.get("evidence_gaps") or []) + all_gaps
    return result
