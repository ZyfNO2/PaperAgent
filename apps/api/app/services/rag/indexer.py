"""Re4.5: TF-IDF indexer — pure Python, no numpy dependency.

Builds a term-document matrix from chunks, persists to JSON via atomic_write_json.
"""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any

from apps.api.app.services.run_state import atomic_write_json

_TOKEN_PATTERN = re.compile(r"[a-zA-Z]{2,}|[\u4e00-\u9fff]{2,}")


def _tokenize(text: str) -> list[str]:
    """Tokenize text: extract words (English >=2 chars + Chinese chars)."""
    return [t.lower() for t in _TOKEN_PATTERN.findall(text)]


def _build_vocabulary(chunks: list[dict[str, Any]]) -> dict[str, int]:
    """Build vocabulary with document frequency."""
    df: dict[str, int] = {}
    for chunk in chunks:
        tokens = set(_tokenize(chunk["text"]))
        for token in tokens:
            df[token] = df.get(token, 0) + 1
    return df


def _compute_tfidf(
    chunks: list[dict[str, Any]], vocabulary: dict[str, int]
) -> list[dict[str, Any]]:
    """Compute TF-IDF vectors for each chunk."""
    n_docs = len(chunks)
    vectors: list[dict[str, Any]] = []

    for chunk in chunks:
        tokens = _tokenize(chunk["text"])
        if not tokens:
            vectors.append({"chunk_id": chunk["chunk_id"], "terms": {}})
            continue

        tf: dict[str, int] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1

        tfidf: dict[str, float] = {}
        for term, freq in tf.items():
            tf_val = freq / len(tokens)
            df_val = vocabulary.get(term, 0)
            if df_val > 0:
                idf_val = math.log(n_docs / df_val)
                tfidf[term] = tf_val * idf_val

        vectors.append({"chunk_id": chunk["chunk_id"], "terms": tfidf})

    return vectors


def build_index(
    case_id: str,
    chunks: list[dict[str, Any]],
    source: str = "",
    case_dir: Path | None = None,
) -> dict[str, Any]:
    """Build TF-IDF index from chunks and persist to JSON."""
    if case_dir is None:
        case_dir = Path(f"tmp_re13_eval/{case_id}")

    for chunk in chunks:
        if "source" not in chunk:
            chunk["source"] = source
        chunk["case_id"] = case_id

    vocabulary = _build_vocabulary(chunks)
    tfidf_vectors = _compute_tfidf(chunks, vocabulary)

    index = {
        "case_id": case_id,
        "documents": chunks,
        "vocabulary": vocabulary,
        "tfidf_vectors": tfidf_vectors,
        "n_chunks": len(chunks),
        "n_terms": len(vocabulary),
        "created_at": time.time(),
        "source": source,
    }

    index_path = case_dir / "rag_index.json"
    atomic_write_json(index_path, index)

    return {
        "status": "ok",
        "case_id": case_id,
        "n_chunks": len(chunks),
        "n_terms": len(vocabulary),
        "index_path": str(index_path),
    }


def load_index(case_id: str, case_dir: Path | None = None) -> dict[str, Any] | None:
    """Load RAG index from disk."""
    if case_dir is None:
        case_dir = Path(f"tmp_re13_eval/{case_id}")
    index_path = case_dir / "rag_index.json"
    if not index_path.exists():
        return None
    return json.loads(index_path.read_text(encoding="utf-8"))


def merge_index(
    case_id: str,
    new_chunks: list[dict[str, Any]],
    source: str = "",
    case_dir: Path | None = None,
) -> dict[str, Any]:
    """Merge new chunks into existing RAG index.

    If no existing index, creates a new one (same as build_index).
    If existing index exists, appends chunks and rebuilds TF-IDF.
    """
    if case_dir is None:
        case_dir = Path(f"tmp_re13_eval/{case_id}")

    existing = load_index(case_id, case_dir)
    if existing is None:
        return build_index(case_id, new_chunks, source=source, case_dir=case_dir)

    existing_n = existing.get("n_chunks", 0)
    for i, chunk in enumerate(new_chunks):
        chunk["chunk_id"] = f"chunk-{existing_n + i}"
        chunk["source"] = chunk.get("source", source)
        chunk["case_id"] = case_id

    all_chunks = existing.get("documents", []) + new_chunks
    vocabulary = _build_vocabulary(all_chunks)
    tfidf_vectors = _compute_tfidf(all_chunks, vocabulary)

    prev_sources = existing.get("source", "")
    merged_source = f"{prev_sources}; {source}" if prev_sources else source

    index = {
        "case_id": case_id,
        "documents": all_chunks,
        "vocabulary": vocabulary,
        "tfidf_vectors": tfidf_vectors,
        "n_chunks": len(all_chunks),
        "n_terms": len(vocabulary),
        "created_at": existing.get("created_at", time.time()),
        "source": merged_source,
    }

    index_path = case_dir / "rag_index.json"
    atomic_write_json(index_path, index)

    return {
        "status": "ok",
        "case_id": case_id,
        "n_chunks": len(all_chunks),
        "n_new_chunks": len(new_chunks),
        "n_terms": len(vocabulary),
        "index_path": str(index_path),
    }
