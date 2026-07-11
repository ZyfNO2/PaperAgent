"""Re4.5: PDF extraction + chunking tests."""
from __future__ import annotations

from apps.api.app.services.rag.chunker import chunk_text
from apps.api.app.services.rag.pdf_extractor import _clean_text


class TestCleanText:
    def test_removes_page_numbers(self):
        text = "Some text\n\n12\n\nMore text"
        cleaned = _clean_text(text)
        assert "Some text" in cleaned
        assert "More text" in cleaned

    def test_normalizes_whitespace(self):
        text = "Hello    world\n\n\n\n\nBye"
        cleaned = _clean_text(text)
        assert "    " not in cleaned
        assert "\n\n\n" not in cleaned


class TestChunker:
    def test_empty_text_returns_empty(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_short_text_one_chunk(self):
        text = "This is a short paragraph."
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0]["chunk_id"] == "chunk-0"
        assert chunks[0]["text"] == text

    def test_long_text_multiple_chunks(self):
        para = "This is a paragraph. " * 30
        text = f"{para}\n\n{para}\n\n{para}"
        chunks = chunk_text(text, chunk_size=500, overlap=100)
        assert len(chunks) >= 2
        for c in chunks:
            assert c["chunk_id"].startswith("chunk-")
            assert "text" in c
            assert "start_char" in c
            assert "end_char" in c

    def test_chunks_have_overlap(self):
        para = "A" * 300 + ". "
        text = para * 10
        chunks = chunk_text(text, chunk_size=500, overlap=100)
        if len(chunks) >= 2:
            end_chunk0 = chunks[0]["text"][-50:]
            start_chunk1 = chunks[1]["text"][:50]
            assert any(c in start_chunk1 for c in end_chunk0[-20:])

    def test_chunk_ids_sequential(self):
        text = "\n\n".join([f"Paragraph {i}. " * 40 for i in range(5)])
        chunks = chunk_text(text, chunk_size=500, overlap=100)
        for i, c in enumerate(chunks):
            assert c["chunk_id"] == f"chunk-{i}"
