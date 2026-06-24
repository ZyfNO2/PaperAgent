# Session 46 验收报告：个人论文库 MVP（arXiv 下载 + PDF 上传 + 切块入库）

> 日期：2026-06-24
> 对应 commit：`47dc779d Session 46: 个人论文库 MVP (arXiv + PDF + 切块 + Evidence Ledger)`

---

## 1. 本轮目标（对齐 SOP §1）

把"资料卡片化"升级为"个人论文库"地基。本轮只做入库，不做向量检索、不做问答（拆到 S47）。

**实际完成**：13 文件 / 2249 行新增；51 个新 pytest 全绿。

---

## 2. 任务完成情况

| Task | 状态 | 关键产物 |
|------|------|----------|
| T1: schemas | ✅ | `schemas_paper_library.py` — PaperRecord/PaperChunk + 4 req/resp |
| T2: 模块骨架 | ✅ | `paper_library/__init__.py` 导出 `ingest_arxiv/ingest_upload/list_papers/get_paper` |
| T3: arxiv_downloader | ✅ | arXiv ID/URL 解析 + 复用 `arxiv.py` + httpx 下载 + 失败占位 |
| T4: local_upload + storage | ✅ | base64 → bytes → sha256 → 落盘 raw/parsed/chunks/manifest |
| T5: chunker | ✅ | section-aware 600-1000 tokens / overlap 100 / reference 整块丢弃 |
| T6: dedup | ✅ | sha256 / arxiv_id / DOI / 标题 jaccard>0.92 (年份过滤) |
| T7: API 4 端点 | ✅ | arxiv/upload/list/get 注册到 main.py |
| T8: Evidence Ledger 联动 | ✅ | ingest 成功自动生成 `EvidenceItem(pending, tag=paper_library)` |
| T9: 测试 | ✅ | 51 测试：id parser / chunker / dedup / 上传 / ingest / 端点 / 联动 |
| T10: 依赖 | ✅ | `pypdf>=4.0` 加入 pyproject.toml |

---

## 3. 数据模型（SOP §3.1）

```python
class PaperRecord(BaseModel):
    paper_id / project_id / title / authors / year / venue
    doi / arxiv_id / url / pdf_path / sha256
    source_mode: Literal["arxiv_download", "local_upload"]
    parse_status: Literal["pending", "parsed", "failed", "skipped"]
    page_count / chunk_count
    metadata_status: Literal["resolved", "partial", "missing"]
    created_at

class PaperChunk(BaseModel):
    chunk_id / paper_id / project_id
    section_title / section_path: list[str]
    page_start / page_end
    text / token_count
    chunk_type: Literal["title", "abstract", "introduction", "related_work",
                        "method", "experiment", "result", "limitation",
                        "conclusion", "reference", "unknown"]
    embedding_id: str | None = None  # S47 填
```

---

## 4. 落盘结构（SOP §3.2）

```
.runtime/paper_library/{project_id}/
├── raw/{arxiv_id_or_sha8}.pdf
├── parsed/{paper_id}.json
├── chunks/{paper_id}_chunks.jsonl
└── index/manifest.json
```

---

## 5. 切块策略

| 块类型 | 触发条件 |
|--------|----------|
| abstract | 正则匹配 `^Abstract` 或 `^摘要` |
| introduction | `^1 Introduction` / `^\d+\s+Introduction` |
| related_work | `^2 Related Work` / `^Related Work` |
| method | `^3 Method(s)?` / `Methodology` |
| experiment | `^4 Experiment(s)?` / `^Evaluation` |
| result | `^5 Result(s)?` |
| conclusion | `^6 Conclusion` / `^Conclusion` |
| reference | **整块丢弃** |
| unknown | 其他 |

参数：600-1000 tokens/块，overlap 100 tokens；reference 整块丢弃；用空格分词估算。

---

## 6. 重复检测（4 类）

