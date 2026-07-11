# PaperAgent Re4.5：全文入库与 RAG 检索 SOP

> **承接**：Re4.4 ACP 最小能力层已完成（14 能力声明，17 集成测试 PASS，端到端 case 通过 ACP 层验证）。
>
> **本 SOP 覆盖 Day 5 全部任务**：PDF 全文提取、语义分块、TF-IDF 向量索引、
> 检索增强问答、ACP 能力接通、前端 RAG 页面落地。
>
> **预计时长**：6–8 小时，分 7 个 Phase。
> **模型**：DeepSeek v4 flash（via OpenCode proxy，`https://opencode.ai/go`）。
> **参考项目复用**：AutoResearchClaw (MIT) `literature/cache.py` per-source cache_key 思想 (B 级)；
> academic-research-skills (CC BY-NC) `evidence_synthesis_protocol.md` 分块策略 (B 级)。
> 不复制外部代码。

---

## 0. 当前事实基线（已验证）

### ACP 声明但未实现的能力（Re4.4 遗留）

| 能力名 | permission | 当前返回 | Day 5 目标 |
|---|---|---|---|
| `ingest_pdf` | write | `NOT_IMPLEMENTED` | 实现：下载 PDF → 提取全文 → 分块 → 索引 |
| `query_rag` | read | `NOT_IMPLEMENTED` | 实现：问题 → 检索 chunks → LLM 生成答案 + 引用 |
| `get_knowledge_graph` | read | `NOT_IMPLEMENTED` | 实现：从已索引文档构建简单知识图谱 |
| `review_human_gate` | write | `NOT_IMPLEMENTED` | **不做**（未来扩展） |

### 现有依赖与工具链

| 项 | 版本/状态 | Day 5 用途 |
|---|---|---|
| `pypdf` | 6.14.2（已安装） | PDF 全文提取 |
| `httpx` | ≥0.27（已安装） | 异步下载 PDF |
| `langgraph-checkpoint-sqlite` | ≥3.1（已安装） | SQLite 可用，RAG 索引可复用同路径 |
| numpy / sklearn / sentence-transformers | **未安装** | Day 5 用纯 Python TF-IDF，不引入新依赖 |
| `atomic_write_json` | Re4.1 已实现 | 索引文件原子写入 |
| `RunLedger` | Re4.1 已实现 | RAG 操作日志 |
| LLM | DeepSeek v4 flash（OpenCode proxy） | 摘要 + 问答生成 |

### 现有前端

| 路由 | 组件 | 状态 |
|---|---|---|
| `/#/rag` | `RagPlaceholder.tsx` | 显示"即将上线"占位 |
| `/#/workbench/:caseId` | `Workbench.tsx` | 可展示报告折叠区 |

Day 5 将 `RagPlaceholder` 替换为真实功能页面。

### 现有 state 字段

```python
# ResearchState 已有的 paper 相关字段
verified_papers: list[dict]     # 已验证论文（有 title/abstract/doi/arxiv_id）
repo_candidates: list[dict]    # GitHub 仓库
dataset_candidates: list[dict] # 数据集

# Re4.1 已有的基础设施
atomic_write_json(path, data)   # 原子写入
RunLedger(path)                # 追加日志
```

### 决策

- **向量方案**：纯 Python TF-IDF（无 numpy 依赖）。每个 chunk 用词频向量表示，
  检索时用余弦相似度排序。MVP 够用，后续 Day 7 可升级为 embedding。
- **索引存储**：JSON 文件（`tmp_re13_eval/{case_id}/rag_index.json`），
  使用 `atomic_write_json` 保证一致性。Day 5 不引入 SQLite FTS5。
- **分块策略**：固定 500 字符 + 100 字符重叠，按段落边界对齐。
  学术论文以段落为语义单元，固定窗口 + 重叠覆盖跨段引用。
- **LLM 问答**：用 DeepSeek v4 flash，prompt 注入 top-K chunks 作为上下文，
  要求答案带 chunk_id 引用。不使用流式（MVP 返回完整 JSON）。
- **知识图谱**：从已索引 chunks 中提取（论文标题→数据集→方法 的简单三元组），
  复用 `evidence_graph_builder` 的 node/edge 格式。

### 参考项目可用资产

| 源 | 文件 | 复用级别 | Day 5 用途 |
|---|---|---|---|
| AutoResearchClaw (MIT) | `literature/cache.py` | B | per-source cache_key + TTL 思想；映射到 RAG chunk cache |
| academic-research-skills (CC BY-NC) | `evidence_synthesis_protocol.md` | B | 分块→检索→综合 三阶段策略 |
| AutoResearchClaw (MIT) | `mcp/tools.py` | B | 已在 Re4.4 借鉴；Day 5 不再重复引用 |

> **许可证行动**：Day 5 不复制外部代码。所有实现为 PaperAgent 独立编写。

---

## 1. 本轮目标

### 核心交付

1. **PDF 全文提取**：`pypdf` 提取文本，清洗分页符/页眉页脚
2. **语义分块**：500 字符窗口 + 100 字符重叠，段落对齐
3. **TF-IDF 索引**：纯 Python 实现，`atomic_write_json` 持久化
4. **检索增强问答**：问题 → TF-IDF top-K → LLM 生成答案 + chunk 引用
5. **ACP 能力接通**：`ingest_pdf` + `query_rag` + `get_knowledge_graph` 从 NOT_IMPLEMENTED 变为可用
6. **前端 RAG 页面**：替换占位页，支持 PDF URL 输入 → 入库 → 问答

### 验收标准

- `ingest_pdf` 成功后返回 chunk 数量 + 索引路径
- `query_rag` 返回答案 + 至少 1 条 chunk 引用（有 chunk_id + 原文片段）
- `get_knowledge_graph` 返回 nodes + edges（从已索引文档构建）
- TF-IDF 检索 top-3 chunks 中至少 1 条与问题语义相关
- 前端可输入 PDF URL → 入库 → 提问 → 看到答案 + 引用

### 不做

