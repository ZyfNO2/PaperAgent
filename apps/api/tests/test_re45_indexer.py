"""Re4.5: TF-IDF indexer tests."""
from __future__ import annotations

from pathlib import Path

from apps.api.app.services.rag.indexer import (
    _build_vocabulary,
    _compute_tfidf,
    _tokenize,
    build_index,
    load_index,
)


class TestTokenizer:
    def test_english(self):
        tokens = _tokenize("YOLO object detection")
        assert "yolo" in tokens
        assert "object" in tokens
        assert "detection" in tokens

    def test_chinese(self):
        tokens = _tokenize("钢材表面缺陷检测")
        assert len(tokens) > 0

    def test_mixed(self):
        tokens = _tokenize("基于YOLO的检测 method")
        assert "yolo" in tokens
        assert "method" in tokens

    def test_short_words_filtered(self):
        tokens = _tokenize("a I am an")
        # 2+ char words pass; single chars are filtered
        assert "a" not in tokens
        assert "I" not in tokens or "i" not in tokens


class TestVocabulary:
    def test_doc_frequency(self):
        chunks = [
            {"text": "YOLO detection", "chunk_id": "c0"},
            {"text": "YOLO classification", "chunk_id": "c1"},
        ]
        vocab = _build_vocabulary(chunks)
        assert vocab["yolo"] == 2
        assert vocab["detection"] == 1
        assert vocab["classification"] == 1


class TestTfIdf:
    def test_vectors_have_terms(self):
        chunks = [{"text": "YOLO detection model", "chunk_id": "c0"}]
        vocab = _build_vocabulary(chunks)
        vectors = _compute_tfidf(chunks, vocab)
        assert len(vectors) == 1
        assert "yolo" in vectors[0]["terms"]

    def test_empty_chunk(self):
        chunks = [{"text": "", "chunk_id": "c0"}]
        vocab = _build_vocabulary(chunks)
        vectors = _compute_tfidf(chunks, vocab)
        assert vectors[0]["terms"] == {}


class TestBuildLoadIndex:
    def test_build_and_load(self, tmp_path: Path):
        chunks = [
            {"text": "YOLO for steel defect detection", "chunk_id": "chunk-0"},
            {"text": "Dataset NEU-DET for training", "chunk_id": "chunk-1"},
        ]
        result = build_index(
            "test-case", chunks, source="test.pdf", case_dir=tmp_path / "test-case"
        )
        assert result["status"] == "ok"
        assert result["n_chunks"] == 2

        loaded = load_index("test-case", case_dir=tmp_path / "test-case")
        assert loaded is not None
        assert loaded["n_chunks"] == 2
        assert loaded["source"] == "test.pdf"
        assert len(loaded["documents"]) == 2
        assert len(loaded["tfidf_vectors"]) == 2

    def test_load_nonexistent(self, tmp_path: Path):
        loaded = load_index("nonexistent", case_dir=tmp_path)
        assert loaded is None
