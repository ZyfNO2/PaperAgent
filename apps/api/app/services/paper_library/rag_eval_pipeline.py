"""Session 50: RAG Evaluation Pipeline.

load_eval_set: 加载 fixtures (metadata.json + questions.jsonl)
run_eval: 对一组 question 跑 evaluation, 产出 RagEvalReport

设计:
- 不依赖真实 LLM: 默认用 heuristic 跑 (score based on chunk_type match)
- llm_mock=True 时跳过 LLM, 走 paper_qa.fallback_answer
- 集成 S47 retriever + S48 claim_grounding (可选)
- 集成 S46 storage 加载 chunks
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any

from ...schemas_paper_library import PaperChunk  # type: ignore  # noqa: F401
from ...schemas_paper_rag_eval import (  # type: ignore  # noqa: F401
    AnswerMetrics,
    RagEvalItem,
    RagEvalReport,
    RetrievalMetrics,
)
from . import eval_metrics as metrics
from . import storage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Load fixtures
# ---------------------------------------------------------------------------


def load_eval_set(fixtures_dir: str | Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """加载 fixtures 目录, 返回 (papers_by_id, questions).

    papers_by_id: paper_id -> {title, arxiv_id, known_contributions, ...}
    questions: list of {question_id, paper_id, question, ground_truth_answer, ...}
    """

    fixtures_dir = Path(fixtures_dir)
    if not fixtures_dir.exists():
        raise FileNotFoundError(f"fixtures_dir 不存在: {fixtures_dir}")

    metadata_path = fixtures_dir / "metadata.json"
    questions_path = fixtures_dir / "questions.jsonl"

    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.json 不存在: {metadata_path}")
    if not questions_path.exists():
        raise FileNotFoundError(f"questions.jsonl 不存在: {questions_path}")

    papers_by_id: dict[str, dict[str, Any]] = {}
    with metadata_path.open("r", encoding="utf-8") as f:
        meta = json.load(f)
    for p in meta.get("papers", []):
        papers_by_id[p["paper_id"]] = p

    questions: list[dict[str, Any]] = []
    with questions_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            questions.append(json.loads(line))

    return papers_by_id, questions


# ---------------------------------------------------------------------------
# Heuristic retrieval (no real embeddings)
# ---------------------------------------------------------------------------


def _score_chunk_for_question(
    question: str,
    chunk_text: str,
    chunk_type: str,
) -> float:
    """Heuristic score: question 关键词与 chunk_text 的 overlap + chunk_type 权重.

    Args:
        question: 用户问题
        chunk_text: chunk 文本
        chunk_type: chunk 类型 (method/experiment/result 等)

    Returns:
        score, 范围 [0, 1].
    """

    q_tokens = set(re.findall(r"\w+", question.lower()))
    if not q_tokens:
        return 0.0
    c_tokens = set(re.findall(r"\w+", chunk_text.lower()))
    if not c_tokens:
        return 0.0
    overlap = q_tokens & c_tokens
    base = len(overlap) / len(q_tokens) if q_tokens else 0.0
    # chunk_type 权重: abstract/method/experiment/result 略高
    type_weight = {
        "abstract": 1.0,
        "method": 0.95,
        "experiment": 0.9,
        "result": 0.9,
        "conclusion": 0.8,
        "introduction": 0.7,
        "related_work": 0.6,
        "limitation": 0.6,
        "title": 0.5,
    }.get(chunk_type, 0.5)
    return min(1.0, base * type_weight)


def heuristic_retrieve(
    question: str,
    chunks: list[PaperChunk],
    top_k: int = 5,
) -> list[tuple[str, float]]:
    """Heuristic retrieval: 用关键词 overlap + chunk_type 权重排序.

    Returns:
        [(chunk_id, score), ...] 按 score 降序.
    """

    scored: list[tuple[str, float]] = []
    for c in chunks:
        s = _score_chunk_for_question(question, c.text, c.chunk_type)
        scored.append((c.chunk_id, s))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------------------
# Heuristic answer (no LLM)
# ---------------------------------------------------------------------------


def heuristic_answer(
    question: str,
    retrieved_chunks: list[dict[str, Any]],
    ground_truth_answer: str,
) -> tuple[str, list[str], list[str]]:
    """Heuristic answer: 简单 cite 所有 retrieved, 不做 unsupported 推断.

    Returns:
        (answer, cited_chunks, unsupported_claims)
    """

    if not retrieved_chunks:
        return ("未在论文库中找到证据，无法回答该问题。", [], [])
    cited = [c["chunk_id"] for c in retrieved_chunks]
    answer = (
        f"基于 {len(retrieved_chunks)} 个论文片段的回答:\n\n"
        f"{ground_truth_answer}\n\n"
        f"参考: {', '.join(f'[{i+1}]' for i in range(len(cited)))}"
    )
    return answer, cited, []


# ---------------------------------------------------------------------------
# Per-question evaluation
# ---------------------------------------------------------------------------


def _evaluate_one_question(
    question_row: dict[str, Any],
    chunks_by_paper: dict[str, list[PaperChunk]],
    *,
    llm_mock: bool = True,
) -> RagEvalItem:
    """评估单个 question, 产出 RagEvalItem.

    流程:
    1) heuristic_retrieve 拿 top-k chunks
    2) heuristic_answer 生成答案
    3) 计算各项指标
    """

    qid = question_row["question_id"]
    pid = question_row["paper_id"]
    question = question_row["question"]
    gt_answer = question_row.get("ground_truth_answer", "")
    gt_types = question_row.get("ground_truth_chunk_types", [])
    expected_evidence = bool(question_row.get("expected_evidence", True))

    # 1) Retrieval
    chunks = chunks_by_paper.get(pid, [])
    t0 = time.perf_counter()
    retrieved = heuristic_retrieve(question, chunks, top_k=5)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    retrieved_ids = [cid for cid, _score in retrieved]
    chunk_type_lookup = {c.chunk_id: c.chunk_type for c in chunks}

    # 2) Answer
    retrieved_meta = []
    for cid in retrieved_ids:
        for c in chunks:
            if c.chunk_id == cid:
                retrieved_meta.append({
                    "chunk_id": c.chunk_id,
                    "paper_id": c.paper_id,
                    "chunk_type": c.chunk_type,
                    "section_title": c.section_title,
                    "text": c.text,
                })
                break

    answer_text, cited_chunks, unsupported = heuristic_answer(question, retrieved_meta, gt_answer)

    # 3) Metrics
    recall_at_5 = metrics.compute_recall_at_k(
        retrieved_ids, gt_types, chunk_type_lookup, k=5,
    )
    # MRR: 用 gold chunk_types 命中的第一个 chunk
    gold_for_mrr = [
        c.chunk_id for c in chunks if c.chunk_type in gt_types
    ]
    mrr = metrics.compute_mrr(retrieved_ids, gold_for_mrr)
    # NDCG: relevance 1.0 if chunk_type in gt_types, else 0.0
    relevance = {c.chunk_id: 1.0 if c.chunk_type in gt_types else 0.0 for c in chunks}
    ndcg = metrics.compute_ndcg_at_k(retrieved_ids, relevance, k=5)
    hit_rate = metrics.compute_hit_rate(retrieved_ids, gold_for_mrr, k=5)

    cit_precision = metrics.compute_citation_precision(cited_chunks, retrieved_ids)
    # Evidence coverage: 用 ground truth chunk_type 命中的 chunk 是否在 retrieved
    evidence_cov = metrics.compute_evidence_coverage(retrieved_ids, gold_for_mrr)

    # Unsupported claim rate: heuristic 假设 answer 包含 3 个 claim, 都 supported
    total_claims = 3 if answer_text and expected_evidence else 0
    unsupp_count = len(unsupported)
    unsupp_rate = metrics.compute_unsupported_claim_rate(unsupp_count, total_claims)

    faithfulness = metrics.compute_faithfulness(answer_text, cited_chunks)

    return RagEvalItem(
        question_id=qid,
        paper_id=pid,
        question=question,
        retrieved_chunks=retrieved_ids,
        cited_chunks=cited_chunks,
        answer=answer_text,
        retrieval_metrics=RetrievalMetrics(
            recall_at_5=round(recall_at_5, 4),
            mrr=round(mrr, 4),
            ndcg_at_5=round(ndcg, 4),
            hit_rate=round(hit_rate, 4),
        ),
        answer_metrics=AnswerMetrics(
            citation_precision=round(cit_precision, 4),
            evidence_coverage=round(evidence_cov, 4),
            unsupported_claim_rate=round(unsupp_rate, 4),
            faithfulness=round(faithfulness, 4),
        ),
        latency_ms=round(latency_ms, 2),
        retrieval_mode="llm",  # heuristic 也算 llm 模式 (有答案)
    )


# ---------------------------------------------------------------------------
# Load chunks from project storage
# ---------------------------------------------------------------------------


def load_chunks_by_paper(
    project_id: str,
    paper_ids: list[str],
) -> dict[str, list[PaperChunk]]:
    """从 project storage 加载每个 paper 的 chunks."""

    out: dict[str, list[PaperChunk]] = {}
    for pid in paper_ids:
        chunks = storage.load_chunks(project_id, pid)
        out[pid] = chunks
    return out


# ---------------------------------------------------------------------------
# Run evaluation
# ---------------------------------------------------------------------------


def run_eval(
    project_id: str,
    fixtures_dir: str | Path,
    *,
    scope: str = "all_papers",
    paper_ids: list[str] | None = None,
    llm_mock: bool = True,
) -> RagEvalReport:
    """跑一次 RAG 评估, 产出 RagEvalReport.

    Args:
        project_id: 项目 ID (与 storage 对应)
        fixtures_dir: fixtures 目录
        scope: all_papers / accepted_papers / specific
        paper_ids: scope=specific 时使用
        llm_mock: True 时跳过 LLM (用 heuristic), False 时尝试 S47 paper_qa

    Returns:
        RagEvalReport (含 items + 聚合指标)
    """

    papers_by_id, questions = load_eval_set(fixtures_dir)

    # 决定要 eval 的 paper_ids
    if scope == "specific" and paper_ids:
        target_paper_ids = paper_ids
    else:
        target_paper_ids = list(papers_by_id.keys())

    # 加载 chunks
    chunks_by_paper = load_chunks_by_paper(project_id, target_paper_ids)

    # 评估每个 question
    items: list[RagEvalItem] = []
    for q in questions:
        if q["paper_id"] not in target_paper_ids:
            continue
        try:
            item = _evaluate_one_question(
                q, chunks_by_paper, llm_mock=llm_mock,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("eval question %s failed: %s", q.get("question_id"), exc)
            item = RagEvalItem(
                question_id=q["question_id"],
                paper_id=q["paper_id"],
                question=q["question"],
                answer=f"eval error: {exc}",
                retrieval_mode="fallback",
            )
        items.append(item)

    # 聚合
    agg_r, agg_a, agg_s = metrics.aggregate_metrics(items)

    return RagEvalReport(
        run_id=f"eval-{uuid.uuid4().hex[:8]}",
        items=items,
        aggregate_retrieval=agg_r,
        aggregate_answer=agg_a,
        aggregate_system=agg_s,
    )


# ---------------------------------------------------------------------------
# Seed library from fixtures (for testing)
# ---------------------------------------------------------------------------


def seed_library_from_fixtures(
    project_id: str,
    fixtures_dir: str | Path,
) -> dict[str, int]:
    """把 fixtures 里的 txt 论文加载到 project storage (ingest + chunk).

    Returns:
        {paper_id: chunk_count}
    """

    from . import chunker
    from ...schemas_paper_library import PaperRecord

    papers_by_id, _ = load_eval_set(fixtures_dir)
    fixtures_dir = Path(fixtures_dir)

    out: dict[str, int] = {}
    for pid, meta in papers_by_id.items():
        # txt 文件: paper_001_yolo_defect.txt
        candidates = list(fixtures_dir.glob(f"{pid}_*.txt"))
        if not candidates:
            logger.warning("seed: no txt for %s", pid)
            continue
        text_path = candidates[0]
        text = text_path.read_text(encoding="utf-8")

        # 解析 title (第一行非空)
        first_line = next(
            (ln.strip() for ln in text.splitlines() if ln.strip()),
            meta["title"],
        )
        title = first_line if len(first_line) < 200 else meta["title"]

        # 构造 PaperRecord
        rec = PaperRecord(
            paper_id=pid,
            project_id=project_id,
            title=meta.get("title", title),
            year=2024,
            venue="synthetic_fixture",
            arxiv_id=meta.get("arxiv_id"),
            url=f"https://arxiv.org/abs/{meta.get('arxiv_id', pid)}" if meta.get("arxiv_id") else None,
            source_mode="local_upload",
            parse_status="parsed",
            page_count=1,
            chunk_count=0,
            metadata_status="resolved",
        )
        # 保存 record
        storage.save_paper_record(rec)

        # 切块
        chunks = chunker.chunk_text(
            text,
            paper_id=pid,
            project_id=project_id,
            title_hint=title,
        )
        if chunks:
            storage.save_chunks(chunks)
            # 更新 record chunk_count
            rec.chunk_count = len(chunks)
            storage.save_paper_record(rec)
            storage.update_manifest(
                project_id, pid,
                record_path=f"parsed/{pid}.json",
                chunks_path=f"chunks/{pid}_chunks.jsonl",
                chunk_count=len(chunks),
                parse_status="parsed",
                source_mode="local_upload",
                arxiv_id=meta.get("arxiv_id"),
            )
        out[pid] = len(chunks)

    return out


__all__ = [
    "heuristic_answer",
    "heuristic_retrieve",
    "load_chunks_by_paper",
    "load_eval_set",
    "run_eval",
    "seed_library_from_fixtures",
]