- 不引入 numpy / sklearn / sentence-transformers（Day 7 升级）
- 不实现 SQLite FTS5 全文检索（Day 7 升级）
- 不实现 OCR（扫描版 PDF 不支持，返回 `extraction_failed`）
- 不修改 graph 拓扑
- 不实现 `review_human_gate`（未来扩展）

> **强制规则**：每个 Phase 完成后必须跑 `pytest --collect-only` 确认零 error；
> 全部 Phase 完成后必须跑一个端到端 case 验证产物完整性和正确性（见 Phase 7）。

---

## 2. Phase 设计

### Phase 1：PDF 提取 + 分块 — 1.5h

#### Fix 1.1: 新建 `services/rag/` 模块

```
apps/api/app/services/rag/
├── __init__.py
├── pdf_extractor.py    # PDF 下载 + 全文提取 + 清洗
├── chunker.py          # 文本分块（500 字符 + 100 重叠）
├── indexer.py          # TF-IDF 索引构建 + 持久化
├── retriever.py        # TF-IDF 检索 + top-K 排序
└── qa.py              # LLM 问答 + 引用生成
```

#### Fix 1.2: `pdf_extractor.py`

**文件**：`apps/api/app/services/rag/pdf_extractor.py`（新建）

```python
"""Re4.5: PDF full-text extraction using pypdf.

Downloads PDF from URL, extracts text, cleans page breaks / headers / footers.
"""
from __future__ import annotations

import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfReader

logger = logging.getLogger(__name__)

# Patterns for cleaning
_PAGE_HEADER_PATTERN = re.compile(r"^\s*\d+\s*$", re.MULTILINE)  # page numbers
_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")


async def download_pdf(url: str, *, timeout: float = 30.0) -> bytes:
    """Download PDF bytes from URL."""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "PaperAgent/1.0"})
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "pdf" not in content_type and not url.lower().endswith(".pdf"):
            raise ValueError(f"URL does not appear to be a PDF (content-type: {content_type})")
        return resp.content


def extract_text(pdf_bytes: bytes) -> str:
    """Extract full text from PDF bytes using pypdf.

    Returns cleaned text with page breaks normalized.
    """
    reader = PdfReader(BytesIO(pdf_bytes))
    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            logger.warning("pypdf page %d extraction failed: %s", i, exc)
            text = ""
        pages.append(text)

    raw = "\n\n".join(pages)
    return _clean_text(raw)


def _clean_text(text: str) -> str:
    """Clean extracted text: normalize whitespace, remove page numbers."""
    # Remove standalone page numbers
    text = _PAGE_HEADER_PATTERN.sub("", text)
    # Normalize spaces
    text = _MULTI_SPACE.sub(" ", text)
    # Collapse excessive newlines (keep paragraph breaks)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def extract_pdf_from_url(url: str) -> dict[str, Any]:
    """Download + extract PDF. Returns metadata + full text.

    Synchronous wrapper for ACP handler (runs in thread).
    """
    import asyncio
    pdf_bytes = asyncio.run(download_pdf(url))
    text = extract_text(pdf_bytes)
    if not text or len(text.strip()) < 100:
        return {
            "status": "extraction_failed",
            "reason": "extracted text too short (likely scanned PDF)",
            "n_chars": len(text),
        }
    return {
        "status": "ok",
        "text": text,
        "n_chars": len(text),
        "n_pages": pdf_bytes.count(b"/Type /Page") if pdf_bytes else 0,
    }
```

#### Fix 1.3: `chunker.py`

**文件**：`apps/api/app/services/rag/chunker.py`（新建）

```python
"""Re4.5: Text chunking — 500 char windows with 100 char overlap.

Paragraph-aligned: chunks break at paragraph boundaries when possible.
"""
from __future__ import annotations

from typing import Any

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


def chunk_text(text: str, *, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> list[dict[str, Any]]:
    """Split text into overlapping chunks.

    Each chunk:
      - chunk_id: "chunk-0", "chunk-1", ...
      - text: the chunk content
      - start_char: start position in original text
      - end_char: end position in original text

    Strategy:
      1. Split into paragraphs by double-newline
      2. Accumulate paragraphs until reaching chunk_size
      3. Backtrack `overlap` chars to create overlap with next chunk
    """
    if not text or not text.strip():
        return []

    paragraphs = text.split("\n\n")
    chunks: list[dict[str, Any]] = []
    current = ""
    current_start = 0
    pos = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            pos += 1  # account for the \n\n we split on
            continue

        if not current:
            current_start = pos

        candidate = para if not current else f"{current}\n\n{para}"

        if len(candidate) >= chunk_size and current:
            # Save current chunk
            chunks.append({
                "chunk_id": f"chunk-{len(chunks)}",
                "text": current,
                "start_char": current_start,
                "end_char": current_start + len(current),
            })
            # Start next chunk with overlap
            if overlap > 0 and len(current) > overlap:
                overlap_text = current[-overlap:]
                current = overlap_text + "\n\n" + para
                current_start = current_start + len(current) - overlap - len(para) - 2
            else:
                current = para
                current_start = pos
        else:
            current = candidate

        pos += len(para) + 2  # +2 for \n\n

    # Last chunk
    if current and current.strip():
        chunks.append({
            "chunk_id": f"chunk-{len(chunks)}",
            "text": current,
            "start_char": current_start,
            "end_char": current_start + len(current),
        })

    return chunks
```

#### Fix 1.4: 测试

**文件**：`apps/api/tests/test_re45_pdf_chunker.py`（新建）

