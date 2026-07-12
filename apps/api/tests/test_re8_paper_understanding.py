"""Re8.0 WP2 Paper Understanding Tests.

Tests PDF section/table extraction, Evidence Gap generation for missing
WP2 fields, and the paper_understanding_node no-op / parse paths.
"""
from __future__ import annotations

import pytest

from apps.api.app.services.agents.graph.nodes.paper_understanding import (
    _canonical_section_name,
    _generate_gaps_for_missing_fields,
    _UNDERSTANDING_SYSTEM,
    extract_sections,
    extract_tables,
    paper_understanding_node,
)
from apps.api.app.services.agents.graph.re80_schema import (
    make_seed_card,
    validate_evidence_gap,
)


# ---------------------------------------------------------------------------
# Test PDF fixture
# ---------------------------------------------------------------------------

def _make_test_pdf() -> bytes:
    """Generate a minimal PDF with headings (14pt) + body (10pt) for
    section detection via PyMuPDF font-size analysis."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    # Headings (large font)
    page.insert_text((72, 72), "Abstract", fontsize=14)
    page.insert_text((72, 160), "1. Introduction", fontsize=14)
    page.insert_text((72, 230), "2. Method", fontsize=14)
    page.insert_text((72, 320), "3. Experiments", fontsize=14)
    # Body text (normal font)
    page.insert_text((72, 100), "This paper proposes a new method.", fontsize=10)
    page.insert_text((72, 115), "It works on image classification.", fontsize=10)
    page.insert_text((72, 190), "Deep learning has advanced rapidly.", fontsize=10)
    page.insert_text((72, 260), "We use a transformer architecture.", fontsize=10)
    page.insert_text((72, 275), "The model has 12 layers.", fontsize=10)
    page.insert_text((72, 350), "We evaluate on CIFAR-10 and ImageNet.", fontsize=10)
    page.insert_text((72, 365), "We achieve 95% accuracy.", fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


# ---------------------------------------------------------------------------
# _canonical_section_name
# ---------------------------------------------------------------------------

class TestCanonicalSectionName:
    def test_abstract(self):
        assert _canonical_section_name("Abstract") == "abstract"

    def test_numbered_introduction(self):
        assert _canonical_section_name("1. Introduction") == "introduction"

    def test_introduction_no_number(self):
        assert _canonical_section_name("Introduction") == "introduction"

    def test_method(self):
        assert _canonical_section_name("2. Method") == "method"

    def test_methodology(self):
        assert _canonical_section_name("3. Methodology") == "method"

    def test_related_work(self):
        assert _canonical_section_name("Related Work") == "related_work"

    def test_experiments(self):
        assert _canonical_section_name("4. Experiments") == "experiments"

    def test_conclusion(self):
        assert _canonical_section_name("5. Conclusion") == "conclusion"

    def test_unknown_heading(self):
        assert _canonical_section_name("Foo Bar Baz") is None


# ---------------------------------------------------------------------------
# extract_sections
# ---------------------------------------------------------------------------

class TestExtractSections:
    def test_extracts_canonical_sections(self):
        pdf = _make_test_pdf()
        sections = extract_sections(pdf)
        assert isinstance(sections, dict)
        # Should find at least some canonical sections
        canonical_found = {
            s for s in sections.keys()
            if s in ("abstract", "introduction", "method", "experiments")
        }
        assert len(canonical_found) >= 2, f"expected >=2 sections, got {sections.keys()}"

    def test_abstract_text_captured(self):
        pdf = _make_test_pdf()
        sections = extract_sections(pdf)
        # Abstract body should mention "proposes"
        abstract_text = sections.get("abstract", "").lower()
        assert "proposes" in abstract_text or "method" in abstract_text

    def test_method_text_captured(self):
        pdf = _make_test_pdf()
        sections = extract_sections(pdf)
        method_text = sections.get("method", "").lower()
        assert "transformer" in method_text

    def test_empty_pdf_returns_dict(self):
        import fitz
        doc = fitz.open()
        doc.new_page()  # blank page, no text
        pdf = doc.tobytes()
        doc.close()
        sections = extract_sections(pdf)
        assert isinstance(sections, dict)


# ---------------------------------------------------------------------------
# extract_tables
# ---------------------------------------------------------------------------

class TestExtractTables:
    def test_pdf_without_tables_returns_empty(self):
        pdf = _make_test_pdf()
        tables = extract_tables(pdf)
        assert tables == []

    def test_max_tables_limit(self):
        pdf = _make_test_pdf()
        tables = extract_tables(pdf, max_tables=0)
        assert tables == []


# ---------------------------------------------------------------------------
# _generate_gaps_for_missing_fields
# ---------------------------------------------------------------------------

class TestGenerateGapsForMissingFields:
    def test_all_missing_generates_4_gaps(self):
        card = make_seed_card(seed_id="s1")
        gaps = _generate_gaps_for_missing_fields(card)
        assert len(gaps) == 4
        gap_ids = {g["gap_id"] for g in gaps}
        assert "gap-s1-method_summary" in gap_ids
        assert "gap-s1-dataset_and_metrics" in gap_ids
        assert "gap-s1-reproduction_environment" in gap_ids
        assert "gap-s1-limitations" in gap_ids

    def test_all_filled_generates_no_gap(self):
        card = make_seed_card(
            seed_id="s1",
            method_summary="A transformer model.",
            dataset_and_metrics={"datasets": ["CIFAR-10"]},
            reproduction_environment={"framework": "PyTorch"},
            limitations=["Only tested on images."],
        )
        gaps = _generate_gaps_for_missing_fields(card)
        assert gaps == []

    def test_partial_fill(self):
        card = make_seed_card(seed_id="s1", method_summary="A model.")
        gaps = _generate_gaps_for_missing_fields(card)
        assert len(gaps) == 3
        ids = {g["gap_id"] for g in gaps}
        assert "gap-s1-method_summary" not in ids

    def test_empty_string_treated_as_missing(self):
        card = make_seed_card(seed_id="s1", method_summary="")
        gaps = _generate_gaps_for_missing_fields(card)
        assert any(g["gap_id"] == "gap-s1-method_summary" for g in gaps)

    def test_empty_dict_treated_as_missing(self):
        card = make_seed_card(
            seed_id="s1",
            method_summary="x",
            dataset_and_metrics={},
            reproduction_environment={"framework": "PT"},
            limitations=["y"],
        )
        gaps = _generate_gaps_for_missing_fields(card)
        assert len(gaps) == 1
        assert gaps[0]["gap_id"] == "gap-s1-dataset_and_metrics"

    def test_gaps_are_valid(self):
        card = make_seed_card(seed_id="s1")
        gaps = _generate_gaps_for_missing_fields(card)
        for g in gaps:
            assert validate_evidence_gap(g) == [], f"invalid gap: {g}"

    def test_gap_type_mapping(self):
        card = make_seed_card(seed_id="s1")
        gaps = _generate_gaps_for_missing_fields(card)
        by_field = {g["gap_id"].split("-")[-1]: g["gap_type"] for g in gaps}
        # method_summary → mechanism, others → environment
        assert by_field["method_summary"] == "mechanism"
        assert by_field["dataset_and_metrics"] == "environment"


# ---------------------------------------------------------------------------
# paper_understanding_node — no-op paths
# ---------------------------------------------------------------------------

class TestPaperUnderstandingNodeNoOp:
    def test_topic_only_skips(self):
        state = {"entry_mode": "topic_only", "seed_cards": []}
        result = paper_understanding_node(state)
        assert "trace_events" in result
        trace = result["trace_events"][0]
        assert trace["node"] == "paper_understanding"
        assert trace["output_summary"]["skipped"] is True
        # Must not touch seed_cards
        assert "seed_cards" not in result

    def test_no_seed_cards_skips(self):
        state = {"entry_mode": "seeded_research", "seed_cards": []}
        result = paper_understanding_node(state)
        assert result["trace_events"][0]["output_summary"]["skipped"] is True

    def test_title_only_seed_skips(self):
        """A seed card with input_form=title (no PDF) should be skipped."""
        card = make_seed_card(seed_id="s1", input_form="title",
                              resolved_title="Some Paper")
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}
        result = paper_understanding_node(state)
        assert result["trace_events"][0]["output_summary"]["skipped"] is True
        reason = result["trace_events"][0]["output_summary"]["reason"]
        assert "no PDF" in reason

    def test_trace_has_state_keys(self):
        """Trace must list state_keys for debugging."""
        state = {"entry_mode": "topic_only", "seed_cards": []}
        result = paper_understanding_node(state)
        trace = result["trace_events"][0]
        assert "seed_cards" in trace["state_keys"]
        assert "evidence_gaps" in trace["state_keys"]
        assert "trace_events" in trace["state_keys"]


# ---------------------------------------------------------------------------
# paper_understanding_node — PDF parse path
# ---------------------------------------------------------------------------

class TestPaperUnderstandingNodeWithPdf:
    def test_pdf_card_parsed_successfully(self, monkeypatch):
        pdf = _make_test_pdf()
        card = make_seed_card(
            seed_id="s1",
            input_form="pdf",
            resolved_title="Test Paper",
            raw_input={"pdf_bytes": pdf, "title": "Test Paper"},
        )
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}

        mock_result = {
            "task_definition": "Image classification.",
            "method_summary": "Transformer architecture.",
            "dataset_and_metrics": {"datasets": ["CIFAR-10"]},
            "reproduction_environment": {"framework": "PyTorch"},
            "limitations": ["Only images."],
        }
        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.paper_understanding._call_understanding_llm",
            lambda title, sections, tables: mock_result,
        )

        result = paper_understanding_node(state)
        assert "seed_cards" in result
        updated = result["seed_cards"][0]
        assert updated["method_summary"] == "Transformer architecture."
        assert updated["dataset_and_metrics"]["datasets"] == ["CIFAR-10"]
        assert updated["fulltext_status"] == "downloaded"
        # All fields filled → no gaps expected
        assert not result.get("evidence_gaps")

    def test_pdf_parse_with_partial_llm_result_generates_gaps(self, monkeypatch):
        pdf = _make_test_pdf()
        card = make_seed_card(
            seed_id="s1",
            input_form="pdf",
            resolved_title="Test",
            raw_input={"pdf_bytes": pdf, "title": "Test"},
        )
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}

        # LLM returns only method_summary
        mock_result = {
            "method_summary": "A transformer.",
        }
        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.paper_understanding._call_understanding_llm",
            lambda title, sections, tables: mock_result,
        )

        result = paper_understanding_node(state)
        updated = result["seed_cards"][0]
        assert updated["method_summary"] == "A transformer."
        assert updated["fulltext_status"] == "downloaded"
        # 3 fields still empty → 3 gaps
        assert "evidence_gaps" in result
        assert len(result["evidence_gaps"]) == 3

    def test_invalid_pdf_bytes_marks_parse_failed(self):
        card = make_seed_card(
            seed_id="s1",
            input_form="pdf",
            raw_input={"pdf_bytes": b"not a pdf at all"},
        )
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}

        result = paper_understanding_node(state)
        updated = result["seed_cards"][0]
        assert updated["fulltext_status"] == "parse_failed"
        assert "repair_hint" in updated
        # Gaps generated for all 4 missing fields
        assert "evidence_gaps" in result
        assert len(result["evidence_gaps"]) == 4

    def test_llm_returns_none_marks_parse_failed(self, monkeypatch):
        pdf = _make_test_pdf()
        card = make_seed_card(
            seed_id="s1",
            input_form="pdf",
            raw_input={"pdf_bytes": pdf},
        )
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}

        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.paper_understanding._call_understanding_llm",
            lambda title, sections, tables: None,
        )

        result = paper_understanding_node(state)
        updated = result["seed_cards"][0]
        assert updated["fulltext_status"] == "parse_failed"
        assert "LLM extraction" in updated.get("repair_hint", "")

    def test_trace_recorded_on_success(self, monkeypatch):
        pdf = _make_test_pdf()
        card = make_seed_card(
            seed_id="s1",
            input_form="pdf",
            raw_input={"pdf_bytes": pdf},
        )
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}

        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.paper_understanding._call_understanding_llm",
            lambda title, sections, tables: {"method_summary": "x"},
        )

        result = paper_understanding_node(state)
        trace = result["trace_events"][0]
        assert trace["node"] == "paper_understanding"
        assert trace["output_summary"]["n_parsed"] == 1
        assert trace["output_summary"]["n_failed"] == 0
        assert trace["provider"] == "llm_router"
        assert trace["elapsed_s"] >= 0
        assert "seed_cards" in trace["state_keys"]


# ---------------------------------------------------------------------------
# LLM prompt contract
# ---------------------------------------------------------------------------

class TestUnderstandingPromptContract:
    """Re8.0 §1 reasoner model rules: system prompt <100 tokens, output
    contract at end of user prompt, no pre-filled title field."""

    def test_system_prompt_is_short(self):
        # System prompt must be < 100 tokens (~400 chars rough estimate)
        assert len(_UNDERSTANDING_SYSTEM) < 400

    def test_user_template_has_output_contract(self):
        from apps.api.app.services.agents.graph.nodes.paper_understanding import (
            _UNDERSTANDING_USER_TEMPLATE,
        )
        assert "[OUTPUT CONTRACT]" in _UNDERSTANDING_USER_TEMPLATE
        assert "JSON object" in _UNDERSTANDING_USER_TEMPLATE

    def test_user_template_uses_title_placeholder(self):
        """Title is passed as data, not pre-filled in template structure."""
        from apps.api.app.services.agents.graph.nodes.paper_understanding import (
            _UNDERSTANDING_USER_TEMPLATE,
        )
        assert "{title}" in _UNDERSTANDING_USER_TEMPLATE
