"""Re4.5: RAG question answering — LLM generation with chunk context.

Uses DeepSeek (via OpenCode proxy) to generate answers grounded in retrieved chunks.
"""
from __future__ import annotations

import logging
from typing import Any

from .retriever import retrieve

logger = logging.getLogger(__name__)

QA_SYSTEM = (
    "你是学术论文问答助手。根据提供的论文片段回答问题。"
    "每个答案必须引用来源片段编号（如 [chunk-0]）。"
    "如果片段中没有相关信息，回答\"未在已索引文档中找到相关信息\"。"
    "只输出JSON。"
)

QA_TEMPLATE = """问题: {question}

相关论文片段:
{context}

请基于上述片段回答问题。输出JSON:
{{"answer": "回答内容（需引用 [chunk-N]）", "confidence": 0.0-1.0, "cited_chunks": ["chunk-0", ...]}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def answer_question(
    question: str,
    index: dict[str, Any],
    case_id: str,
    top_k: int = 3,
) -> dict[str, Any]:
    """Answer a question using RAG."""
    chunks = retrieve(question, index, top_k=top_k)

    if not chunks:
        return {
            "answer": "未在已索引文档中找到相关信息",
            "confidence": 0.0,
            "cited_chunks": [],
            "retrieved_chunks": [],
            "case_id": case_id,
        }

    context_parts: list[str] = []
    for c in chunks:
        context_parts.append(
            f"[{c['chunk_id']}] (score={c['score']})\n{c['text'][:500]}"
        )
    context = "\n\n".join(context_parts)

    try:
        from apps.api.app.services import llm_router

        prompt = QA_TEMPLATE.format(question=question[:500], context=context[:3000])
        result = llm_router.call_json(
            prompt,
            system=QA_SYSTEM,
            profile="fast_json",
            max_tokens=1000,
            expected="dict",
            timeout=30,
        )
        answer = result.get("answer", "")
        confidence = float(result.get("confidence", 0.5))
        cited = result.get("cited_chunks", [])
    except Exception as exc:
        logger.warning("RAG QA LLM failed: %s — fallback to retrieval only", exc)
        answer = f"基于检索结果（LLM 不可用）：{chunks[0]['text'][:200]}"
        confidence = 0.3
        cited = [chunks[0]["chunk_id"]]

    return {
        "answer": answer,
        "confidence": confidence,
        "cited_chunks": cited,
        "retrieved_chunks": [
            {
                "chunk_id": c["chunk_id"],
                "score": c["score"],
                "text": c["text"][:200],
                "source": c["source"],
            }
            for c in chunks
        ],
        "case_id": case_id,
    }
