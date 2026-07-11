"""Re4.6: Multi-document RAG merge index tests."""
from __future__ import annotations

from pathlib import Path

from apps.api.app.services.rag.indexer import build_index, load_index, merge_index


class TestMergeIndex:
    def test_merge_creates_new_if_no_existing(self, tmp_path: Path):
        """merge_index with no existing index should create new."""
        chunks = [{"text": "YOLO detection", "chunk_id": "chunk-0"}]
        result = merge_index("test", chunks, source="url1", case_dir=tmp_path / "test")
        assert result["status"] == "ok"
        assert result["n_chunks"] == 1

    def test_merge_appends_to_existing(self, tmp_path: Path):
        """merge_index should append to existing index."""
        chunks1 = [{"text": "YOLO detection model", "chunk_id": "chunk-0"}]
        build_index("test2", chunks1, source="url1", case_dir=tmp_path / "test2")

        chunks2 = [{"text": "Dataset NEU-DET", "chunk_id": "chunk-0"}]
        result = merge_index("test2", chunks2, source="url2", case_dir=tmp_path / "test2")
        assert result["status"] == "ok"
        assert result["n_chunks"] == 2
        assert result["n_new_chunks"] == 1

        loaded = load_index("test2", case_dir=tmp_path / "test2")
        assert loaded["n_chunks"] == 2
        sources = [d["source"] for d in loaded["documents"]]
        assert "url1" in sources
        assert "url2" in sources

    def test_merge_rebuilds_tfidf(self, tmp_path: Path):
        """Merge should rebuild TF-IDF with updated IDF."""
        chunks1 = [{"text": "YOLO YOLO detection", "chunk_id": "chunk-0"}]
        build_index("test3", chunks1, source="url1", case_dir=tmp_path / "test3")

        chunks2 = [{"text": "Transformer architecture", "chunk_id": "chunk-0"}]
        merge_index("test3", chunks2, source="url2", case_dir=tmp_path / "test3")

        loaded = load_index("test3", case_dir=tmp_path / "test3")
        assert len(loaded["tfidf_vectors"]) == 2
        assert "yolo" in loaded["vocabulary"]
        assert "transformer" in loaded["vocabulary"]

    def test_merge_chunk_ids_unique(self, tmp_path: Path):
        """Merged chunks should have unique IDs."""
        chunks1 = [{"text": "first document", "chunk_id": "chunk-0"}]
        build_index("test4", chunks1, case_dir=tmp_path / "test4")

        chunks2 = [{"text": "second document", "chunk_id": "chunk-0"}]
        merge_index("test4", chunks2, case_dir=tmp_path / "test4")

        loaded = load_index("test4", case_dir=tmp_path / "test4")
        ids = [d["chunk_id"] for d in loaded["documents"]]
        assert len(ids) == len(set(ids))