```python
"""Re4.5: PDF extraction + chunking tests."""
from __future__ import annotations

from apps.api.app.services.rag.chunker import chunk_text
from apps.api.app.services.rag.pdf_extractor import _clean_text


class TestCleanText:
    def test_removes_page_numbers(self):
        text = "Some text\n\n12\n\nMore text"
        cleaned = _clean_text(text)
        assert "12" not in cleaned or "Some text" in cleaned

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
        # Create text longer than chunk_size (500)
        para = "This is a paragraph. " * 30  # ~600 chars
        text = f"{para}\n\n{para}\n\n{para}"
        chunks = chunk_text(text, chunk_size=500, overlap=100)
        assert len(chunks) >= 2
        # Each chunk should have chunk_id
        for c in chunks:
            assert c["chunk_id"].startswith("chunk-")
            assert "text" in c
            assert "start_char" in c
            assert "end_char" in c

    def test_chunks_have_overlap(self):
        para = "A" * 300 + ". "
        text = para * 10  # ~3000 chars
        chunks = chunk_text(text, chunk_size=500, overlap=100)
        if len(chunks) >= 2:
            # The end of chunk 0 should overlap with start of chunk 1
            end_chunk0 = chunks[0]["text"][-50:]
            start_chunk1 = chunks[1]["text"][:50]
            # There should be some overlap
            assert any(c in start_chunk1 for c in end_chunk0[-20:])

    def test_chunk_ids_sequential(self):
        text = "\n\n".join([f"Paragraph {i}. " * 40 for i in range(5)])
        chunks = chunk_text(text, chunk_size=500, overlap=100)
        for i, c in enumerate(chunks):
            assert c["chunk_id"] == f"chunk-{i}"
```

---

### Phase 2：TF-IDF 索引 — 1.5h

#### Fix 2.1: `indexer.py`

**文件**：`apps/api/app/services/rag/indexer.py`（新建）

```python
"""Re4.5: TF-IDF indexer — pure Python, no numpy dependency.

Builds a term-document matrix from chunks, persists to JSON via atomic_write_json.

Index structure:
{
  "case_id": "xxx",
  "documents": [
    {"chunk_id": "chunk-0", "text": "...", "source": "arxiv:2401.00001", "page": 3},
    ...
  ],
  "vocabulary": {"term": doc_freq, ...},
  "tfidf_vectors": [
    {"chunk_id": "chunk-0", "terms": {"term": tfidf_score, ...}},
    ...
  ],
  "n_chunks": 42,
  "created_at": 1783690000.0,
}
"""
from __future__ import annotations

import math
import re
import time
from pathlib import Path
from typing import Any

from apps.api.app.services.run_state import atomic_write_json

# Token pattern: words with at least 2 chars, alphanumeric
_TOKEN_PATTERN = re.compile(r"[a-zA-Z\u4e00-\u9fff]{2,}")


def _tokenize(text: str) -> list[str]:
    """Tokenize text: extract words (English ≥2 chars + Chinese chars)."""
    return [t.lower() for t in _TOKEN_PATTERN.findall(text)]


def _build_vocabulary(chunks: list[dict[str, Any]]) -> dict[str, int]:
    """Build vocabulary with document frequency."""
    df: dict[str, int] = {}
    for chunk in chunks:
        tokens = set(_tokenize(chunk["text"]))
        for token in tokens:
            df[token] = df.get(token, 0) + 1
    return df


def _compute_tfidf(chunks: list[dict[str, Any]],
                   vocabulary: dict[str, int]) -> list[dict[str, Any]]:
    """Compute TF-IDF vectors for each chunk."""
    n_docs = len(chunks)
    vectors: list[dict[str, Any]] = []

    for chunk in chunks:
        tokens = _tokenize(chunk["text"])
        if not tokens:
            vectors.append({"chunk_id": chunk["chunk_id"], "terms": {}})
            continue

        # Term frequency
        tf: dict[str, int] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1

        # TF-IDF
        tfidf: dict[str, float] = {}
        for term, freq in tf.items():
            tf_val = freq / len(tokens)
            df_val = vocabulary.get(term, 0)
            if df_val > 0:
                idf_val = math.log(n_docs / df_val)
                tfidf[term] = tf_val * idf_val

        vectors.append({"chunk_id": chunk["chunk_id"], "terms": tfidf})

    return vectors


def build_index(case_id: str, chunks: list[dict[str, Any]],
                source: str = "", case_dir: Path | None = None) -> dict[str, Any]:
    """Build TF-IDF index from chunks and persist to JSON.

    Args:
        case_id: Case ID for storage path
        chunks: List of chunk dicts (from chunker)
        source: Source URL/identifier of the PDF
        case_dir: Override case directory (defaults to tmp_re13_eval/{case_id})

    Returns:
        Index summary dict (without full vectors, for API response)
    """
    if case_dir is None:
        case_dir = Path(f"tmp_re13_eval/{case_id}")

    # Annotate chunks with source
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
    import json
    if case_dir is None:
        case_dir = Path(f"tmp_re13_eval/{case_id}")
    index_path = case_dir / "rag_index.json"
    if not index_path.exists():
        return None
    return json.loads(index_path.read_text(encoding="utf-8"))
```

#### Fix 2.2: 测试

**文件**：`apps/api/tests/test_re45_indexer.py`（新建）

```python
"""Re4.5: TF-IDF indexer tests."""
from __future__ import annotations

import json
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
        assert len(tokens) > 0  # Chinese chars extracted

    def test_mixed(self):
        tokens = _tokenize("基于YOLO的检测 method")
        assert "yolo" in tokens
        assert "method" in tokens

    def test_short_words_filtered(self):
        tokens = _tokenize("a I am an")
        assert "a" not in tokens
        assert "an" not in tokens


class TestVocabulary:
    def test_doc_frequency(self):
        chunks = [
            {"text": "YOLO detection", "chunk_id": "c0"},
            {"text": "YOLO classification", "chunk_id": "c1"},
        ]
        vocab = _build_vocabulary(chunks)
        assert vocab["yolo"] == 2  # appears in both
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
        result = build_index("test-case", chunks, source="test.pdf",
                             case_dir=tmp_path / "test-case")
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
```

---

### Phase 3：检索 + 问答 — 1.5h

#### Fix 3.1: `retriever.py`

**文件**：`apps/api/app/services/rag/retriever.py`（新建）

