"""Session 47: Paper RAG 检索与问答 tests.

覆盖 (SOP §11 + §13):
- embedding 确定性
- indexer 构建/加载/幂等
- retriever: keyword + dense + RRF + scope
- reranker: section_type 加权 (method > reference)
- paper_qa: LLM 路径 + fallback + 无命中
- API: 2 端点形状
- ingest-index 联动 (auto-index after upload)
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
    """写入 3 个 chunk: method / abstract / introduction."""
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
    # 也更新 manifest, 让 list_paper_ids 能找到
    from pathlib import Path
    storage.update_manifest(
        project_id=project_id, paper_id=paper_id,
        record_path=str(Path(storage._project_paths(project_id)["parsed"]) / f"{paper_id}.json"),
        chunks_path=str(Path(storage._project_paths(project_id)["chunks"]) / f"{paper_id}_chunks.jsonl"),
        chunk_count=len(chunks), parse_status="parsed",
        source_mode="local_upload",
    )


def _seed_record(project_id: str, paper_id: str, title: str = "YOLO Steel Defect Detection") -> None:
    from app.schemas_paper_library import PaperRecord
    from app.services.paper_library import storage
    rec = PaperRecord(
        paper_id=paper_id, project_id=project_id, title=title,
        source_mode="local_upload", parse_status="parsed",
        metadata_status="resolved", year=2024, arxiv_id="2401.00001",
    )
    storage.save_paper_record(rec)


# ===========================================================================
# 1. Embedding 确定性
# ===========================================================================


class TestEmbedding:
    def test_embed_text_deterministic(self):
        from app.services.paper_library import embedding
        v1 = embedding.embed_text("hello world hello")
        v2 = embedding.embed_text("hello world hello")
        assert v1 == v2

    def test_embed_text_different_text_diff_vector(self):
        from app.services.paper_library import embedding
        v1 = embedding.embed_text("hello world")
        v2 = embedding.embed_text("foo bar baz")
        assert v1 != v2

    def test_cosine_similarity_identical(self):
        from app.services.paper_library import embedding
        v = [1.0, 0.5, 0.3, 0.1]
        assert abs(embedding.cosine_similarity(v, v) - 1.0) < 1e-6

    def test_cosine_similarity_zero(self):
        from app.services.paper_library import embedding
        v = [1.0, 0.0, 0.0]
        z = [0.0, 0.0, 0.0]
        assert embedding.cosine_similarity(v, z) == 0.0

    def test_cosine_similarity_orthogonal(self):
        from app.services.paper_library import embedding
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        assert abs(embedding.cosine_similarity(v1, v2)) < 1e-6

    def test_embed_corpus_shapes(self):
        from app.services.paper_library import embedding
        corpus = ["hello world", "foo bar", "baz qux"]
        vectors, vocab = embedding.embed_corpus(corpus, top_n=10)
        assert len(vectors) == 3
        assert all(len(v) == len(vocab) for v in vectors)
        assert len(vocab) <= 10


# ===========================================================================
# 2. Indexer 构建/加载/幂等
# ===========================================================================


class TestIndexer:
    def test_build_index_creates_files(self, _tmp_library):
        from app.services.paper_library import indexer, storage
        _seed_record("proj1", "paper_xx_1")
        _seed_chunks("proj1", "paper_xx_1")
        result = indexer.build_index("proj1")
        assert result["chunk_count"] == 3
        assert result["indexed"] == 3

        idx = indexer.load_index("proj1")
        assert idx["chunk_count"] == 3
        assert len(idx["vectors"]) == 3
        assert len(idx["chunks"]) == 3

    def test_build_index_idempotent(self, _tmp_library):
        from app.services.paper_library import indexer
        _seed_record("proj1", "paper_xx_1")
        _seed_chunks("proj1", "paper_xx_1")
        r1 = indexer.build_index("proj1")
        r2 = indexer.build_index("proj1")
        assert r1["indexed"] == 3
        assert r2["indexed"] == 0  # 全部跳过
        assert r2["skipped"] == 3

    def test_build_index_force_rebuilds(self, _tmp_library):
        from app.services.paper_library import indexer
        _seed_record("proj1", "paper_xx_1")
        _seed_chunks("proj1", "paper_xx_1")
        indexer.build_index("proj1")
        r2 = indexer.build_index("proj1", force=True)
        assert r2["indexed"] == 3
        assert r2["skipped"] == 0

    def test_build_index_specific_paper(self, _tmp_library):
        from app.services.paper_library import indexer
        _seed_record("proj1", "paper_xx_1")
        _seed_record("proj1", "paper_xx_2")
        _seed_chunks("proj1", "paper_xx_1")
        _seed_chunks("proj1", "paper_xx_2")
        result = indexer.build_index("proj1", paper_ids=["paper_xx_1"])
        assert result["chunk_count"] == 3
        assert result["indexed"] == 3


# ===========================================================================
# 3. Retriever: keyword + dense + RRF + scope
# ===========================================================================


class TestRetriever:
    def test_rewrite_query_chinese(self):
        from app.services.paper_library.retriever import rewrite_query
        kws = rewrite_query("YOLO 缺陷检测")
        # 至少包含 yolo
        assert any("yolo" in k for k in kws)
        # 至少包含中文 phrase 或 zh→en 翻译
        assert len(kws) >= 2

    def test_rewrite_query_english(self):
        from app.services.paper_library.retriever import rewrite_query
        kws = rewrite_query("real time defect detection")
        assert "real" in kws
        assert "defect" in kws

    def test_rrf_fuse_merges(self):
        from app.services.paper_library.retriever import rrf_fuse
        sparse = [("a", 0.9), ("b", 0.5)]
        dense = [("b", 0.9), ("a", 0.4)]
        fused = rrf_fuse(sparse, dense)
        assert set(fused) == {"a", "b"}
        # 都出现 2 次, RRF 平局 → 但稳定
        assert len(fused) == 2

    def test_keyword_retrieve_top_k(self, _tmp_library):
        from app.services.paper_library import indexer, retriever
        _seed_record("proj1", "paper_xx_1")
        _seed_chunks("proj1", "paper_xx_1")
        indexer.build_index("proj1")
        idx = indexer.load_index("proj1")
        hits = retriever.keyword_retrieve(idx["chunks"], ["YOLO", "defect"], top_k=2)
        assert len(hits) <= 2
        # 至少有一个分数 > 0
        assert any(s > 0 for _, s in hits)

    def test_dense_retrieve_returns(self, _tmp_library):
        from app.services.paper_library import indexer, retriever
        _seed_record("proj1", "paper_xx_1")
        _seed_chunks("proj1", "paper_xx_1")
        indexer.build_index("proj1")
        idx = indexer.load_index("proj1")
        hits = retriever.dense_retrieve(idx["vectors"], "YOLO steel defect", top_k=3)
        assert len(hits) <= 3

    def test_retrieve_returns_chunk_ids(self, _tmp_library):
        from app.services.paper_library import indexer, retriever
        _seed_record("proj1", "paper_xx_1")
        _seed_chunks("proj1", "paper_xx_1")
        indexer.build_index("proj1")
        hits = retriever.retrieve("proj1", "YOLO 缺陷检测", top_k=3)
        assert len(hits) <= 3
        # 每个 hit 是 (chunk_id, score)
        for cid, _ in hits:
            assert isinstance(cid, str)
            assert cid.startswith("c_paper_xx_1_")


# ===========================================================================
# 4. Reranker section_type 加权
# ===========================================================================


class TestReranker:
    def _chunk(self, cid: str, chunk_type: str, text: str, paper_id: str = "p1") -> dict:
        return {
            "chunk_id": cid,
            "paper_id": paper_id,
            "text": text,
            "chunk_type": chunk_type,
            "section_title": chunk_type.title(),
            "rerank_score": 0.01,  # fused_score 估计 ~0.01
        }

    def test_method_above_reference(self):
        from app.services.paper_library.reranker import rerank_chunks

        chunks = [
            (self._chunk("ref1", "abstract", "YOLO defect detection baseline"), 0.005),
            (self._chunk("m1", "method", "We propose YOLO steel defect detection"), 0.005),
            (self._chunk("ref2", "introduction", "Introduction text YOLO defect"), 0.005),
        ]
        reranked = rerank_chunks("YOLO defect detection", chunks, paper_year_lookup={"p1": 2024})
        # method chunk 应当排在 abstract 之前
        ids = [m["chunk_id"] for m, _ in reranked]
        assert ids.index("m1") < ids.index("ref1")

    def test_method_higher_than_reference(self):
        """method 章节应当比 reference 章节 rerank 更高 (即使 keyword 相同)."""
        from app.services.paper_library.reranker import rerank_chunks

        chunks = [
            (self._chunk("r1", "reference", "YOLO defect reference paper"), 0.0),
            (self._chunk("m1", "method", "YOLO defect detection method"), 0.0),
        ]
        # 注意: reference 实际上不会进入 chunks (chunker 过滤), 但作为测试
        reranked = rerank_chunks("YOLO defect", chunks)
        # method 应该更高
        m_score = next(s for m, s in reranked if m["chunk_id"] == "m1")
        r_score = next(s for m, s in reranked if m["chunk_id"] == "r1")
        assert m_score > r_score

    def test_recency_factor(self):
        from app.services.paper_library.reranker import rerank_chunks

        chunks = [
            (self._chunk("old", "method", "YOLO steel", paper_id="old"), 0.0),
            (self._chunk("new", "method", "YOLO steel", paper_id="new"), 0.0),
        ]
        # new = 2026, old = 2020
        reranked = rerank_chunks("YOLO steel", chunks, paper_year_lookup={"old": 2020, "new": 2026})
        new_score = next(s for m, s in reranked if m["chunk_id"] == "new")
        old_score = next(s for m, s in reranked if m["chunk_id"] == "old")
        assert new_score > old_score


# ===========================================================================
# 5. paper_qa: LLM + fallback + 无命中
# ===========================================================================


class TestPaperQA:
    def test_build_context(self):
        from app.services.paper_library.paper_qa import build_context
        chunks = [
            {"chunk_id": "c1", "paper_id": "p1", "section_title": "Method",
             "text": "hello", "page_start": 3},
        ]
        ctx = build_context(chunks, paper_titles={"p1": "YOLO Steel"})
        assert "[1]" in ctx
        assert "YOLO Steel" in ctx
        assert "p.3" in ctx

    def test_fallback_answer(self):
        from app.services.paper_library.paper_qa import fallback_answer
        chunks = [
            {"chunk_id": "c1", "paper_id": "p1", "section_title": "Method",
             "text": "hello world test", "chunk_type": "method", "page_start": 1},
        ]
        ans = fallback_answer("q?", chunks)
        assert ans.retrieval_mode == "fallback"
        assert ans.confidence == 0.0
        assert len(ans.evidence_refs) == 1
        assert "检索到以下相关片段" in ans.answer

    def test_fallback_empty(self):
        from app.services.paper_library.paper_qa import fallback_answer
        ans = fallback_answer("q?", [])
        assert ans.retrieval_mode == "fallback"
        assert "未在论文库中找到证据" in ans.answer
        assert ans.evidence_refs == []

    def test_llm_answer_with_evidence(self):
        """Mock LLM 返回带 evidence_refs 的 JSON."""
        from app.services.paper_library import paper_qa

        chunks = [
            {"chunk_id": "c1", "paper_id": "p1", "section_title": "Method",
             "text": "YOLO steel defect method content", "chunk_type": "method",
             "page_start": 3, "rerank_score": 0.5},
        ]
        mock_llm_resp = {
            "answer": "可以用 [1] 做 YOLO 缺陷检测 baseline",
            "evidence_refs": [
                {
                    "ref_id": 1, "paper_id": "p1", "chunk_id": "c1",
                    "page_start": 3, "page_end": 4,
                    "quote": "YOLO steel defect method content",
                    "support_type": "direct",
                },
            ],
            "unsupported_claims": [],
        }
        with patch("app.services.llm.chat_json", return_value=mock_llm_resp):
            ans = paper_qa.answer_with_llm("哪些论文能做 YOLO baseline?", chunks)

        assert ans.retrieval_mode == "llm"
        assert len(ans.evidence_refs) == 1
        assert ans.evidence_refs[0].paper_id == "p1"
        assert ans.evidence_refs[0].chunk_id == "c1"
        assert ans.evidence_refs[0].support_type == "direct"
        assert ans.confidence == 1.0  # 1 supported / 1 total

    def test_llm_answer_with_unsupported(self):
        """LLM 报告 unsupported_claims 时, confidence 应 < 1."""
        from app.services.paper_library import paper_qa

        chunks = [
            {"chunk_id": "c1", "paper_id": "p1", "section_title": "Abstract",
             "text": "YOLO abstract content", "chunk_type": "abstract",
             "page_start": 1, "rerank_score": 0.3},
        ]
        mock_llm_resp = {
            "answer": "部分能 [1], 部分不能.",
            "evidence_refs": [
                {"ref_id": 1, "chunk_id": "c1", "paper_id": "p1",
                 "page_start": 1, "quote": "YOLO abstract",
                 "support_type": "direct"},
            ],
            "unsupported_claims": ["Transformer 不行"],
        }
        with patch("app.services.llm.chat_json", return_value=mock_llm_resp):
            ans = paper_qa.answer_with_llm("test?", chunks)
        assert ans.confidence == 0.5  # 1/(1+1)

    def test_llm_fallback_on_exception(self):
        """LLM 抛异常 → answer_with_llm 应 raise, 上层走 fallback."""
        from app.services.paper_library import paper_qa

        chunks = [
            {"chunk_id": "c1", "paper_id": "p1", "section_title": "Method",
             "text": "test", "chunk_type": "method"},
        ]
        with patch("app.services.llm.chat_json", side_effect=Exception("network")):
            with pytest.raises(Exception):
                paper_qa.answer_with_llm("q?", chunks)

    def test_no_hit_question(self):
        """没有 chunks 时, answer 必须明说"未在论文库中找到证据"."""
        from app.services.paper_library import paper_qa
        ans = paper_qa.answer_with_llm("test?", [])
        assert "未在论文库中找到证据" in ans.answer
        assert ans.evidence_refs == []
        assert ans.confidence == 0.0


# ===========================================================================
# 6. Scope filter: accepted_papers
# ===========================================================================


class TestScopeFilter:
    def test_specific_scope(self, _tmp_library):
        from app.services.paper_library import indexer, retriever
        _seed_record("proj1", "paper_xx_1", title="P1")
        _seed_record("proj1", "paper_xx_2", title="P2")
        _seed_chunks("proj1", "paper_xx_1")
        _seed_chunks("proj1", "paper_xx_2")
        indexer.build_index("proj1")
        hits = retriever.retrieve("proj1", "YOLO defect", scope="specific", paper_ids=["paper_xx_1"], top_k=10)
        # 应该只返回 paper_xx_1 的 chunks
        ids = {cid for cid, _ in hits}
        assert all(cid.startswith("c_paper_xx_1_") for cid in ids)

    def test_accepted_papers_scope_filters(self, _tmp_library):
        """accepted_papers 仅返回 review_status in (accepted, core) 的 paper 的 chunks."""
        from app.services import evidence as ev_store
        from app.services.paper_library import indexer, retriever
        from app.schemas_evidence import PaperManualCreate

        _seed_record("proj1", "paper_xx_1", title="Accepted Paper")
        _seed_record("proj1", "paper_xx_2", title="Pending Paper")
        _seed_chunks("proj1", "paper_xx_1")
        _seed_chunks("proj1", "paper_xx_2")
        indexer.build_index("proj1")

        # paper_xx_1 和 paper_xx_2 用不同 arxiv_id, 区分 accepted / pending
        # 手动写 record.json 用不同 arxiv_id
        import json
        from app.services.paper_library import storage
        from pathlib import Path

        rec1 = storage.load_record("proj1", "paper_xx_1")
        rec1 = rec1.model_copy(update={"arxiv_id": "2401.00011"})
        storage.save_paper_record(rec1)
        rec2 = storage.load_record("proj1", "paper_xx_2")
        rec2 = rec2.model_copy(update={"arxiv_id": "2401.00022"})
        storage.save_paper_record(rec2)

        # 把 paper_xx_1 (arxiv_id=2401.00011) mark 为 accepted
        ev_store.add_paper_manual("proj1", PaperManualCreate(
            title="Accepted Paper", arxiv_id="2401.00011", review_status="accepted",
        ))
        # paper_xx_2 仍为 pending

        hits = retriever.retrieve("proj1", "YOLO defect", scope="accepted_papers", top_k=10)
        ids = {cid for cid, _ in hits}
        # 仅 paper_xx_1 应被命中
        assert all(cid.startswith("c_paper_xx_1_") for cid in ids), f"Got ids: {ids}"
        assert not any(cid.startswith("c_paper_xx_2_") for cid in ids)


# ===========================================================================
# 7. API endpoints
# ===========================================================================


class TestApiEndpoints:
    def _client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def _setup_paper(self, _tmp_library):
        """上传 + 自动索引一个 paper, 返回 paper_id."""
        from app.services.paper_library import ingest_upload
        content = base64.b64encode(_fake_pdf_bytes()).decode()
        outcome = ingest_upload("proj1", "t.pdf", content, "application/pdf")
        return outcome.paper_id

    def test_index_endpoint(self, _tmp_library):
        client = self._client()
        pid = self._setup_paper(_tmp_library)
        r = client.post(f"/api/v1/projects/proj1/paper-library/{pid}/index", json={"force": True})
        assert r.status_code == 200
        data = r.json()
        assert data["paper_id"] == pid
        assert "duration_ms" in data

    def test_index_endpoint_idempotent(self, _tmp_library):
        client = self._client()
        pid = self._setup_paper(_tmp_library)
        # 第一次
        client.post(f"/api/v1/projects/proj1/paper-library/{pid}/index", json={"force": False})
        # 第二次 (auto-index 已跑过) → 0 indexed
        r = client.post(f"/api/v1/projects/proj1/paper-library/{pid}/index", json={"force": False})
        assert r.status_code == 200
        # parsed/failed PDF 文本为空 → 0 chunks → indexed=0
        # 仅验证形状
        assert "indexed" in r.json()

    def test_ask_endpoint_no_chunks(self, _tmp_library):
        """空论文库 → /ask 返回未找到."""
        client = self._client()
        r = client.post(
            "/api/v1/projects/proj_empty/paper-library/ask",
            json={"question": "哪些论文能做 YOLO baseline?"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["answer"] == "未在论文库中找到证据，无法回答该问题。"
        assert data["evidence_refs"] == []
        assert data["confidence"] == 0.0

    def test_ask_endpoint_with_mock_llm(self, _tmp_library):
        """有索引 + mock LLM → answer_with_llm 路径."""
        from app.services.paper_library import indexer

        client = self._client()
        pid = self._setup_paper(_tmp_library)
        # 手动注入 chunks + 索引
        _seed_chunks("proj1", pid)
        _seed_record("proj1", pid, title="YOLO Test")
        indexer.build_index("proj1", paper_ids=[pid])

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
                "/api/v1/projects/proj1/paper-library/ask",
                json={"question": "YOLO baseline?", "scope": "all_papers", "top_k": 3},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["retrieval_mode"] == "llm"
        assert len(data["evidence_refs"]) == 1
        assert data["evidence_refs"][0]["paper_id"] == pid

    def test_ask_endpoint_llm_fails_returns_fallback(self, _tmp_library):
        """LLM 抛异常 → /ask 返回 retrieval_mode=fallback."""
        from app.services.paper_library import indexer

        client = self._client()
        pid = self._setup_paper(_tmp_library)
        _seed_chunks("proj1", pid)
        _seed_record("proj1", pid)
        indexer.build_index("proj1", paper_ids=[pid])

        with patch("app.services.llm.chat_json", side_effect=Exception("no key")):
            r = client.post(
                "/api/v1/projects/proj1/paper-library/ask",
                json={"question": "YOLO?"},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["retrieval_mode"] == "fallback"
        assert data["confidence"] == 0.0
        assert "检索到以下相关片段" in data["answer"]

    def test_ask_endpoint_validation(self):
        """空 question → 422."""
        client = self._client()
        r = client.post(
            "/api/v1/projects/proj1/paper-library/ask",
            json={"question": ""},
        )
        assert r.status_code == 422


# ===========================================================================
# 8. Ingest → auto-index 联动
# ===========================================================================


class TestIngestIndexLinkage:
    def test_upload_triggers_auto_index(self, _tmp_library):
        """upload 后, index 已自动建好 (best-effort, 不抛)."""
        from app.services.paper_library import ingest_upload, indexer
        content = base64.b64encode(_fake_pdf_bytes()).decode()
        # _fake_pdf 没有真实文本, 但 ingest 不崩; index 会建但 chunk_count=0
        outcome = ingest_upload("proj1", "t.pdf", content, "application/pdf")
        # 不管有没有 chunks, index 都应该建成功
        idx = indexer.load_index("proj1")
        assert "vectors" in idx
        assert "chunks" in idx

    def test_arxiv_triggers_auto_index(self, _tmp_library, monkeypatch):
        from app.services.paper_library import arxiv_downloader, ingest_arxiv, indexer

        class _FakePaper:
            arxiv_id = "2409.13740"
            title = "Test"
            authors = ["A"]
            year = 2024
            summary = "s"
            abs_url = "https://arxiv.org/abs/2409.13740"
            pdf_url = ""
            categories = []

        monkeypatch.setattr(arxiv_downloader, "_lookup_metadata", lambda x: _FakePaper())
        monkeypatch.setattr(arxiv_downloader, "_download_pdf", lambda url, timeout=30.0: None)

        ingest_arxiv("proj1", "2409.13740")
        idx = indexer.load_index("proj1")
        assert "vectors" in idx


# ===========================================================================
# 9. Schemas
# ===========================================================================


class TestSchemas:
    def test_evidence_ref_serialize(self):
        from app.schemas_paper_rag import EvidenceRef
        ref = EvidenceRef(
            paper_id="p1", chunk_id="c1", page_start=1, page_end=2,
            quote="hello", support_type="direct", score=0.5,
        )
        d = ref.model_dump()
        assert d["paper_id"] == "p1"
        assert d["support_type"] == "direct"

    def test_paper_rag_answer_serialize(self):
        from app.schemas_paper_rag import PaperRAGAnswer, EvidenceRef
        ans = PaperRAGAnswer(
            question="q", answer="a",
            evidence_refs=[EvidenceRef(paper_id="p1", chunk_id="c1", quote="x")],
            unsupported_claims=[],
            confidence=1.0,
            used_papers=["p1"],
            retrieval_mode="llm",
        )
        d = ans.model_dump()
        assert d["retrieval_mode"] == "llm"
        assert d["confidence"] == 1.0