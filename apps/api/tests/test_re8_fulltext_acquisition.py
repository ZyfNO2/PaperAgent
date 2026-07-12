"""Re8.0 P1-1: Fulltext Acquisition node tests.

Verifies the node's download orchestration, failure handling (paywall/403
→ evidence gap), idempotency, offline guard, and no-op paths.

The HTTP layer (httpx) is mocked at the ``_get_unpaywall_pdf_url`` and
``_download_pdf`` wrapper functions — these are the thin async helpers
that encapsulate all httpx usage inside the node, so mocking them tests
the node's orchestration logic without coupling to httpx's async context
manager protocol.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from apps.api.app.services.agents.graph.nodes import fulltext_acquisition as _fta
from apps.api.app.services.agents.graph.nodes.fulltext_acquisition import (
    _extract_arxiv_id,
    fulltext_acquisition_node,
)
from apps.api.app.services.agents.graph.re80_schema import (
    make_seed_card,
    validate_evidence_gap,
)
from apps.api.app.services.network_guard import NetworkPolicyGuard


@pytest.fixture(autouse=True)
def _reset_guard():
    """Reset the singleton NetworkPolicyGuard between tests."""
    NetworkPolicyGuard._reset()
    yield
    NetworkPolicyGuard._reset()


# ── Card fixtures ───────────────────────────────────────────────────────────

def _doi_card(seed_id: str = "s1", doi: str = "10.1000/test",
              title: str = "Test Paper") -> dict:
    """A verified DOI seed card with metadata_only fulltext status."""
    return make_seed_card(
        seed_id=seed_id,
        input_form="doi",
        resolved_title=title,
        doi=doi,
        existence_status="verified",
        fulltext_status="metadata_only",
        raw_input={"doi": doi, "title": title},
    )


def _arxiv_card(seed_id: str = "s2", arxiv_id: str = "2401.00001",
                title: str = "ArXiv Paper") -> dict:
    """A verified arXiv seed card with metadata_only fulltext status."""
    return make_seed_card(
        seed_id=seed_id,
        input_form="arxiv",
        resolved_title=title,
        canonical_url=f"http://arxiv.org/abs/{arxiv_id}",
        existence_status="verified",
        fulltext_status="metadata_only",
        raw_input={"arxiv_id": arxiv_id, "title": title},
    )


_FAKE_PDF = b"%PDF-1.4\n%fake pdf content for testing\n%%EOF"


# ── _extract_arxiv_id helper ────────────────────────────────────────────────

class TestExtractArxivId:
    def test_from_raw_input_arxiv_id(self):
        card = _arxiv_card()
        assert _extract_arxiv_id(card) == "2401.00001"

    def test_from_canonical_url(self):
        """arXiv ID extracted from canonical_url even if raw_input lacks it."""
        card = make_seed_card(
            seed_id="s1",
            canonical_url="https://arxiv.org/abs/2106.09685v3",
            raw_input={},
        )
        assert _extract_arxiv_id(card) == "2106.09685v3"

    def test_from_raw_input_url(self):
        card = make_seed_card(
            seed_id="s1",
            raw_input={"url": "https://arxiv.org/pdf/2301.12345"},
        )
        assert _extract_arxiv_id(card) == "2301.12345"

    def test_returns_none_for_no_arxiv(self):
        card = _doi_card()
        assert _extract_arxiv_id(card) is None

    def test_returns_none_for_empty_card(self):
        card = make_seed_card(seed_id="s1")
        assert _extract_arxiv_id(card) is None

    def test_old_style_arxiv_id(self):
        """Old-style subject-class IDs like cs.LG/0703001."""
        card = make_seed_card(
            seed_id="s1",
            canonical_url="https://arxiv.org/abs/cs.LG/0703001",
            raw_input={},
        )
        assert _extract_arxiv_id(card) == "cs.LG/0703001"


# ── No-op paths ─────────────────────────────────────────────────────────────

class TestNoOpPaths:
    def test_topic_only_skips(self):
        """entry_mode != seeded_research → no-op trace, no card changes."""
        card = _doi_card()
        state = {"entry_mode": "topic_only", "seed_cards": [card]}
        result = fulltext_acquisition_node(state)
        trace = result["trace_events"][0]
        assert trace["node"] == "fulltext_acquisition"
        assert trace["output_summary"]["skipped"] is True
        # Must not touch seed_cards or evidence_gaps
        assert "seed_cards" not in result
        assert "evidence_gaps" not in result

    def test_empty_seed_cards_skips(self):
        """No seed_cards → no-op."""
        state = {"entry_mode": "seeded_research", "seed_cards": []}
        result = fulltext_acquisition_node(state)
        assert result["trace_events"][0]["output_summary"]["skipped"] is True
        assert "seed_cards" not in result

    def test_no_verified_cards_skips(self):
        """All cards ambiguous → no target cards → no-op."""
        card = make_seed_card(
            seed_id="s1",
            existence_status="ambiguous",
            fulltext_status="metadata_only",
        )
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}
        result = fulltext_acquisition_node(state)
        assert result["trace_events"][0]["output_summary"]["skipped"] is True
        reason = result["trace_events"][0]["output_summary"]["reason"]
        assert "no verified metadata_only" in reason

    def test_offline_mode_skips_gracefully(self):
        """NetworkPolicyGuard offline → no-op, no gaps, no card changes."""
        NetworkPolicyGuard.configure("offline")
        card = _doi_card()
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}
        result = fulltext_acquisition_node(state)
        trace = result["trace_events"][0]
        assert trace["output_summary"]["skipped"] is True
        assert trace["output_summary"]["reason"] == "offline mode"
        assert "seed_cards" not in result
        assert "evidence_gaps" not in result

    def test_offline_via_network_policy_state_skips(self):
        """network_policy='offline' in state → no-op (even if guard not
        configured, state-level check catches it)."""
        card = _doi_card()
        state = {
            "entry_mode": "seeded_research",
            "network_policy": "offline",
            "seed_cards": [card],
        }
        result = fulltext_acquisition_node(state)
        assert result["trace_events"][0]["output_summary"]["skipped"] is True


# ── DOI download success ────────────────────────────────────────────────────

class TestDoiDownloadSuccess:
    @patch.object(
        _fta,
        "_get_unpaywall_pdf_url",
        new_callable=AsyncMock,
    )
    @patch.object(
        _fta,
        "_download_pdf",
        new_callable=AsyncMock,
    )
    def test_doi_download_success(self, mock_download, mock_unpaywall):
        """DOI → Unpaywall returns PDF URL → download succeeds → card updated."""
        mock_unpaywall.return_value = "https://example.com/paper.pdf"
        mock_download.return_value = _FAKE_PDF

        card = _doi_card()
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}
        result = fulltext_acquisition_node(state)

        updated = result["seed_cards"][0]
        assert updated["fulltext_status"] == "fulltext_available"
        assert updated["pdf_bytes"] == _FAKE_PDF
        # No gaps on success
        assert not result.get("evidence_gaps")
        # Trace records the download
        trace = result["trace_events"][0]
        assert trace["output_summary"]["n_downloaded"] == 1
        assert trace["output_summary"]["n_failed"] == 0
        assert trace["output_summary"]["n_gaps_opened"] == 0

    @patch.object(
        _fta,
        "_get_unpaywall_pdf_url",
        new_callable=AsyncMock,
    )
    @patch.object(
        _fta,
        "_download_pdf",
        new_callable=AsyncMock,
    )
    def test_unpaywall_called_with_correct_doi(self, mock_download, mock_unpaywall):
        """Unpaywall helper receives the card's DOI."""
        mock_unpaywall.return_value = "https://example.com/paper.pdf"
        mock_download.return_value = _FAKE_PDF
        card = _doi_card(doi="10.5555/special.doi")
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}
        fulltext_acquisition_node(state)
        mock_unpaywall.assert_called_once_with("10.5555/special.doi")