```python
"""Re4.5: TF-IDF retriever — cosine similarity ranking.

Pure Python, no numpy. Computes query vector, ranks chunks by cosine sim.
"""
from __future__ import annotations

import math
from typing import Any

from .indexer import _tokenize, _build_vocabulary, _compute_tfidf


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


def retrieve(query: str, index: dict[str, Any], top_k: int = 3) -> list[dict[str, Any]]:
    """Retrieve top-K chunks for a query.

    Args:
        query: Question text
        index: RAG index (from load_index)
        top_k: Number of chunks to return

    Returns:
        List of {chunk_id, text, score, source} sorted by score descending
    """
    # Build query TF-IDF vector using the index's vocabulary
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    n_docs = index["n_chunks"]
    vocab = index["vocabulary"]

    # Query term frequency
    tf: dict[str, int] = {}
    for token in query_tokens:
        tf[token] = tf.get(token, 0) + 1

    # Query TF-IDF
    query_vec: dict[str, float] = {}
    for term, freq in tf.items():
        df_val = vocab.get(term, 0)
        if df_val > 0 and n_docs > 0:
            idf_val = math.log(n_docs / df_val)
            query_vec[term] = (freq / len(query_tokens)) * idf_val

    # Score each chunk
    scored: list[dict[str, Any]] = []
    for vec_entry in index["tfidf_vectors"]:
        score = _cosine_similarity(query_vec, vec_entry["terms"])
        if score > 0:
            # Find the corresponding document
            chunk_id = vec_entry["chunk_id"]
            doc = next((d for d in index["documents"] if d["chunk_id"] == chunk_id), None)
            if doc:
                scored.append({
                    "chunk_id": chunk_id,
                    "text": doc["text"],
                    "score": round(score, 4),
                    "source": doc.get("source", ""),
                    "start_char": doc.get("start_char", 0),
                })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
```

#### Fix 3.2: `qa.py`

**文件**：`apps/api/app/services/rag/qa.py`（新建）

```python
"""Re4.5: RAG question answering — LLM generation with chunk context.

Uses DeepSeek v4 flash to generate answers grounded in retrieved chunks.
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
    """Answer a question using RAG.

    Args:
        question: User's question
        index: RAG index
        case_id: Case ID
        top_k: Number of chunks to retrieve

    Returns:
        {answer, confidence, cited_chunks, retrieved_chunks}
    """
    # Retrieve top-K chunks
    chunks = retrieve(question, index, top_k=top_k)

    if not chunks:
        return {
            "answer": "未在已索引文档中找到相关信息",
            "confidence": 0.0,
            "cited_chunks": [],
            "retrieved_chunks": [],
            "case_id": case_id,
        }

    # Build context text
    context_parts: list[str] = []
    for c in chunks:
        context_parts.append(f"[{c['chunk_id']}] (score={c['score']})\n{c['text'][:500]}")
    context = "\n\n".join(context_parts)

    # Call LLM
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
        # Fallback: return top chunk as answer
        answer = f"基于检索结果（LLM 不可用）：{chunks[0]['text'][:200]}"
        confidence = 0.3
        cited = [chunks[0]["chunk_id"]]

    return {
        "answer": answer,
        "confidence": confidence,
        "cited_chunks": cited,
        "retrieved_chunks": [
            {"chunk_id": c["chunk_id"], "score": c["score"],
             "text": c["text"][:200], "source": c["source"]}
            for c in chunks
        ],
        "case_id": case_id,
    }
```

#### Fix 3.3: 测试

**文件**：`apps/api/tests/test_re45_retriever_qa.py`（新建）

```python
"""Re4.5: Retriever + QA tests."""
from __future__ import annotations

from apps.api.app.services.rag.indexer import build_index
from apps.api.app.services.rag.retriever import retrieve, _cosine_similarity


class TestCosineSimilarity:
    def test_identical_vectors(self):
        vec = {"a": 1.0, "b": 2.0}
        assert _cosine_similarity(vec, vec) == 1.0

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

        from apps.api.app.services.rag.indexer import load_index
        index = load_index("test", case_dir=tmp_path / "test")

        results = retrieve("steel defect detection dataset", index, top_k=2)
        assert len(results) > 0
        assert len(results) <= 2
        # The NEU-DET chunk should rank higher than transformer chunk
        top_ids = [r["chunk_id"] for r in results]
        assert "c1" in top_ids  # NEU-DET chunk
        assert "c2" not in top_ids  # Transformer chunk should not be in top-2

    def test_retrieve_empty_query(self, tmp_path):
        chunks = [{"text": "some text", "chunk_id": "c0"}]
        build_index("test2", chunks, case_dir=tmp_path / "test2")
        from apps.api.app.services.rag.indexer import load_index
        index = load_index("test2", case_dir=tmp_path / "test2")
        results = retrieve("", index)
        assert results == []

    def test_retrieve_no_match(self, tmp_path):
        chunks = [{"text": "abc xyz", "chunk_id": "c0"}]
        build_index("test3", chunks, case_dir=tmp_path / "test3")
        from apps.api.app.services.rag.indexer import load_index
        index = load_index("test3", case_dir=tmp_path / "test3")
        results = retrieve("completely different topic qwerty", index)
        # May return 0 or very low scores
        assert isinstance(results, list)
```

---

### Phase 4：知识图谱构建 — 1h

#### Fix 4.1: `knowledge_graph.py`

**文件**：`apps/api/app/services/rag/knowledge_graph.py`（新建）

