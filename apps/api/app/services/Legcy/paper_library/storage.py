"""Paper Library storage (Session 46).

落盘 .runtime/paper_library/{project_id}/
  ├── raw/{arxiv_id_or_sha8}.pdf
  ├── parsed/{paper_id}.json
  ├── chunks/{paper_id}_chunks.jsonl
  └── index/manifest.json

复用 materials/storage 的 sanitize + check_allowed, 但目录不同.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from pathlib import Path
from typing import Any

from ...schemas_paper_library import PaperChunk, PaperRecord


# ---------- 根目录 ---------- #


def _library_root() -> Path:
    """每次读 env, 方便测试切换."""

    return Path(os.environ.get("PAPERAGENT_PAPER_LIBRARY_DIR", ".runtime/paper_library"))


def _safe_project(project_id: str) -> str:
    return re.sub(r"[^\w\-]", "_", project_id)


# ---------- 落盘 helper ---------- #


def _project_paths(project_id: str) -> dict[str, Path]:
    root = _library_root() / _safe_project(project_id)
    paths = {
        "root": root,
        "raw": root / "raw",
        "parsed": root / "parsed",
        "chunks": root / "chunks",
        "index": root / "index",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths


def save_raw_pdf(project_id: str, key: str, data: bytes) -> str:
    """保存原始 PDF bytes; key 一般是 arxiv_id 或 sha256 前 8 位."""

    paths = _project_paths(project_id)
    safe_key = re.sub(r"[^\w\-\.]", "_", key)[:64] or f"file_{uuid.uuid4().hex[:8]}"
    target = paths["raw"] / f"{safe_key}.pdf"
    target.write_bytes(data)
    return str(target)


def save_paper_record(record: PaperRecord) -> str:
    """保存 PaperRecord 到 parsed/{paper_id}.json."""

    paths = _project_paths(record.project_id)
    target = paths["parsed"] / f"{record.paper_id}.json"
    target.write_text(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(target)


def save_chunks(chunks: list[PaperChunk]) -> str:
    """保存 chunks 到 chunks/{paper_id}_chunks.jsonl, 返回路径."""

    if not chunks:
        return ""
    paths = _project_paths(chunks[0].project_id)
    target = paths["chunks"] / f"{chunks[0].paper_id}_chunks.jsonl"
    with target.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.model_dump(mode="json"), ensure_ascii=False) + "\n")
    return str(target)


# ---------- manifest ---------- #


_MANIFEST_LOCK = threading.RLock()


def _load_manifest(project_id: str) -> dict[str, Any]:
    paths = _project_paths(project_id)
    mf = paths["index"] / "manifest.json"
    if not mf.exists():
        return {"project_id": project_id, "papers": {}}
    try:
        return json.loads(mf.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"project_id": project_id, "papers": {}}


def _save_manifest(project_id: str, mf: dict[str, Any]) -> str:
    paths = _project_paths(project_id)
    target = paths["index"] / "manifest.json"
    target.write_text(json.dumps(mf, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(target)


def update_manifest(
    project_id: str,
    paper_id: str,
    *,
    record_path: str,
    chunks_path: str,
    chunk_count: int,
    parse_status: str,
    source_mode: str,
    sha256: str | None = None,
    arxiv_id: str | None = None,
) -> None:
    """更新 manifest: 写或覆盖单条 paper_id 记录."""

    with _MANIFEST_LOCK:
        mf = _load_manifest(project_id)
        entry = {
            "record_path": record_path,
            "chunks_path": chunks_path,
            "chunk_count": chunk_count,
            "parse_status": parse_status,
            "source_mode": source_mode,
            "sha256": sha256,
            "arxiv_id": arxiv_id,
        }
        mf["papers"][paper_id] = entry
        _save_manifest(project_id, mf)


def read_manifest(project_id: str) -> dict[str, Any]:
    return _load_manifest(project_id)


def load_record(project_id: str, paper_id: str) -> PaperRecord | None:
    paths = _project_paths(project_id)
    target = paths["parsed"] / f"{paper_id}.json"
    if not target.exists():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return PaperRecord(**data)
    except Exception:  # noqa: BLE001
        return None


def load_chunks(project_id: str, paper_id: str) -> list[PaperChunk]:
    paths = _project_paths(project_id)
    target = paths["chunks"] / f"{paper_id}_chunks.jsonl"
    if not target.exists():
        return []
    out: list[PaperChunk] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(PaperChunk(**json.loads(line)))
        except Exception:  # noqa: BLE001
            continue
    return out


def load_full_text(project_id: str, paper_id: str) -> str:
    """从 parsed JSON 取 record 关联的 full_text_excerpt (若存了)."""

    paths = _project_paths(project_id)
    target = paths["parsed"] / f"{paper_id}.json"
    if not target.exists():
        return ""
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data.get("full_text_excerpt", "") or ""
    except Exception:  # noqa: BLE001
        return ""


def save_full_text_excerpt(project_id: str, paper_id: str, excerpt: str) -> None:
    """把全文前 N 字保存到 parsed JSON (供 preview 用)."""

    paths = _project_paths(project_id)
    target = paths["parsed"] / f"{paper_id}.json"
    if not target.exists():
        return
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        data["full_text_excerpt"] = excerpt[:5000]
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        return


# ---------- 内存索引 (paper_id 映射, 方便查重) ---------- #


def list_paper_ids(project_id: str) -> list[str]:
    mf = _load_manifest(project_id)
    return list(mf.get("papers", {}).keys())