# ── Download failure → evidence gap ─────────────────────────────────────────

class TestDownloadFailure:
    @patch.object(
        _fta,
        "_get_unpaywall_pdf_url",
        new_callable=AsyncMock,
    )
    @patch.object(
        _fta,
        "_download_pdf",
        new_callable=AsyncMock,
    )
    def test_403_opens_fulltext_gap(self, mock_download, mock_unpaywall):
        """Download returns 403 → fulltext_status stays metadata_only,
        evidence gap opened with type='fulltext'."""
        mock_unpaywall.return_value = "https://example.com/paper.pdf"
        mock_download.side_effect = Exception("403 Forbidden")

        card = _doi_card()
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}
        result = fulltext_acquisition_node(state)

        updated = result["seed_cards"][0]
        assert updated["fulltext_status"] == "metadata_only"
        assert "pdf_bytes" not in updated
        # Gap opened
        assert "evidence_gaps" in result
        gaps = result["evidence_gaps"]
        assert len(gaps) == 1
        gap = gaps[0]
        assert gap["gap_type"] == "fulltext"
        assert gap["status"] == "open"
        assert gap["gap_id"] == "gap-s1-fulltext"
        assert "s1" in gap["related_claim_ids"]
        # Gap must be schema-valid
        assert validate_evidence_gap(gap) == [], f"invalid gap: {gap}"
        # Trace records the failure
        trace = result["trace_events"][0]
        assert trace["output_summary"]["n_failed"] == 1
        assert trace["output_summary"]["n_downloaded"] == 0
        assert trace["output_summary"]["n_gaps_opened"] == 1

    @patch.object(
        _fta,
        "_get_unpaywall_pdf_url",
        new_callable=AsyncMock,
    )
    @patch.object(
        _fta,
        "_download_pdf",
        new_callable=AsyncMock,
    )
    def test_timeout_opens_gap(self, mock_download, mock_unpaywall):
        """Download timeout → gap opened."""
        mock_unpaywall.return_value = "https://example.com/paper.pdf"
        mock_download.side_effect = TimeoutError("read timeout")
        card = _doi_card()
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}
        result = fulltext_acquisition_node(state)
        assert result["seed_cards"][0]["fulltext_status"] == "metadata_only"
        assert len(result["evidence_gaps"]) == 1
        assert result["evidence_gaps"][0]["gap_type"] == "fulltext"

    @patch.object(
        _fta,
        "_get_unpaywall_pdf_url",
        new_callable=AsyncMock,
    )
    def test_paywall_no_oa_url_opens_gap(self, mock_unpaywall):
        """DOI exists but Unpaywall finds no OA location (paywall) → gap."""
        mock_unpaywall.return_value = None  # no OA PDF URL
        card = _doi_card()
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}
        result = fulltext_acquisition_node(state)
        updated = result["seed_cards"][0]
        assert updated["fulltext_status"] == "metadata_only"
        assert "evidence_gaps" in result
        assert result["evidence_gaps"][0]["gap_type"] == "fulltext"
        # The gap reason should mention paywall / no OA
        assert "paywall" in result["evidence_gaps"][0]["why_needed"].lower()


