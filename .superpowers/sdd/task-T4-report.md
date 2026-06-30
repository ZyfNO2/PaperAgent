# Phase 63 T4: research_tool_router.py — 验收报告

**Task**: Session 63 T4 (Phase 63 — LLM-first 整改后扩展)

## 产物

- `apps/api/app/services/research_tool_router.py` (新建, 230 行)

## 实现摘要

unified tool router, 所有 paper / dataset / repo / local_rag / trace 调用统一从这走.

### 对外接口

```python
async def search_papers(queries, sources=None, top_k_per_query=8, project_id="") -> list[dict]
async def search_datasets(queries, sources=None, top_k_per_query=5, project_id="") -> list[dict]
async def search_repos(queries, min_stars=20, top_k_per_query=8, project_id="") -> list[dict]
def local_rag_search(query, project_id="", top_k=5) -> list[dict]
def trace_write_event(event_type, event_data, project_id) -> None
```

- paper 默认源: `["arxiv", "openalex"]`
- dataset 默认源: `["huggingface", "kaggle"]`
- repo 固定走 `github`, client-side 按 `min_stars` 过滤

### 集成点

| 路由函数 | 底层 adapter / service |
|----------|------------------------|
| `search_papers` | `retrieval.adapters.arxiv_search`, `retrieval.adapters.openalex_search` |
| `search_datasets` | `retrieval.adapters.huggingface_search`, `retrieval.adapters.optional_adapters.kaggle_search` |
| `search_repos` | `retrieval.adapters.github_search` (本地按 min_stars 过滤) |
| `local_rag_search` | `paper_library.local_rag.ask_local_rag` (sync, 内部已用 keyword_retrieve + dense_retrieve + rrf_fuse) |
| `trace_write_event` | `trace_store.append_trace` |

### Trace 事件

11 个支持的 event_type 都列在 `TRACE_EVENTS` 字典, 写入时把 `event_data` 塞进 `after` 字段, `source="research_tool_router"`.

`tool_call_started` / `tool_call_completed` / `tool_call_failed` 三个事件由 `_run_source` 包裹每个 source 调用, 不需要外部手动写.

### 错误处理

- 单 source 抛 `HttpError` 或其他异常: `_run_source` 捕获 → 写 `tool_call_failed` → 返回 `[]`. 其他 source 不受影响 (用 `asyncio.gather` 并发).
- github 同样独立 try/except, 失败不影响其它 (虽然 repo 只有 github 一个 source).
- `local_rag_search` 失败 → 返回 `[]` + 写 `tool_call_failed`.
- 空 queries / 空 query 字符串 → 返回 `[]` 不写 trace.

### 风险点 / 已知边界

- **github search 按 stars desc 但 min_stars 过滤**: adapter 只取 `top_k_per_query` 条然后本地过滤. 如果前 8 条都是低星 repo, 过滤后可能 <8 条. 这是设计选择 (不二次请求 API), 上限做不到就是做不到. ponytail 注释: 超过 min_stars 的候选数 = adapter 决定, 这里只过滤不补查.
- **paper 源 arxiv + openalex 各跑 queries[:1]**: 每源只跑首 query (与 adapter 现有行为一致, 避免重复), router 沿用.
- **kaggle adapter** 通过 `optional_adapters` 间接拿, 因为 `retrieval.adapters.__init__` 里就这个引用方式.
- **trace 写 event_data 字段**: 不强制 schema 校验 (TRACE_EVENTS 字典只是参考集合), 字段缺失不报错.

## 验证

- import 干净: `from app.services.research_tool_router import search_papers, search_datasets, search_repos, local_rag_search, trace_write_event, TRACE_EVENTS` → 通过
- TRACE_EVENTS 11 个 key 全部存在 (与 task brief 一致)

## 后续 (T5+)

T5+ 的 orchestrator / agent 调用 paper/dataset/repo 必须从这里走, 不许直连 adapter. 这样 trace / min_stars 过滤 / 错误隔离都集中一个地方.
