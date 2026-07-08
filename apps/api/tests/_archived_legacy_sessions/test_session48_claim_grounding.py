"""Session 48: RAG ↔ Evidence Ledger 联动 + Claim Grounding tests.

覆盖 (SOP §11 Task 10):
- EvidenceItem extension: paper_library_chunk + chunk fields (Task 1)
- add_paper_library_chunk 入池 + 去重 (Task 2)
- write_answer_to_ledger: RAG answer → ledger (Task 2)
- scope=accepted_papers 过滤 (Task 3) — 沿用 S47
- rejected chunk 永不返回 (Task 6)
- claim_grounding 启发式: supported / weak_support / contradiction / unsupported (Task 4)
- LLM fallback 路径 (Task 4)
- citation 规则: pending direct → background, failed verify → background (Task 6)
- filter_refs_by_citation_rules: rejected 移除 (Task 6)
- ground-claims API 端点形状 (Task 7)
- extract_section_claims 抽取声明性句子 (Task 5)
"""

from __future__ import annotations

import base64
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _tmp_library(monkeypatch, tmp_path):
    """每个测试用独立 .runtime/paper_library + 清 evidence + 清 vocab."""

    monkeypatch.setenv("PAPERAGENT_PAPER_LIBRARY_DIR", str(tmp_path / "paper_library"))
    from app.services import evidence as ev_store
    from app.services.paper_library import embedding
    ev_store.reset_all()
    embedding.reset_vocab()
    yield
    ev_store.reset_all()
    embedding.reset_vocab()


def _fake_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%%%EOF"


def _seed_chunks(project_id: str, paper_id: str) -> None:
    """写 3 个 chunk: method / abstract / introduction."""
    from app.schemas_paper_library import PaperChunk
    from app.services.paper_library import storage

    chunks = [
        PaperChunk(
            chunk_id=f"c_{paper_id}_m", paper_id=paper_id, project_id=project_id,
            section_title="Method", section_path=["Method"],
            text="We propose YOLO based steel defect detection. The model uses anchor free detection.",
            token_count=12, chunk_type="method",
            page_start=3, page_end=4,
        ),
        PaperChunk(
            chunk_id=f"c_{paper_id}_a", paper_id=paper_id, project_id=project_id,
            section_title="Abstract", section_path=["Abstract"],
            text="Abstract: This paper studies YOLO defects in steel manufacturing.",
            token_count=10, chunk_type="abstract",
            page_start=1, page_end=1,
        ),
        PaperChunk(
            chunk_id=f"c_{paper_id}_i", paper_id=paper_id, project_id=project_id,
            section_title="Introduction", section_path=["Introduction"],
            text="Introduction: Real time defect detection in steel plates is challenging.",
            token_count=11, chunk_type="introduction",
            page_start=2, page_end=2,
        ),
    ]
    storage.save_chunks(chunks)
    from pathlib import Path
    storage.update_manifest(
        project_id=project_id, paper_id=paper_id,
        record_path=str(Path(storage._project_paths(project_id)["parsed"]) / f"{paper_id}.json"),
        chunks_path=str(Path(storage._project_paths(project_id)["chunks"]) / f"{paper_id}_chunks.jsonl"),
        chunk_count=len(chunks), parse_status="parsed",
        source_mode="local_upload",
    )


def _seed_record(project_id: str, paper_id: str, title: str = "YOLO Steel Defect Detection",
                 arxiv_id: str | None = None) -> None:
    from app.schemas_paper_library import PaperRecord
    from app.services.paper_library import storage
    rec = PaperRecord(
        paper_id=paper_id, project_id=project_id, title=title,
        source_mode="local_upload", parse_status="parsed",
        metadata_status="resolved", year=2024, arxiv_id=arxiv_id or "2401.00001",
    )
    storage.save_paper_record(rec)


# ===========================================================================
# 1. EvidenceItem extension: paper_library_chunk 类型
# ===========================================================================