# ── Skip behavior ───────────────────────────────────────────────────────────

class TestSkipBehavior:
    def test_ambiguous_card_skipped(self):
        """Card with existence_status='ambiguous' → not attempted."""
        card = make_seed_card(
            seed_id="s1",
            input_form="doi",
            doi="10.1000/test",
            existence_status="ambiguous",
            fulltext_status="metadata_only",
        )
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}
        result = fulltext_acquisition_node(state)
        # No-op (no target cards)
        assert result["trace_events"][0]["output_summary"]["skipped"] is True
        assert "seed_cards" not in result
        assert "evidence_gaps" not in result

    def test_already_fulltext_available_skipped(self):
        """Card with fulltext_status='fulltext_available' → idempotent skip."""
        card = make_seed_card(
            seed_id="s1",
            input_form="doi",
            doi="10.1000/test",
            existence_status="verified",
            fulltext_status="fulltext_available",
            raw_input={"pdf_bytes": b"already have it"},
        )
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}
        result = fulltext_acquisition_node(state)
        assert result["trace_events"][0]["output_summary"]["skipped"] is True
        assert "seed_cards" not in result

    def test_already_downloaded_skipped(self):
        """Card with legacy fulltext_status='downloaded' → idempotent skip."""
        card = make_seed_card(
            seed_id="s1",
            existence_status="verified",
            fulltext_status="downloaded",
        )
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}
        result = fulltext_acquisition_node(state)
        assert result["trace_events"][0]["output_summary"]["skipped"] is True


# ── arXiv download ──────────────────────────────────────────────────────────

class TestArxivDownload:
    @patch.object(
        _fta,
        "_download_pdf",
        new_callable=AsyncMock,
    )
    def test_arxiv_url_constructed_and_downloaded(self, mock_download):
        """arXiv seed → constructs https://arxiv.org/pdf/{id} → downloads."""
        mock_download.return_value = _FAKE_PDF
        card = _arxiv_card(arxiv_id="2401.00001")
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}
        result = fulltext_acquisition_node(state)

        updated = result["seed_cards"][0]
        assert updated["fulltext_status"] == "fulltext_available"
        assert updated["pdf_bytes"] == _FAKE_PDF
        # Verify the constructed URL
        mock_download.assert_called_once_with("https://arxiv.org/pdf/2401.00001")

    @patch.object(
        _fta,
        "_download_pdf",
        new_callable=AsyncMock,
    )
    def test_arxiv_download_failure_opens_gap(self, mock_download):
        """arXiv download fails → gap with type='fulltext'."""
        mock_download.side_effect = Exception("503 Service Unavailable")
        card = _arxiv_card()
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}
        result = fulltext_acquisition_node(state)
        assert result["seed_cards"][0]["fulltext_status"] == "metadata_only"
        assert len(result["evidence_gaps"]) == 1
        assert result["evidence_gaps"][0]["gap_type"] == "fulltext"


