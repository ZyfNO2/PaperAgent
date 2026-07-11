"""Re4.5: TF-IDF retriever — cosine similarity ranking.

Pure Python, no numpy. Computes query vector, ranks chunks by cosine sim.
"""
from __future__ import annotations

import math
from typing import Any

from .indexer import _tokenize


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Cosine similarity between two sparse term->weight dicts."""
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(vec_a.get(t, 0) * vec_b.get(t, 0) for t in vec_a if t in vec_b)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve(
    query: str, index: dict[str, Any], top_k: int = 3
) -> list[dict[str, Any]]:
    """Retrieve top-K chunks for a query."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    n_docs = index["n_chunks"]
    vocab = index["vocabulary"]

    tf: dict[str, int] = {}
    for token in query_tokens:
        tf[token] = tf.get(token, 0) + 1

    query_vec: dict[str, float] = {}
    for term, freq in tf.items():
        df_val = vocab.get(term, 0)
        if df_val > 0 and n_docs > 0:
            idf_val = math.log(n_docs / df_val)
            query_vec[term] = (freq / len(query_tokens)) * idf_val

    scored: list[dict[str, Any]] = []
    for vec_entry in index["tfidf_vectors"]:
        score = _cosine_similarity(query_vec, vec_entry["terms"])
        if score > 0:
            chunk_id = vec_entry["chunk_id"]
            doc = next(
                (d for d in index["documents"] if d["chunk_id"] == chunk_id), None
            )
            if doc:
                scored.append(
                    {
                        "chunk_id": chunk_id,
                        "text": doc["text"],
                        "score": round(score, 4),
                        "source": doc.get("source", ""),
                        "start_char": doc.get("start_char", 0),
                    }
                )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