| 类型 | 键 | 适用 |
|------|----|----|
| sha256 | 文件哈希 | local_upload |
| arxiv_id | 完全相同 | arxiv_download |
| DOI | 完全相同 | 跨类型 |
| 标题 jaccard | > 0.92（同年过滤） | 跨类型 |

重复返回已有 `paper_id`，不重复入库。

---

## 7. API 设计（SOP §9）

```
POST /api/v1/projects/{project_id}/paper-library/arxiv
  body: { arxiv_id_or_url: "2409.13740" }
  resp: { paper_id, status, parse_status, chunk_count, evidence_id }

POST /api/v1/projects/{project_id}/paper-library/upload
  body: { filename, content_b64, mime? }
  resp: { paper_id, parse_status, chunk_count, evidence_id }

GET  /api/v1/projects/{project_id}/paper-library
  resp: { papers: PaperRecord[], total_chunks }

GET  /api/v1/projects/{project_id}/paper-library/{paper_id}
  resp: PaperRecord + chunks 前 3 个预览
```

---

## 8. Evidence Ledger 联动

入库成功后（无论 arxiv 还是 upload）自动调用 `evidence.add_paper_manual` 生成 `EvidenceItem(pending, tag=paper_library)`：
- `source_mode=auto_search` (arXiv) / `source_mode=upload` (本地)
- `paper_id` 入 evidence 引用
- 用户可后续审核 `pending → accepted/core/background/rejected`

**不变式**：论文库负责全文存储和切块；**检索和问答留给 S47**；入库即 pending，不自动成为报告事实。

---

## 9. pytest 结果

| 范围 | 数量 | 状态 |
|------|------|------|
| Session 46 新增 | 51 | ✅ all pass |
| 旧测试 | 611 | ✅ pass（无回归） |
| **总计** | **662 passed, 1 skipped** | ✅ |

---

## 10. 失败兜底（SOP §5）

| 失败 | 兜底 |
|------|------|
| arXiv API 失败 | 用 arxiv_id 当 title 占位，`parse_status=failed`，仍生成 PaperRecord |
| PDF 下载失败 | `parse_status=failed`，不崩服务 |
| pypdf 未装 | 复用 `materials/pdf_parser._extract_minimal` 极弱解析 |
| 假 arXiv ID | 解析失败 → 占位 metadata |

---

## 11. 与 S34/S47/S48 的边界

| 模块 | 作用 | 不做（留给后续 Session） |
|------|------|------------------------|
| S34 `rag_pipeline.py` | 元数据候选检索（演示级 mock） | 全文 chunk 检索 |
| **S46 `paper_library/`** | **入库 + 切块 + 落盘 + 联动** | **embedding + 检索 + 问答** |
| S47 `paper_library/{embedding,indexer,retriever,reranker,paper_qa}.py` | 全文 RAG | claim grounding |
| S48 Evidence Ledger | RAG 答案 refs 写回 + claim_grounding skill | — |

面试讲法：
> S34 是我最早的 Hybrid RAG 流程演示，操作元数据；S46 把论文库地基落地（arXiv 真实下载 + 本地 PDF 上传 + 切块入库 + Evidence 联动）；S47 在它上面接全文 RAG，加 chunk 级 reranker 和 EvidenceRef。

---

## 12. 通过条件自检（SOP §13）

- [x] arXiv 下载 + PDF 上传 + 切块 + 落盘 + Evidence 联动 全链路
- [x] 失败兜底：arXiv API / PDF 下载 / pypdf 都返回占位，不挂服务
- [x] 切块：600-1000 tokens / overlap 100 / reference 整块丢弃
- [x] 重复检测：sha256 / arxiv_id / DOI / 标题 jaccard
- [x] 4 端点可调，响应符合 schema
- [x] pytest 全绿，新增 51 测试，总数 662
- [x] `pypdf>=4.0` 加入 pyproject.toml