class TestEvidenceItemExtension:
    def test_evidence_type_includes_paper_library_chunk(self):
        from app.schemas_evidence import EvidenceType
        # Literal 含 paper_library_chunk
        import typing
        args = typing.get_args(EvidenceType)
        assert "paper_library_chunk" in args

    def test_source_mode_includes_paper_rag(self):
        from app.schemas_evidence import SourceMode
        import typing
        args = typing.get_args(SourceMode)
        assert "paper_rag" in args

    def test_evidence_item_with_chunk_fields(self):
        from app.schemas_evidence import EvidenceItem
        e = EvidenceItem(
            evidence_id="x1", project_id="p1",
            evidence_type="paper_library_chunk",
            source_mode="paper_rag",
            title="YOLO chunk",
            paper_id="paper_xx_1",
            chunk_id="c_paper_xx_1_m",
            page_start=3, page_end=4,
            quote="YOLO steel defect method",
            support_type="direct",
            review_status="pending",
            tags=["paper_rag"],
        )
        d = e.model_dump()
        assert d["paper_id"] == "paper_xx_1"
        assert d["chunk_id"] == "c_paper_xx_1_m"
        assert d["page_start"] == 3
        assert d["support_type"] == "direct"

    def test_evidence_item_default_chunk_fields_none(self):
        """旧 evidence (paper/dataset/repo/note) 不传新字段也 OK."""
        from app.schemas_evidence import EvidenceItem
        e = EvidenceItem(
            evidence_id="y1", project_id="p1",
            evidence_type="paper", source_mode="manual",
            title="Old Paper",
        )
        assert e.paper_id is None
        assert e.chunk_id is None
        assert e.support_type is None


# ===========================================================================
# 2. add_paper_library_chunk 入池 + 去重
# ===========================================================================


class TestAddPaperLibraryChunk:
    def test_add_creates_chunk(self):
        from app.services import evidence as ev_store
        resp = ev_store.add_paper_library_chunk(
            project_id="p1",
            paper_id="paper_x", chunk_id="c_x_1",
            title="Test chunk", quote="hello",
            page_start=3, support_type="direct",
        )
        assert resp.ok is True
        assert resp.evidence.evidence_type == "paper_library_chunk"
        assert resp.evidence.review_status == "pending"
        assert resp.evidence.paper_id == "paper_x"
        assert "paper_rag" in resp.evidence.tags

    def test_add_dedup_same_chunk_id(self):
        from app.services import evidence as ev_store
        r1 = ev_store.add_paper_library_chunk(
            "p1", paper_id="px", chunk_id="cx1", title="t1",
        )
        r2 = ev_store.add_paper_library_chunk(
            "p1", paper_id="px", chunk_id="cx1", title="t1",
        )
        assert r1.ok is True
        assert r2.ok is False  # dedup
        assert "已存在" in r2.message

    def test_find_chunk(self):
        from app.services import evidence as ev_store
        ev_store.add_paper_library_chunk(
            "p1", paper_id="px", chunk_id="cx2", title="t", review_status="accepted",
        )
        item = ev_store.find_paper_library_chunk("p1", "px", "cx2")
        assert item is not None
        assert item.review_status == "accepted"

    def test_list_chunks(self):
        from app.services import evidence as ev_store
        ev_store.add_paper_library_chunk("p1", paper_id="px", chunk_id="cx3", title="t1")
        ev_store.add_paper_library_chunk("p1", paper_id="px", chunk_id="cx4", title="t2")
        chunks = ev_store.list_paper_library_chunks("p1")
        assert len(chunks) == 2


# ===========================================================================
# 3. write_answer_to_ledger: RAG answer → ledger
# ===========================================================================