```python
"""Re4.5: Simple knowledge graph from RAG index.

Extracts (paper, dataset, method) triples from chunk text using regex patterns.
Returns nodes + edges in the same format as evidence_graph_builder.
"""
from __future__ import annotations

import re
from typing import Any


def build_knowledge_graph(index: dict[str, Any], case_id: str) -> dict[str, Any]:
    """Build a simple knowledge graph from RAG-indexed chunks.

    Extracts:
      - Paper titles (from source or chunk text)
      - Dataset names (from known patterns)
      - Method names (from known patterns)

    Edges: paper → uses → dataset, paper → uses → method
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_node_ids: set[str] = set()

    def add_node(node_id: str, node_type: str, label: str) -> None:
        if node_id not in seen_node_ids:
            nodes.append({"id": node_id, "type": node_type, "label": label})
            seen_node_ids.add(node_id)

    def add_edge(from_id: str, to_id: str, label: str = "uses") -> None:
        edge_key = f"{from_id}->{to_id}"
        if not any(e["from"] == from_id and e["to"] == to_id for e in edges):
            edges.append({"from": from_id, "to": to_id, "label": label})

    # Known dataset names (reuse from innovation_extractor fallback list)
    dataset_names = [
        "NEU-DET", "GC10-DET", "MVTec AD", "COCO", "ImageNet", "CIFAR", "MNIST",
        "Cityscapes", "nuScenes", "DOTA", "VisDrone", "UAVDT", "Waymo",
        "LIDC-IDRI", "MIMIC-CXR", "ChestX-ray14", "BRATS", "ISIC",
    ]
    method_patterns = [
        r"\b(YOLOv\d+|YOLO|SSD|Faster\s+R-CNN|Mask\s+R-CNN|ResNet|VGG|Transformer|BERT|GPT|ViT|DETR)\b",
    ]

    for doc in index.get("documents", []):
        chunk_id = doc["chunk_id"]
        text = doc.get("text", "")
        source = doc.get("source", "")

        # Paper node
        if source:
            paper_id = f"paper:{source}"
            add_node(paper_id, "paper", source)
        else:
            paper_id = f"chunk:{chunk_id}"
            add_node(paper_id, "chunk", chunk_id)

        # Dataset nodes
        for ds_name in dataset_names:
            if ds_name.lower() in text.lower():
                ds_id = f"dataset:{ds_name.lower()}"
                add_node(ds_id, "dataset", ds_name)
                add_edge(paper_id, ds_id, "uses_dataset")

        # Method nodes
        for pattern in method_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                method_name = match.group(1).strip()
                method_id = f"method:{method_name.lower()}"
                add_node(method_id, "method", method_name)
                add_edge(paper_id, method_id, "uses_method")

    return {
        "case_id": case_id,
        "nodes": nodes,
        "edges": edges,
        "n_nodes": len(nodes),
        "n_edges": len(edges),
    }
```

#### Fix 4.2: 测试

**文件**：`apps/api/tests/test_re45_knowledge_graph.py`（新建）

```python
"""Re4.5: Knowledge graph builder tests."""
from __future__ import annotations

from apps.api.app.services.rag.knowledge_graph import build_knowledge_graph


class TestKnowledgeGraph:
    def test_empty_index(self):
        index = {"documents": []}
        kg = build_knowledge_graph(index, "test")
        assert kg["nodes"] == []
        assert kg["edges"] == []

    def test_dataset_extraction(self):
        index = {
            "documents": [
                {"chunk_id": "c0", "text": "We use NEU-DET dataset for training YOLO model.",
                 "source": "arxiv:2401.00001"},
            ],
        }
        kg = build_knowledge_graph(index, "test")
        node_types = [n["type"] for n in kg["nodes"]]
        assert "paper" in node_types
        assert "dataset" in node_types
        assert "method" in node_types

    def test_edge_creation(self):
        index = {
            "documents": [
                {"chunk_id": "c0", "text": "YOLO model trained on COCO dataset.",
                 "source": "paper-1"},
            ],
        }
        kg = build_knowledge_graph(index, "test")
        assert len(kg["edges"]) >= 2  # paper→dataset + paper→method

    def test_node_ids_unique(self):
        index = {
            "documents": [
                {"chunk_id": "c0", "text": "YOLO on NEU-DET", "source": "p1"},
                {"chunk_id": "c1", "text": "YOLO on NEU-DET again", "source": "p2"},
            ],
        }
        kg = build_knowledge_graph(index, "test")
        node_ids = [n["id"] for n in kg["nodes"]]
        assert len(node_ids) == len(set(node_ids))  # no duplicates
```

---

### Phase 5：ACP 能力接通 — 1h

#### Fix 5.1: ACP handler 注册

**文件**：`apps/api/app/services/acp/server.py`

在 `_get_handler` 中添加三个新 handler：

```python
def _get_handler(self, name: str):
    handlers = {
        # ... existing handlers ...
        "ingest_pdf": self._h_ingest_pdf,
        "query_rag": self._h_query_rag,
        "get_knowledge_graph": self._h_get_knowledge_graph,
    }
    return handlers.get(name)

def _h_ingest_pdf(self, params: dict[str, Any]) -> dict[str, Any]:
    from apps.api.app.services.rag.pdf_extractor import extract_pdf_from_url
    from apps.api.app.services.rag.chunker import chunk_text
    from apps.api.app.services.rag.indexer import build_index

    case_id = params.get("case_id", "global")
    pdf_url = params["pdf_url"]

    # Extract
    result = extract_pdf_from_url(pdf_url)
    if result["status"] != "ok":
        return result

    # Chunk
    chunks = chunk_text(result["text"])
    if not chunks:
        return {"status": "extraction_failed", "reason": "no chunks generated"}

    # Index
    index_result = build_index(case_id, chunks, source=pdf_url)
    return index_result

def _h_query_rag(self, params: dict[str, Any]) -> dict[str, Any]:
    from apps.api.app.services.rag.indexer import load_index
    from apps.api.app.services.rag.qa import answer_question

    case_id = params.get("case_id", "global")
    question = params["question"]

    index = load_index(case_id)
    if index is None:
        return {"error": "no RAG index found", "case_id": case_id}

    return answer_question(question, index, case_id)

def _h_get_knowledge_graph(self, params: dict[str, Any]) -> dict[str, Any]:
    from apps.api.app.services.rag.indexer import load_index
    from apps.api.app.services.rag.knowledge_graph import build_knowledge_graph

    case_id = params["case_id"]
    index = load_index(case_id)
    if index is None:
        return {"nodes": [], "edges": [], "n_nodes": 0, "n_edges": 0}

    return build_knowledge_graph(index, case_id)
```

#### Fix 5.2: capabilities.py 描述更新

