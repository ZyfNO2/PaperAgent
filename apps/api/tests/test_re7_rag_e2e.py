"""Re7.6: RAG end-to-end HTTP test — validates feedback_bar + citation_valid via FastAPI TestClient."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _isolate_contract_registry():
    """Save/restore global contract registry to prevent cross-test pollution."""
    from apps.api.app.services.router.contracts import get_contract_registry
    reg = get_contract_registry()
    saved = dict(reg._contracts) if hasattr(reg, "_contracts") else {}
    saved_by_role = dict(reg._by_role) if hasattr(reg, "_by_role") else {}
    yield
    if hasattr(reg, "_contracts"):
        reg._contracts = saved
    if hasattr(reg, "_by_role"):
        reg._by_role = saved_by_role


@pytest.fixture
def app_client():
    from apps.api.app.main import app
    return TestClient(app)


@pytest.fixture
def case_with_index(tmp_path, monkeypatch):
    """Create a temporary case dir with a small RAG index."""
    case_id = "re76_rag_e2e"
    case_dir = tmp_path / f"tmp_re13_eval/{case_id}"
    case_dir.mkdir(parents=True, exist_ok=True)

    # Build a small index
    from apps.api.app.services.rag.indexer import build_index

    chunks = [
        {
            "chunk_id": "chunk-0",
            "text": "Transformer architecture uses self-attention mechanism for sequence modeling. "
                    "The attention weights are computed via scaled dot-product attention.",
            "source": "https://example.com/paper1.pdf",
            "page": 1,
            "paragraph": 2,
        },
        {
            "chunk_id": "chunk-1",
            "text": "Vision Transformer applies Transformer to image patches. "
                    "Images are split into fixed-size patches and linearly embedded.",
            "source": "https://example.com/paper1.pdf",
            "page": 3,
            "paragraph": 1,
        },
        {
            "chunk_id": "chunk-2",
            "text": "BERT uses bidirectional self-attention for pre-training language models. "
                    "It masks words and predicts them from context.",
            "source": "https://example.com/paper2.pdf",
            "page": 2,
            "paragraph": 4,
        },
    ]

    # Build index to tmp_path so it's isolated
    build_index(case_id, chunks, source="https://example.com/paper1.pdf",
                case_dir=case_dir)

    # Patch load_index to use our tmp case_dir
    from apps.api.app.services.rag import indexer as indexer_mod
    original_load = indexer_mod.load_index

    def patched_load(cid, cd=None):
        if cid == case_id:
            return original_load(cid, case_dir=case_dir)
        return original_load(cid, case_dir=cd)

    monkeypatch.setattr(indexer_mod, "load_index", patched_load)

    return case_id, case_dir


class TestRagE2EHTTP:
    """Test RAG Q&A through the ACP invoke endpoint."""

    def _invoke_rag(self, client, case_id, question):
        """Helper: invoke query_rag via ACP."""
        resp = client.post(
            "/api/v1/acp/invoke",
            json={
                "capability": "query_rag",
                "params": {
                    "case_id": case_id,
                    "question": question,
                },
            },
            headers={"X-ACP-Capability": "read"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # ACP wraps: {"success": True, "result": {...}}
        return body.get("result", body)

    def test_query_rag_returns_feedback_bar(self, app_client, case_with_index):
        """RAG answer must include feedback_bar with required fields."""
        case_id, _ = case_with_index
        result = self._invoke_rag(app_client, case_id, "What is self-attention mechanism?")

        fb = result.get("feedback_bar")
        assert fb is not None, "feedback_bar missing from RAG response"
        assert "artifact_id" in fb
        assert "idempotency_key" in fb
        assert "artifact_type" in fb
        assert fb["artifact_type"] == "rag_answer"
        assert "options" in fb
        assert len(fb["options"]) >= 3

    def test_query_rag_has_citation_valid(self, app_client, case_with_index):
        """RAG answer must include citation_valid flag."""
        case_id, _ = case_with_index
        result = self._invoke_rag(app_client, case_id, "How does Vision Transformer work?")

        assert "citation_valid" in result
        assert isinstance(result["citation_valid"], bool)

    def test_query_rag_has_cited_chunks(self, app_client, case_with_index):
        """RAG answer should have cited_chunks list."""
        case_id, _ = case_with_index
        result = self._invoke_rag(app_client, case_id, "What is BERT?")

        assert "cited_chunks" in result
        assert isinstance(result["cited_chunks"], list)

    def test_query_rag_abstention_on_no_index(self, app_client):
        """RAG should return error when no index exists for the case."""
        resp = app_client.post(
            "/api/v1/acp/invoke",
            json={
                "capability": "query_rag",
                "params": {
                    "case_id": "nonexistent_case_xyz",
                    "question": "What is attention?",
                },
            },
            headers={"X-ACP-Capability": "read"},
        )
        assert resp.status_code == 200
        body = resp.json()
        result = body.get("result", body)
        assert "error" in result
        assert "no RAG index" in result["error"]

    def test_query_rag_retrieved_chunks_present(self, app_client, case_with_index):
        """RAG response should include retrieved_chunks for transparency."""
        case_id, _ = case_with_index
        result = self._invoke_rag(app_client, case_id, "What is self-attention?")

        assert "retrieved_chunks" in result
        assert isinstance(result["retrieved_chunks"], list)

    def test_feedback_bar_idempotency_well_formed(self, app_client, case_with_index):
        """idempotency_key should be 24 hex chars (SHA-256 truncated)."""
        case_id, _ = case_with_index
        result = self._invoke_rag(app_client, case_id, "What is BERT?")

        fb = result.get("feedback_bar", {})
        assert len(fb.get("idempotency_key", "")) == 24

    def test_query_rag_has_artifact_id(self, app_client, case_with_index):
        """RAG answer should include artifact_id for feedback binding."""
        case_id, _ = case_with_index
        result = self._invoke_rag(app_client, case_id, "What is self-attention?")

        assert "artifact_id" in result
        assert result["artifact_id"].startswith("rag-")


class TestRAGQAContract:
    """Direct unit tests for RAG answer_question contract enforcement."""

    @pytest.fixture
    def small_index(self, tmp_path):
        from apps.api.app.services.rag.indexer import build_index, load_index

        chunks = [
            {
                "chunk_id": "chunk-0",
                "text": "Transformer architecture uses self-attention mechanism.",
                "source": "https://example.com/paper1.pdf",
                "page": 1,
                "paragraph": 1,
            },
            {
                "chunk_id": "chunk-1",
                "text": "Vision Transformer applies Transformer to image patches.",
                "source": "https://example.com/paper1.pdf",
                "page": 2,
                "paragraph": 1,
            },
        ]
        build_index("contract-test", chunks, source="https://example.com/paper1.pdf", case_dir=tmp_path)
        return load_index("contract-test", case_dir=tmp_path)

    def test_fake_citation_is_rejected(self, small_index, monkeypatch):
        """LLM citing a chunk_id not in retrieved index must be abstained."""
        from unittest.mock import patch
        from apps.api.app.services.rag.qa import answer_question

        with patch(
            "apps.api.app.services.llm_router.call_json",
            return_value={
                "answer": "The answer is fabricated.",
                "confidence": 0.9,
                "cited_chunks": ["chunk-999"],
            },
        ):
            result = answer_question(
                "What is self-attention?", small_index, case_id="contract-test"
            )

        assert result["abstain_reason"] is not None
        assert "not in the retrieved index" in result["abstain_reason"]
        assert result["citation_valid"] is False
        assert result["trace"]["n_citations"] == 1
        assert result["trace"]["n_valid_citations"] == 0

    def test_irrelevant_questions_mostly_abstain(self, small_index):
        """20 unrelated questions should trigger abstention for at least 19."""
        from apps.api.app.services.rag.qa import answer_question

        irrelevant = [
            "量子计算", "气候变化", "法国大革命", "比特币挖矿", "碳排放交易",
            "深度学习优化器", "神经网络剪枝", "图卷积网络", "强化学习奖励",
            "贝叶斯优化", "联邦学习", "自然语言推理", "知识图谱嵌入",
            "迁移学习", "多模态融合", "扩散模型", "Transformer 变体",
            "提示工程", "大模型幻觉", "推荐系统",
        ]
        abstained = 0
        for q in irrelevant:
            result = answer_question(q, small_index, case_id="contract-test")
            if result.get("abstain_reason"):
                abstained += 1
        assert abstained >= 19, f"only {abstained}/20 irrelevant questions abstained"

    def test_trace_fields_present(self, small_index, monkeypatch):
        """answer_question must return trace with top_score, n_citations, n_valid_citations."""
        from unittest.mock import patch
        from apps.api.app.services.rag.qa import answer_question

        with patch(
            "apps.api.app.services.llm_router.call_json",
            return_value={
                "answer": "Self-attention computes attention weights.",
                "confidence": 0.8,
                "cited_chunks": ["chunk-0"],
            },
        ):
            result = answer_question(
                "What is self-attention?", small_index, case_id="contract-test"
            )

        trace = result.get("trace", {})
        assert "top_score" in trace
        assert "n_citations" in trace
        assert "n_valid_citations" in trace
        assert "n_retrieved_chunks" in trace
        assert trace["n_citations"] == 1
        assert trace["n_valid_citations"] == 1


class TestFeedbackStoreFlow:
    """Feedback write / read / aggregate lifecycle."""

    def test_feedback_write_read_aggregate(self, tmp_path):
        from apps.api.app.services.feedback_store import FeedbackStore, FeedbackCreate

        store_path = tmp_path / "feedback.jsonl"
        store = FeedbackStore(str(store_path))

        fb = FeedbackCreate(
            case_id="case-42",
            idempotency_key="key-1",
            artifact_type="rag_answer",
            artifact_id="rag-abc123",
            verdict="unsupported",
            comment="citation missing",
        )
        record = store.save(fb)
        assert record.artifact_type == "rag_answer"

        # Idempotency: second save returns existing record
        record2 = store.save(fb)
        assert record2.feedback_id == record.feedback_id

        # Read back by artifact binding
        by_artifact = store.list_by_artifact("case-42", "rag_answer", "rag-abc123")
        assert len(by_artifact) == 1
        assert by_artifact[0].verdict == "unsupported"

        # Add another feedback for a different artifact
        fb2 = FeedbackCreate(
            case_id="case-42",
            idempotency_key="key-2",
            artifact_type="final_recommendation",
            artifact_id="rec-def456",
            verdict="incorrect",
        )
        store.save(fb2)

        summary = store.get_summary()
        assert summary.total == 2
        assert summary.by_verdict.get("unsupported") == 1
        assert summary.by_verdict.get("incorrect") == 1
        assert summary.by_artifact.get("rag_answer") == 1
        assert summary.by_artifact.get("final_recommendation") == 1
        assert summary.unsupported_incorrect == 2