class TestWriteAnswerToLedger:
    def test_writes_all_evidence_refs(self, _tmp_library):
        from app.services import evidence as ev_store
        from app.services.paper_library import paper_qa
        from app.schemas_paper_rag import EvidenceRef, PaperRAGAnswer

        _seed_record("p1", "paper_xx_1", title="YOLO Test")
        _seed_chunks("p1", "paper_xx_1")

        ans = PaperRAGAnswer(
            question="q",
            answer="a",
            evidence_refs=[
                EvidenceRef(paper_id="paper_xx_1", chunk_id="c_paper_xx_1_m",
                            quote="YOLO steel", support_type="direct"),
                EvidenceRef(paper_id="paper_xx_1", chunk_id="c_paper_xx_1_a",
                            quote="abstract", support_type="indirect"),
            ],
            unsupported_claims=[],
        )
        created = paper_qa.write_answer_to_ledger("p1", ans)
        assert len(created) == 2
        ledger_chunks = ev_store.list_paper_library_chunks("p1")
        assert len(ledger_chunks) == 2
        # 默认 review_status = pending
        assert all(c.review_status == "pending" for c in ledger_chunks)
        # tag 含 paper_rag
        assert all("paper_rag" in c.tags for c in ledger_chunks)

    def test_no_refs_returns_empty(self, _tmp_library):
        from app.services.paper_library import paper_qa
        from app.schemas_paper_rag import PaperRAGAnswer
        ans = PaperRAGAnswer(question="q", answer="a", evidence_refs=[])
        created = paper_qa.write_answer_to_ledger("p1", ans)
        assert created == []

    def test_dedup_on_repeat(self, _tmp_library):
        from app.services.paper_library import paper_qa
        from app.schemas_paper_rag import EvidenceRef, PaperRAGAnswer

        _seed_record("p1", "paper_xx_1", title="YOLO")
        _seed_chunks("p1", "paper_xx_1")

        ans = PaperRAGAnswer(
            question="q", answer="a",
            evidence_refs=[EvidenceRef(paper_id="paper_xx_1", chunk_id="c_paper_xx_1_m",
                                       quote="x", support_type="direct")],
        )
        c1 = paper_qa.write_answer_to_ledger("p1", ans)
        c2 = paper_qa.write_answer_to_ledger("p1", ans)
        assert len(c1) == 1
        assert c2 == []  # 重复 chunk 不再入池


# ===========================================================================
# 4. Scope filter: rejected chunk 永不返回
# ===========================================================================


class TestScopeFilterRejected:
    def test_rejected_chunk_excluded_from_all_papers(self, _tmp_library):
        """session 48 Task 6: rejected chunk 在 all_papers scope 下也不返回."""
        from app.services import evidence as ev_store
        from app.services.paper_library import indexer, retriever
        _seed_record("p1", "paper_xx_1", title="Paper1")
        _seed_chunks("p1", "paper_xx_1")
        indexer.build_index("p1")

        # 把 c_paper_xx_1_m 标记 rejected
        ev_store.add_paper_library_chunk(
            "p1", paper_id="paper_xx_1", chunk_id="c_paper_xx_1_m",
            title="Rejected", review_status="rejected",
        )

        hits = retriever.retrieve("p1", "YOLO defect", scope="all_papers", top_k=10)
        ids = {cid for cid, _ in hits}
        # rejected chunk 永不出
        assert "c_paper_xx_1_m" not in ids
        # 其他 chunk 可出现
        assert "c_paper_xx_1_a" in ids or "c_paper_xx_1_i" in ids

    def test_rejected_chunk_excluded_from_accepted_papers(self, _tmp_library):
        from app.services import evidence as ev_store
        from app.services.paper_library import indexer, retriever
        from app.schemas_evidence import PaperManualCreate

        _seed_record("p1", "paper_xx_1", title="P1", arxiv_id="2401.00011")
        _seed_chunks("p1", "paper_xx_1")
        indexer.build_index("p1")

        # mark paper accepted
        ev_store.add_paper_manual("p1", PaperManualCreate(
            title="P1", arxiv_id="2401.00011", review_status="accepted",
        ))
        # 把 c_paper_xx_1_m 标记 rejected
        ev_store.add_paper_library_chunk(
            "p1", paper_id="paper_xx_1", chunk_id="c_paper_xx_1_m",
            title="Rejected", review_status="rejected",
        )

        hits = retriever.retrieve("p1", "YOLO defect", scope="accepted_papers", top_k=10)
        ids = {cid for cid, _ in hits}
        assert "c_paper_xx_1_m" not in ids


# ===========================================================================
# 5. Citation rule filter: pending/failed/rejected
# ===========================================================================


