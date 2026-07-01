"""Session 47: Paper indexer (SOP §3.2 + §11 Task 3).

落盘结构:
.runtime/paper_library/{project_id}/index/
├── manifest.json          # S46 已有, 本轮扩展加 embedding 字段
├── embeddings.jsonl       # 每行: {chunk_id, paper_id, vector: [...]}
└── chunks_index.json      # chunk_id -> {paper_id, section, text, chunk_type}

幂等: 已索引的 chunk 跳过 (除非 force=True)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from . import embedding, storage


def _index_dir(project_id: str) -> Path:
    paths = storage._project_paths(project_id)
    return paths["index"]


def _load_embeddings(project_id: str) -> dict[str, dict[str, Any]]:
    """读 embeddings.jsonl → {chunk_id: {paper_id, vector}}."""

    target = _index_dir(project_id) / "embeddings.jsonl"
    if not target.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    try:
        for line in target.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            out[d["chunk_id"]] = d
    except Exception:  # noqa: BLE001
        return {}
    return out


def _append_embeddings(project_id: str, entries: list[dict[str, Any]]) -> None:
    """追加 embeddings 到 jsonl (append-only, 启动时去重)."""

    target = _index_dir(project_id) / "embeddings.jsonl"
    # 直接 append (load_embeddings 时会按 chunk_id 去重, 重复写入后写入胜)
    with target.open("a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _load_chunks_index(project_id: str) -> dict[str, dict[str, Any]]:
    """读 chunks_index.json → {chunk_id: {paper_id, section, text, chunk_type}}."""

    target = _index_dir(project_id) / "chunks_index.json"
    if not target.exists():
        return {}
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_chunks_index(project_id: str, idx: dict[str, dict[str, Any]]) -> None:
    target = _index_dir(project_id) / "chunks_index.json"
    target.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")


def build_index(
    project_id: str,
    paper_ids: list[str] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """为指定 paper_ids (或全部) 建 embedding 索引.

    Returns:
        {
            "chunk_count": int,
            "indexed": int,  # 本次新写入的 chunk 数
            "skipped": int,  # 跳过 (已索引)
            "duration_ms": int,
            "paper_ids": [str, ...]
        }
    """

    start = time.perf_counter()
    paths = storage._project_paths(project_id)

    # 1) 收集目标 paper 的 chunks
    target_ids: list[str] = []
    if paper_ids:
        target_ids = list(paper_ids)
    else:
        target_ids = storage.list_paper_ids(project_id)

    all_chunks: list[Any] = []
    for pid in target_ids:
        chunks = storage.load_chunks(project_id, pid)
        all_chunks.extend(chunks)

    if not all_chunks:
        return {
            "chunk_count": 0,
            "indexed": 0,
            "skipped": 0,
            "duration_ms": int((time.perf_counter() - start) * 1000),
            "paper_ids": target_ids,
        }

    # 2) 读已有索引
    existing = _load_embeddings(project_id) if not force else {}
    chunks_index = {} if force else _load_chunks_index(project_id)

    # 3) 收集需要新建的 chunk
    new_chunks = [c for c in all_chunks if c.chunk_id not in existing]
    skipped = len(all_chunks) - len(new_chunks)

    if new_chunks:
        # 4) 重建 vocab (用 new_chunks + 已索引的, 保持一致)
        corpus = [c.text or "" for c in new_chunks]
        # 已索引的文本也算 (保持 vocab 稳定)
        for cidx, meta in chunks_index.items():
            if cidx not in {nc.chunk_id for nc in new_chunks}:
                corpus.append(meta.get("text", ""))
        vectors, _vocab = embedding.embed_corpus(corpus, top_n=256)

        # 5) 写 embeddings.jsonl (全量重写, 保证 vocab 一致)
        target = paths["index"] / "embeddings.jsonl"
        # 保留已索引的 (沿用旧 vector)
        all_entries: list[dict[str, Any]] = []
        # 先写已存在的 (非本次 new_chunks 的)
        new_ids = {nc.chunk_id for nc in new_chunks}
        for cid, edata in existing.items():
            if cid not in new_ids:
                all_entries.append(edata)
        # 再写新的 (按 new_chunks 顺序对齐)
        for i, c in enumerate(new_chunks):
            all_entries.append({
                "chunk_id": c.chunk_id,
                "paper_id": c.paper_id,
                "vector": vectors[i] if i < len(vectors) else [],
            })
        target.write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in all_entries) + "\n",
            encoding="utf-8",
        )

        # 6) 更新 chunks_index
        for i, c in enumerate(new_chunks):
            chunks_index[c.chunk_id] = {
                "paper_id": c.paper_id,
                "section_title": c.section_title or "",
                "section_path": c.section_path or [],
                "text": c.text or "",
                "chunk_type": c.chunk_type or "unknown",
                "page_start": c.page_start,
                "page_end": c.page_end,
                "token_count": c.token_count,
            }
        _save_chunks_index(project_id, chunks_index)

        # 7) 更新 manifest 中 paper 的 embedding_status
        for pid in target_ids:
            storage.update_manifest(
                project_id=project_id,
                paper_id=pid,
                record_path=str(paths["parsed"] / f"{pid}.json"),
                chunks_path=str(paths["chunks"] / f"{pid}_chunks.jsonl"),
                chunk_count=sum(1 for c in all_chunks if c.paper_id == pid),
                parse_status="parsed",
                source_mode="arxiv_download",  # 占位, manifest 已有不会覆盖
            )

    duration_ms = int((time.perf_counter() - start) * 1000)
    return {
        "chunk_count": len(all_chunks),
        "indexed": len(new_chunks),
        "skipped": skipped,
        "duration_ms": duration_ms,
        "paper_ids": target_ids,
    }


def load_index(project_id: str) -> dict[str, Any]:
    """读 embeddings + chunks_index, 返回统一 dict.

    Returns:
        {
            "vectors": {chunk_id: [float, ...]},
            "chunks": {chunk_id: {paper_id, section_title, text, ...}},
            "chunk_count": int
        }
    """

    embeddings = _load_embeddings(project_id)
    chunks_index = _load_chunks_index(project_id)
    vectors = {cid: edata.get("vector", []) for cid, edata in embeddings.items()}
    return {
        "vectors": vectors,
        "chunks": chunks_index,
        "chunk_count": len(vectors),
    }


def reset_index(project_id: str) -> None:
    """测试用: 清空该 project 的 index/ 下所有文件."""

    paths = storage._project_paths(project_id)
    idx = paths["index"]
    for fname in ("embeddings.jsonl", "chunks_index.json"):
        target = idx / fname
        if target.exists():
            target.unlink()


__all__ = [
    "build_index",
    "load_index",
    "reset_index",
]