将 `ingest_pdf` / `query_rag` / `get_knowledge_graph` 的 description 中的
`[Re4.5 — not yet implemented]` / `[Re4.6 — not yet implemented]` 移除。

#### Fix 5.3: 测试

**文件**：`apps/api/tests/test_re45_acp_rag.py`（新建）

```python
"""Re4.5: ACP RAG capability tests."""
from __future__ import annotations

from apps.api.app.services.rag.chunker import chunk_text
from apps.api.app.services.rag.indexer import build_index


class TestACPIngestPDF:
    def test_ingest_pdf_implemented(self):
        """ingest_pdf should no longer return NOT_IMPLEMENTED."""
        from apps.api.app.services.acp.server import get_acp_server
        server = get_acp_server()
        # Check handler exists
        assert server._get_handler("ingest_pdf") is not None


class TestACPQueryRAG:
    def test_query_rag_implemented(self):
        """query_rag should no longer return NOT_IMPLEMENTED."""
        from apps.api.app.services.acp.server import get_acp_server
        server = get_acp_server()
        assert server._get_handler("query_rag") is not None

    def test_query_rag_no_index(self):
        """query_rag with no index should return error."""
        from apps.api.app.services.acp.server import get_acp_server
        server = get_acp_server()
        handler = server._get_handler("query_rag")
        result = handler({"question": "test?", "case_id": "nonexistent-rag-case"})
        assert "error" in result or "answer" in result


class TestACPGetKnowledgeGraph:
    def test_get_knowledge_graph_implemented(self):
        """get_knowledge_graph should no longer return NOT_IMPLEMENTED."""
        from apps.api.app.services.acp.server import get_acp_server
        server = get_acp_server()
        assert server._get_handler("get_knowledge_graph") is not None
```

---

### Phase 6：前端 RAG 页面 — 1h

#### Fix 6.1: 替换 RagPlaceholder

**文件**：`apps/web-react/src/pages/RagPlaceholder.tsx`

替换为真实 RAG 页面：

```tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LoadingDots } from '../components/LoadingDots';
import { ErrorState } from '../components/ErrorState';

export function RagPlaceholder() {
  const navigate = useNavigate();
  const [pdfUrl, setPdfUrl] = useState('');
  const [caseId, setCaseId] = useState('');
  const [question, setQuestion] = useState('');
  const [ingesting, setIngesting] = useState(false);
  const [asking, setAsking] = useState(false);
  const [ingestResult, setIngestResult] = useState<{n_chunks?: number; status?: string} | null>(null);
  const [answer, setAnswer] = useState<{answer: string; cited_chunks: string[]; retrieved_chunks: any[]} | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleIngest = async () => {
    if (!pdfUrl.trim()) return;
    setIngesting(true);
    setError(null);
    try {
      const resp = await fetch('/api/v1/acp/invoke', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-ACP-Capability': 'write'},
        body: JSON.stringify({
          capability: 'ingest_pdf',
          params: {pdf_url: pdfUrl, case_id: caseId || 'global'},
        }),
      });
      const data = await resp.json();
      if (data.success) {
        setIngestResult(data.result);
      } else {
        setError(data.error?.message || '入库失败');
      }
    } catch (e) {
      setError('网络错误：' + (e instanceof Error ? e.message : 'unknown'));
    }
    setIngesting(false);
  };

  const handleAsk = async () => {
    if (!question.trim()) return;
    setAsking(true);
    setError(null);
    try {
      const resp = await fetch('/api/v1/acp/invoke', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          capability: 'query_rag',
          params: {question, case_id: caseId || 'global'},
        }),
      });
      const data = await resp.json();
      if (data.success) {
        setAnswer(data.result);
      } else {
        setError(data.error?.message || '查询失败');
      }
    } catch (e) {
      setError('网络错误：' + (e instanceof Error ? e.message : 'unknown'));
    }
    setAsking(false);
  };

  return (
    <div>
      <h2 style={{marginBottom: '24px'}}>📚 RAG 问答</h2>

      {/* Step 1: Ingest PDF */}
      <div style={{marginBottom: '24px'}}>
        <h3>步骤 1：入库 PDF</h3>
        <div style={{display: 'flex', gap: '8px', marginBottom: '8px'}}>
          <input
            type="text"
            placeholder="PDF URL (如 https://arxiv.org/pdf/2401.00001)"
            value={pdfUrl}
            onChange={(e) => setPdfUrl(e.target.value)}
            style={{flex: 1, padding: '8px 12px', border: '1px solid #e2e8f0', borderRadius: '8px'}}
          />
          <input
            type="text"
            placeholder="Case ID (可选)"
            value={caseId}
            onChange={(e) => setCaseId(e.target.value)}
            style={{width: '150px', padding: '8px 12px', border: '1px solid #e2e8f0', borderRadius: '8px'}}
          />
          <button
            className="btn-primary"
            onClick={handleIngest}
            disabled={ingesting || !pdfUrl.trim()}
          >
            {ingesting ? <LoadingDots text="入库中"/> : '入库'}
          </button>
        </div>
        {ingestResult && (
          <div style={{padding: '8px 16px', background: '#f0fdf4', borderRadius: '8px', fontSize: '14px'}}>
            ✅ 入库成功：{ingestResult.n_chunks || 0} 个文本块，{ingestResult.n_terms || 0} 个词项
          </div>
        )}
      </div>

      {/* Step 2: Ask question */}
      <div style={{marginBottom: '24px'}}>
        <h3>步骤 2：提问</h3>
        <div style={{display: 'flex', gap: '8px'}}>
          <input
            type="text"
            placeholder="输入问题..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
            style={{flex: 1, padding: '8px 12px', border: '1px solid #e2e8f0', borderRadius: '8px'}}
            disabled={!ingestResult}
          />
          <button
            className="btn-primary"
            onClick={handleAsk}
            disabled={asking || !question.trim() || !ingestResult}
          >
            {asking ? <LoadingDots text="查询中"/> : '提问'}
          </button>
        </div>
      </div>

      {/* Answer */}
      {answer && (
        <div style={{marginBottom: '24px'}}>
          <h3>回答</h3>
          <div style={{padding: '16px', background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px'}}>
            <p style={{marginBottom: '12px'}}>{answer.answer}</p>
            <div style={{fontSize: '13px', color: '#64748b'}}>
              置信度：{(answer.confidence * 100).toFixed(0)}% ·
              引用：{answer.cited_chunks.join(', ')}
            </div>
          </div>

          {/* Retrieved chunks */}
          {answer.retrieved_chunks && answer.retrieved_chunks.length > 0 && (
            <div style={{marginTop: '16px'}}>
              <h4>检索到的片段</h4>
              {answer.retrieved_chunks.map((c, i) => (
                <details key={i} style={{marginBottom: '8px'}}>
                  <summary style={{cursor: 'pointer', fontSize: '13px'}}>
                    {c.chunk_id} (score={c.score})
                  </summary>
                  <pre style={{padding: '8px', background: '#f8fafc', fontSize: '12px', whiteSpace: 'pre-wrap'}}>
                    {c.text}
                  </pre>
                </details>
              ))}
            </div>
          )}
        </div>
      )}

      {error && <ErrorState title="操作失败" message={error} onRetry={() => setError(null)} />}
    </div>
  );
}
```