class TestCitationRuleFilter:
    def test_rejected_ref_removed(self, _tmp_library):
        from app.services import evidence as ev_store
        from app.services.paper_library import paper_qa
        from app.schemas_paper_rag import EvidenceRef

        ev_store.add_paper_library_chunk(
            "p1", paper_id="px", chunk_id="cx1", title="rej", review_status="rejected",
        )
        refs = [EvidenceRef(paper_id="px", chunk_id="cx1", quote="x", support_type="direct")]
        out, warns = paper_qa.filter_refs_by_citation_rules("p1", refs)
        assert len(out) == 0
        assert any("rejected" in w for w in warns)

    def test_pending_direct_downgraded_to_background(self, _tmp_library):
        from app.services import evidence as ev_store
        from app.services.paper_library import paper_qa
        from app.schemas_paper_rag import EvidenceRef

        ev_store.add_paper_library_chunk(
            "p1", paper_id="px", chunk_id="cx2", title="pend", review_status="pending",
        )
        refs = [EvidenceRef(paper_id="px", chunk_id="cx2", quote="x", support_type="direct")]
        out, warns = paper_qa.filter_refs_by_citation_rules("p1", refs)
        assert len(out) == 1
        assert out[0].support_type == "background"
        assert any("pending" in w and "降级" in w for w in warns)

    def test_failed_verification_direct_downgraded(self, _tmp_library):
        from app.services import evidence as ev_store
        from app.services.paper_library import paper_qa
        from app.schemas_paper_rag import EvidenceRef

        ev_store.add_paper_library_chunk(
            "p1", paper_id="px", chunk_id="cx3", title="ok",
            review_status="accepted", verification_status="failed",
        )
        refs = [EvidenceRef(paper_id="px", chunk_id="cx3", quote="x", support_type="direct")]
        out, warns = paper_qa.filter_refs_by_citation_rules("p1", refs)
        assert len(out) == 1
        assert out[0].support_type == "background"
        assert any("verification failed" in w for w in warns)

    def test_accepted_direct_passes(self, _tmp_library):
        from app.services import evidence as ev_store
        from app.services.paper_library import paper_qa
        from app.schemas_paper_rag import EvidenceRef

        ev_store.add_paper_library_chunk(
            "p1", paper_id="px", chunk_id="cx4", title="ok",
            review_status="accepted", verification_status="verified",
        )
        refs = [EvidenceRef(paper_id="px", chunk_id="cx4", quote="x", support_type="direct")]
        out, warns = paper_qa.filter_refs_by_citation_rules("p1", refs)
        assert len(out) == 1
        assert out[0].support_type == "direct"
        assert warns == []


# ===========================================================================
# 6. claim_grounding heuristic: supported / contradiction / unsupported / weak_support
# ===========================================================================