# ── Multiple cards / concurrency ────────────────────────────────────────────

class TestMultipleCards:
    @patch.object(
        _fta,
        "_get_unpaywall_pdf_url",
        new_callable=AsyncMock,
    )
    @patch.object(
        _fta,
        "_download_pdf",
        new_callable=AsyncMock,
    )
    def test_mixed_success_and_failure(self, mock_download, mock_unpaywall):
        """One card succeeds, one fails → one updated, one gap."""
        mock_unpaywall.return_value = "https://example.com/paper.pdf"
        # First card succeeds, second fails
        mock_download.side_effect = [_FAKE_PDF, Exception("403 Forbidden")]

        card1 = _doi_card(seed_id="s1")
        card2 = _doi_card(seed_id="s2", doi="10.2000/other")
        state = {"entry_mode": "seeded_research", "seed_cards": [card1, card2]}
        result = fulltext_acquisition_node(state)

        cards = result["seed_cards"]
        assert cards[0]["fulltext_status"] == "fulltext_available"
        assert cards[1]["fulltext_status"] == "metadata_only"
        assert len(result["evidence_gaps"]) == 1
        assert result["evidence_gaps"][0]["gap_id"] == "gap-s2-fulltext"
        trace = result["trace_events"][0]
        assert trace["output_summary"]["n_downloaded"] == 1
        assert trace["output_summary"]["n_failed"] == 1

    @patch.object(
        _fta,
        "_get_unpaywall_pdf_url",
        new_callable=AsyncMock,
    )
    @patch.object(
        _fta,
        "_download_pdf",
        new_callable=AsyncMock,
    )
    def test_existing_gaps_preserved(self, mock_download, mock_unpaywall):
        """New gaps are appended to existing evidence_gaps, not replacing."""
        mock_unpaywall.return_value = "https://example.com/paper.pdf"
        mock_download.side_effect = Exception("403")
        card = _doi_card()
        existing_gap = {
            "gap_id": "gap-existing",
            "question": "old question",
            "gap_type": "mechanism",
            "why_needed": "",
            "related_claim_ids": [],
            "success_condition": "",
            "budget": {},
            "status": "open",
        }
        state = {
            "entry_mode": "seeded_research",
            "seed_cards": [card],
            "evidence_gaps": [existing_gap],
        }
        result = fulltext_acquisition_node(state)
        gaps = result["evidence_gaps"]
        assert len(gaps) == 2
        assert gaps[0]["gap_id"] == "gap-existing"
        assert gaps[1]["gap_id"] == "gap-s1-fulltext"


# ── Trace / contract ────────────────────────────────────────────────────────

class TestTraceContract:
    @patch.object(
        _fta,
        "_get_unpaywall_pdf_url",
        new_callable=AsyncMock,
    )
    @patch.object(
        _fta,
        "_download_pdf",
        new_callable=AsyncMock,
    )
    def test_trace_has_required_fields(self, mock_download, mock_unpaywall):
        mock_unpaywall.return_value = "https://example.com/paper.pdf"
        mock_download.return_value = _FAKE_PDF
        card = _doi_card()
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}
        result = fulltext_acquisition_node(state)
        trace = result["trace_events"][0]
        assert trace["node"] == "fulltext_acquisition"
        assert trace["provider"] == "httpx"
        assert trace["elapsed_s"] >= 0
        assert "seed_cards" in trace["state_keys"]
        assert "evidence_gaps" in trace["state_keys"]
        assert "trace_events" in trace["state_keys"]
        assert "errors" in trace["state_keys"]
        # Tool calls recorded for auditability
        tool_names = {t["tool"] for t in trace["tool_calls"]}
        assert "unpaywall" in tool_names
        assert "arxiv_pdf" in tool_names

    def test_trace_skipped_has_reason(self):
        """Skipped traces must carry a 'reason' for debuggability."""
        state = {"entry_mode": "topic_only", "seed_cards": []}
        result = fulltext_acquisition_node(state)
        trace = result["trace_events"][0]
        assert trace["output_summary"]["skipped"] is True
        assert "reason" in trace["output_summary"]
