"""Re4.5: Retriever + QA tests."""
from __future__ import annotations

from apps.api.app.services.rag.indexer import build_index, load_index
from apps.api.app.services.rag.retriever import _cosine_similarity, retrieve


class TestCosineSimilarity:
    def test_identical_vectors(self):
        vec = {"a": 1.0, "b": 2.0}
        assert abs(_cosine_similarity(vec, vec) - 1.0) < 1e-9

    def test_orthogonal_vectors(self):
        a = {"x": 1.0}
        b = {"y": 1.0}
        assert _cosine_similarity(a, b) == 0.0

    def test_empty_vectors(self):
        assert _cosine_similarity({}, {"a": 1.0}) == 0.0


class TestRetrieve:
    def test_retrieve_returns_relevant(self, tmp_path):
        chunks = [
            {"text": "YOLO object detection model for real-time inference", "chunk_id": "c0"},
            {"text": "Dataset NEU-DET contains steel surface defect images", "chunk_id": "c1"},
            {"text": "Transformer architecture for NLP tasks", "chunk_id": "c2"},
        ]
        build_index("test", chunks, case_dir=tmp_path / "test")
        index = load_index("test", case_dir=tmp_path / "test")

        results = retrieve("steel defect detection dataset", index, top_k=2)
        assert len(results) > 0
        assert len(results) <= 2
        top_ids = [r["chunk_id"] for r in results]
        assert "c1" in top_ids
        assert "c2" not in top_ids

    def test_retrieve_empty_query(self, tmp_path):
        chunks = [{"text": "some text", "chunk_id": "c0"}]
        build_index("test2", chunks, case_dir=tmp_path / "test2")
        index = load_index("test2", case_dir=tmp_path / "test2")
        results = retrieve("", index)
        assert results == []

    def test_retrieve_no_match(self, tmp_path):
        chunks = [{"text": "abc xyz", "chunk_id": "c0"}]
        build_index("test3", chunks, case_dir=tmp_path / "test3")
        index = load_index("test3", case_dir=tmp_path / "test3")
        results = retrieve("completely different topic qwerty", index)
        assert isinstance(results, list)