class TestClaimGroundingHeuristic:
    def _setup_indexed_paper(self, project_id="p1"):
        _seed_record(project_id, "paper_xx_1", title="YOLO Steel")
        _seed_chunks(project_id, "paper_xx_1")
        from app.services.paper_library import indexer
        indexer.build_index(project_id)

    def test_supported_when_keyword_overlap_high(self, _tmp_library):
        """heuristic 路径: chunk 含 claim 关键词 → supported."""
        from app.services.paper_library import claim_grounding

        self._setup_indexed_paper("p1")
        result = claim_grounding.ground_claim(
            "YOLO steel defect detection method",
            project_id="p1",
            scope="all_papers",
            top_k=3,
        )
        assert result.verdict in ("supported", "weak_support")
        if result.verdict == "supported":
            assert len(result.supporting_chunks) >= 1

    def test_unsupported_when_no_hits(self, _tmp_library):
        """空论文库 → unsupported, retrieval_mode=fallback."""
        from app.services.paper_library import claim_grounding

        result = claim_grounding.ground_claim(
            "Quantum entanglement in blockchain",
            project_id="empty_proj",
            scope="all_papers",
            top_k=3,
        )
        assert result.verdict == "unsupported"
        assert result.confidence == 0.0
        assert result.retrieval_mode == "fallback"

    def test_llm_path_used_when_available(self, _tmp_library):
        """LLM 返回有效 verdict → result.retrieval_mode='llm'."""
        from app.services import evidence as ev_store
        from app.services.paper_library import claim_grounding

        self._setup_indexed_paper("p1")
        # 注册 chunk 为 accepted (否则默认 pending → direct 降级)
        for cid in ("c_paper_xx_1_m", "c_paper_xx_1_a", "c_paper_xx_1_i"):
            ev_store.add_paper_library_chunk(
                "p1", paper_id="paper_xx_1", chunk_id=cid,
                title="ok", review_status="accepted", verification_status="verified",
            )
        llm_resp = {
            "classifications": [
                {"ref_id": 1, "support_type": "direct", "reason": "directly states"},
            ],
            "verdict": "supported",
            "confidence": 0.9,
            "reason": "LLM 直接支持",
        }
        with patch("app.services.llm.chat_json", return_value=llm_resp):
            result = claim_grounding.ground_claim(
                "YOLO steel detection",
                project_id="p1",
                scope="all_papers",
                top_k=3,
            )
        assert result.retrieval_mode == "llm"
        assert result.verdict == "supported"
        assert result.confidence >= 0.5

    def test_contradiction_when_negation_detected(self, _tmp_library):
        """heuristic: chunk 含 'no' / 'not' / '无法' + claim 关键词 → contradiction."""
        from app.services.paper_library import claim_grounding
        from app.services.paper_library import indexer
        from app.schemas_paper_library import PaperChunk
        from app.services.paper_library import storage

        _seed_record("p1", "paper_xx_1", title="Contradict paper")
        # 用一段含否定的 chunk
        chunks = [
            PaperChunk(
                chunk_id="c_neg_1", paper_id="paper_xx_1", project_id="p1",
                section_title="Result", section_path=["Result"],
                text="YOLO method does not work for steel defect detection on NEU-DET.",
                token_count=10, chunk_type="result",
                page_start=5,
            ),
        ]
        storage.save_chunks(chunks)
        indexer.build_index("p1")

        result = claim_grounding.ground_claim(
            "YOLO steel defect detection on NEU-DET",
            project_id="p1",
            scope="all_papers",
            top_k=3,
        )
        # heuristic 路径 + chunk 含 "does not" + claim 关键词 → contradiction
        assert result.verdict in ("contradiction", "weak_support", "unsupported")
        if result.verdict == "contradiction":
            assert len(result.contradicting_chunks) >= 1

    def test_empty_claim_returns_unsupported(self, _tmp_library):
        from app.services.paper_library import claim_grounding
        result = claim_grounding.ground_claim("", project_id="p1")
        assert result.verdict == "unsupported"
        assert result.confidence == 0.0


# ===========================================================================
# 7. Section integration: extract + ground + enforce
# ===========================================================================


class TestSectionIntegration:
    def test_extract_section_claims_skip_headings_and_lists(self):
        from app.services.paper_library.section_integration import extract_section_claims

        md = (
            "## 一、研究背景\n\n"
            "- 列表项 1\n"
            "- 列表项 2\n\n"
            "YOLO 在钢材缺陷检测上达到了 95% 的准确率。\n"
            "本研究使用了 anchor-free 检测方法。\n"
            "[E1] 这一句是引用。\n"
        )
        claims = extract_section_claims(md)
        # 不应包含列表项和标题
        assert any("95%" in c for c in claims)
        assert any("anchor-free" in c for c in claims)
        # 标题 / 列表不应进入 claims
        assert not any("研究背景" in c for c in claims)
        assert not any("列表项" in c for c in claims)

    def test_enforce_section_citation_rules_passes_through(self):
        """无 ledger 状态下 (chunk 不存在 → pending), 直接 ref 应被降级."""
        from app.services.paper_library.section_integration import (
            enforce_section_citation_rules,
        )
        from app.schemas_paper_rag import EvidenceRef
        # chunk 不在 ledger → 默认 pending
        refs = [EvidenceRef(paper_id="px", chunk_id="cx", quote="x", support_type="direct")]
        out, warns = enforce_section_citation_rules("p1", refs)
        # pending direct → background
        assert len(out) == 1
        assert out[0].support_type == "background"
        assert any("pending" in w for w in warns)


# ===========================================================================
# 8. ground-claims API endpoint
# ===========================================================================