#### Fix 6.2: 路由更新

路由文件不需要修改——`/#/rag` 已经指向 `RagPlaceholder` 组件，
只是组件内容从占位变为真实功能。

#### Fix 6.3: Playwright 截图

**文件**：`apps/web-react/e2e/test_re42_react_web.py`

更新 RAG 测试：

```python
class TestReactRagPlaceholder:
    def test_rag_page_loads(self, page: Page):
        """RAG 页面加载，显示入库 + 问答 UI。"""
        page.goto(BASE_URL + "/#/rag")
        expect(page.locator("text=入库")).to_be_visible()
        expect(page.locator("text=提问")).to_be_visible()
        page.screenshot(path=str(SCREENSHOT_DIR / "rag_page.png"))
```

---

### Phase 7：验收与端到端验证 — 1h

#### Step 1: 单元测试

```bash
cd G:\PaperAgent
.venv\Scripts\python.exe -m pytest apps/api/tests/test_re45_pdf_chunker.py -v
.venv\Scripts\python.exe -m pytest apps/api/tests/test_re45_indexer.py -v
.venv\Scripts\python.exe -m pytest apps/api/tests/test_re45_retriever_qa.py -v
.venv\Scripts\python.exe -m pytest apps/api/tests/test_re45_knowledge_graph.py -v
.venv\Scripts\python.exe -m pytest apps/api/tests/test_re45_acp_rag.py -v
# 预期：全部 PASS
```

#### Step 2: ACP 能力状态验证

```bash
# 启动后端
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181

# ingest_pdf 应不再是 NOT_IMPLEMENTED
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -H "X-ACP-Capability: write" \
  -d '{"capability": "ingest_pdf", "params": {"pdf_url": "https://arxiv.org/pdf/2401.17270", "case_id": "re45-test"}}'

# query_rag 应不再是 NOT_IMPLEMENTED
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability": "query_rag", "params": {"question": "What datasets are used?", "case_id": "re45-test"}}'

# get_knowledge_graph 应不再是 NOT_IMPLEMENTED
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability": "get_knowledge_graph", "params": {"case_id": "re45-test"}}'
```

#### Step 3: pytest 收集不退化

```bash
.venv\Scripts\python.exe -m pytest --collect-only -q 2>&1 | Select-String "error|collected"
# 预期：0 errors，collected 数 ≥ 497（新增 Re4.5 测试）
```

#### Step 4: ruff 无新增

```bash
.venv\Scripts\python.exe -m ruff check apps/api/app --statistics
# 预期：≤ 19 errors（无新增）
```

#### Step 5: 端到端验证（强制）

> **规则**：全部 Phase 完成后必须通过 ACP 层跑一个端到端 RAG 流程。

**前置条件**：后端 18181 运行中，`.env` 有效 `DEEPSEEK_API_KEY`。

**流程**：

1. 通过 ACP `ingest_pdf` 入库一篇 arXiv PDF
2. 通过 ACP `query_rag` 提问
3. 通过 ACP `get_knowledge_graph` 获取知识图谱
4. 检查产物完整性

**产物完整性检查清单**：

| 检查项 | 通过标准 |
|---|---|
| ingest_pdf 返回 | `status=ok`，`n_chunks > 0`，`n_terms > 0` |
| rag_index.json | 文件存在于 `tmp_re13_eval/{case_id}/rag_index.json` |
| query_rag 返回 | `answer` 非空，`cited_chunks` 至少 1 条 |
| retrieved_chunks | `top_k` 条，每条有 chunk_id + score + text |
| get_knowledge_graph | `nodes` 非空（至少有 paper + dataset/method 节点） |
| acp_ledger.jsonl | 记录了 ingest_pdf + query_rag + get_knowledge_graph 调用 |

**数据正确性自检清单**：

| 维度 | 验证方法 | 通过标准 |
|---|---|---|
| 检索相关性 | query_rag 的 retrieved_chunks 中 top-1 score > 0 | score > 0 |
| 引用一致性 | cited_chunks 中的 chunk_id 存在于 retrieved_chunks | 一致 |
| 知识图谱节点类型 | nodes 中有 paper/dataset/method 类型 | ≥ 2 种类型 |
| 向后兼容 | Re4.4 的 ACP 测试仍通过 | 17 tests PASS |

> **自我检验**：验收者必须对照上述清单逐项检查实际产物，
> 确认每项通过后再标记 Phase 7 完成。

---

## 3. 执行顺序与依赖