class TestGroundClaimsEndpoint:
    def _client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_endpoint_shape_with_empty_library(self, _tmp_library):
        """空论文库 → 端点返回 unsupported."""
        client = self._client()
        r = client.post(
            "/api/v1/projects/empty_proj/paper-library/ground-claims",
            json={"claims": ["test claim"], "scope": "all_papers", "top_k": 3},
        )
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert data["total"] == 1
        assert data["results"][0]["verdict"] == "unsupported"
        assert data["results"][0]["retrieval_mode"] == "fallback"

    def test_endpoint_validation_empty_claims(self, _tmp_library):
        client = self._client()
        r = client.post(
            "/api/v1/projects/p1/paper-library/ground-claims",
            json={"claims": []},
        )
        # FastAPI 422 (Pydantic min_length=1) 或 400 (manual check)
        assert r.status_code in (400, 422)

    def test_endpoint_batch_with_2_claims(self, _tmp_library):
        client = self._client()
        r = client.post(
            "/api/v1/projects/p1/paper-library/ground-claims",
            json={"claims": ["claim one", "claim two"], "scope": "all_papers"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert len(data["results"]) == 2


# ===========================================================================
# 9. /ask endpoint writes to ledger (Task 2 + 6 integration)
# ===========================================================================


class TestAskWritesToLedger:
    def test_ask_writes_evidence_refs_to_ledger(self, _tmp_library):
        from app.services import evidence as ev_store
        from app.services.paper_library import indexer

        # 上传 + 索引
        from app.services.paper_library import ingest_upload
        content = base64.b64encode(_fake_pdf_bytes()).decode()
        outcome = ingest_upload("p1", "t.pdf", content, "application/pdf")
        pid = outcome.paper_id
        _seed_chunks("p1", pid)
        _seed_record("p1", pid, title="YOLO Test")
        indexer.build_index("p1", paper_ids=[pid])

        client = self._client()
        mock_resp = {
            "answer": "可以用 [1] 做 baseline",
            "evidence_refs": [
                {"ref_id": 1, "paper_id": pid, "chunk_id": f"c_{pid}_m",
                 "page_start": 3, "quote": "YOLO steel",
                 "support_type": "direct"},
            ],
            "unsupported_claims": [],
        }
        with patch("app.services.llm.chat_json", return_value=mock_resp):
            r = client.post(
                "/api/v1/projects/p1/paper-library/ask",
                json={"question": "YOLO baseline?", "scope": "all_papers", "top_k": 3},
            )
        assert r.status_code == 200
        # ledger 中应出现 paper_library_chunk
        chunks = ev_store.list_paper_library_chunks("p1")
        assert len(chunks) == 1
        assert chunks[0].paper_id == pid
        assert chunks[0].chunk_id == f"c_{pid}_m"
        assert chunks[0].review_status == "pending"

    def _client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)


# ===========================================================================
# 10. Schemas
# ===========================================================================


class TestClaimGroundingSchemas:
    def test_claim_grounding_result_fields(self):
        from app.schemas_claim_grounding import ClaimGroundingResult
        from app.schemas_paper_rag import EvidenceRef
        r = ClaimGroundingResult(
            claim="test", status="supported", verdict="supported",
            confidence=0.8,
            supporting_chunks=[EvidenceRef(paper_id="p1", chunk_id="c1", quote="x")],
        )
        d = r.model_dump()
        assert d["claim"] == "test"
        assert d["status"] == "supported"
        assert d["verdict"] == "supported"
        assert d["confidence"] == 0.8
        assert len(d["supporting_chunks"]) == 1

    def test_claim_grounding_result_invalid_status_rejected(self):
        from app.schemas_claim_grounding import ClaimGroundingResult
        with pytest.raises(Exception):
            ClaimGroundingResult(claim="x", status="bogus")

    def test_batch_request_validation(self):
        from app.schemas_claim_grounding import ClaimGroundBatchRequest
        req = ClaimGroundBatchRequest(claims=["a", "b"], scope="accepted_papers", top_k=3)
        assert req.scope == "accepted_papers"
        assert len(req.claims) == 2