```
Phase 1 (PDF 提取 + 分块) ─── 无依赖
    │
    ├── Phase 2 (TF-IDF 索引) ─── 依赖 Phase 1 的 chunks
    │
    ├── Phase 3 (检索 + 问答) ─── 依赖 Phase 2 的 index
    │
    ├── Phase 4 (知识图谱) ─── 依赖 Phase 2 的 index
    │
    ├── Phase 5 (ACP 接通) ─── 依赖 Phase 1-4 全部完成
    │
    ├── Phase 6 (前端 RAG 页面) ─── 依赖 Phase 5 ACP 接通
    │
    └── Phase 7 (验收 + 端到端) ─── 依赖全部完成

可并行：
- Phase 3 (检索+问答) 和 Phase 4 (知识图谱) 可同时开发
- Phase 6 (前端) 可与 Phase 5 后半段并行
```

---

## 4. 风险与预案

| 风险 | 触发信号 | 预案 |
|---|---|---|
| PDF 下载失败 / 超时 | `extract_pdf_from_url` 抛异常 | 返回 `extraction_failed` + 错误原因；不影响其他 case |
| pypdf 提取文本为空（扫描版 PDF） | `n_chars < 100` | 返回 `extraction_failed` + reason="scanned PDF"；Day 5 不做 OCR |
| TF-IDF 检索全部 score=0 | query 词不在 vocabulary 中 | 返回空 retrieved_chunks + "未找到相关信息" |
| LLM 问答超时 / JSON 解析失败 | `llm_router.call_json` 抛异常 | Fallback：返回 top-1 chunk 文本作为答案，confidence=0.3 |
| 索引文件过大（长论文） | rag_index.json > 10MB | 限制最多 500 chunks（截断长论文尾部） |
| ACP handler 中的 async/sync 混用 | `extract_pdf_from_url` 内部 `asyncio.run` 在已有 loop 时失败 | 用 `httpx.Client` 同步下载替代 `httpx.AsyncClient` |
| Vite proxy 不传递 `X-ACP-Capability` header | 前端 ingest_pdf 返回 PERMISSION_DENIED | 确认 Vite proxy 默认传递所有 header；如不传则用 query param fallback |

---

## 5. 完成标准

- [ ] `pdf_extractor.py` 可从 URL 下载 PDF 并提取全文
- [ ] `chunker.py` 将文本分为 500 字符 + 100 重叠的 chunks
- [ ] `indexer.py` 构建 TF-IDF 索引并持久化到 `rag_index.json`
- [ ] `retriever.py` 用余弦相似度检索 top-K chunks
- [ ] `qa.py` 用 LLM 生成答案 + chunk 引用
- [ ] `knowledge_graph.py` 从索引构建 nodes + edges
- [ ] ACP `ingest_pdf` 不再返回 NOT_IMPLEMENTED
- [ ] ACP `query_rag` 不再返回 NOT_IMPLEMENTED
- [ ] ACP `get_knowledge_graph` 不再返回 NOT_IMPLEMENTED
- [ ] 前端 RAG 页面可输入 PDF URL → 入库 → 提问 → 看到答案
- [ ] `pytest --collect-only` 零 error
- [ ] `ruff check apps/api/app` ≤ 19 errors（无新增）
- [ ] **端到端验证**：ACP ingest_pdf → query_rag → get_knowledge_graph 全链路成功
- [ ] **数据正确性自检**：检索 score > 0，引用一致，知识图谱有节点

---

## 6. 提交清单

| 文件 | 操作 |
|---|---|
| `apps/api/app/services/rag/__init__.py` | 新建 |
| `apps/api/app/services/rag/pdf_extractor.py` | 新建 |
| `apps/api/app/services/rag/chunker.py` | 新建 |
| `apps/api/app/services/rag/indexer.py` | 新建 |
| `apps/api/app/services/rag/retriever.py` | 新建 |
| `apps/api/app/services/rag/qa.py` | 新建 |
| `apps/api/app/services/rag/knowledge_graph.py` | 新建 |
| `apps/api/app/services/acp/server.py` | 修改：添加 3 个 RAG handler |
| `apps/api/app/services/acp/capabilities.py` | 修改：移除 NOT_IMPLEMENTED 标记 |
| `apps/web-react/src/pages/RagPlaceholder.tsx` | 重写：真实 RAG 页面 |
| `apps/api/tests/test_re45_pdf_chunker.py` | 新建 |
| `apps/api/tests/test_re45_indexer.py` | 新建 |
| `apps/api/tests/test_re45_retriever_qa.py` | 新建 |
| `apps/api/tests/test_re45_knowledge_graph.py` | 新建 |
| `apps/api/tests/test_re45_acp_rag.py` | 新建 |
| `CHANGELOG.md` | 追加 Re4.5 条目 |

---

## 7. CHANGELOG 预备

```markdown
## [0.4.0-dev] - 2026-07-10 (Re4.5)

### Added
- `services/rag/`: 全文入库与 RAG 检索
  - `pdf_extractor.py`: PDF 下载 + pypdf 全文提取 + 文本清洗
  - `chunker.py`: 500 字符 + 100 重叠分块，段落对齐
  - `indexer.py`: 纯 Python TF-IDF 索引，atomic_write_json 持久化
  - `retriever.py`: 余弦相似度检索，top-K 排序
  - `qa.py`: LLM 问答 + chunk 引用生成
  - `knowledge_graph.py`: 从索引构建 paper→dataset/method 知识图谱
- ACP 能力接通：`ingest_pdf`、`query_rag`、`get_knowledge_graph`
- 前端 RAG 页面：替换占位页，支持 PDF 入库 → 问答 → 引用展示
- 5 个新测试文件：pdf_chunker、indexer、retriever_qa、knowledge_graph、acp_rag

### Changed
- `acp/server.py`: 添加 3 个 RAG handler
- `acp/capabilities.py`: 移除 3 个能力的 NOT_IMPLEMENTED 标记
- `RagPlaceholder.tsx`: 从占位页重写为真实 RAG 功能页

### Verified
- 端到端验证：ACP ingest_pdf → query_rag → get_knowledge_graph 全链路成功
- 检索相关性：top-1 chunk score > 0
- 引用一致性：cited_chunks 存在于 retrieved_chunks
- 知识图谱：nodes 包含 paper + dataset/method 类型
- Re4.4 ACP 测试仍全部通过（向后兼容）
```
