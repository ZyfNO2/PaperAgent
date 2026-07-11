# CODELY.md — PaperAgent Project Context

## Project Overview

**PaperAgent** (TopicPilot-CN) is an interactive evidence workbench for Chinese graduate students' thesis topic selection. Users input a single topic + target tier, and the system produces keyword decomposition, multi-source retrieval, evidence verification, citation expansion, feasibility assessment, and a traceable opening-proposal Markdown report.

**Not** a full thesis generator — it organizes papers, datasets, GitHub baselines, PDF/screenshot/web materials into an auditable evidence chain. All AI-extracted results default to `pending` and require human review before being promoted to `accepted/core/background`.

### Core Pipeline

```
Input topic → Keyword decomposition → Multi-source retrieval → Workbench review
            → URL verified → Evidence cards → Trace persistence
            → FinalPackage Markdown → ReportQuality 8-dim review
            → ACP capability layer → RAG full-text Q&A → Knowledge graph
```

### Tech Stack

| Layer | Technology |
|---|---|
| Language | Python ≥3.12 |
| Backend | FastAPI + uvicorn |
| Graph Engine | LangGraph (state machine for research pipeline) |
| Schema | Pydantic v2 |
| HTTP | httpx (async) |
| Frontend | React + Vite + TypeScript (port 18183); legacy vanilla JS at `/web/` |
| ACP | REST + JSON Schema capability layer (14 capabilities) |
| RAG | TF-IDF indexer + cosine retriever + LLM Q&A |
| Testing | pytest + pytest-asyncio + Playwright (531 tests) |
| Linting | ruff |
| Package Mgmt | uv (uv.lock) + setuptools |
| PDF Parsing | pypdf |
| LLM | DeepSeek v4 flash (via OpenCode proxy) |

## Building and Running

### Environment Setup

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
.venv/Scripts/python.exe -m playwright install chromium
```

Copy `.env.example` → `.env` and fill in API keys (DeepSeek via OpenCode proxy).

### Start Backend

```bash
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181
```

- Legacy frontend: <http://127.0.0.1:18181/web/>
- React frontend: <http://127.0.0.1:18183/> (dev server)
- API docs: <http://127.0.0.1:18181/docs>
- Health: <http://127.0.0.1:18181/health>
- ACP capabilities: <http://127.0.0.1:18181/api/v1/acp/capabilities>

### Start React Frontend (Dev)

```bash
cd apps/web-react
npm install
npm run dev  # http://127.0.0.1:18183, proxy /api → 18181
npm run build  # produces dist/, served at /react
```

### Tests

```bash
# All tests
.venv/Scripts/python.exe -m pytest

# Backend only
.venv/Scripts/python.exe -m pytest apps/api/tests -v

# React e2e
.venv/Scripts/python.exe -m pytest apps/web-react/e2e -v -m "react_web"

# Legacy frontend e2e
.venv/Scripts/python.exe -m pytest apps/web/e2e -v
```

Pytest config: `asyncio_mode=auto`, testpaths = `apps/api/tests`, `apps/web/e2e`, `apps/web-react/e2e`. Markers: `react-web`, `legacy-web`, `re02`, `re03`, `network`.

### Linting

```bash
.venv/Scripts/python.exe -m ruff check .
```

## Architecture

### Directory Structure

```
apps/
  api/
    app/
      main.py                     # FastAPI entry, CORS (env), route registration, static mount (/web + /react)
      api/v1/
        research.py               # Main REST router (submit, status, SSE, evidence graph, papers, work-packages)
        acp.py                    # ACP REST endpoints (capabilities, invoke, examples)
      services/
        llm_router.py             # Provider profile → concrete provider mapping
        llm.py                    # LLM client (DeepSeek via OpenCode proxy)
        json_repair.py            # 3-phase JSON parsing
        source_policy.py          # Unified SourcePolicy (per-source enable/disable, backoff, status)
        run_state.py              # RunState model + atomic_write_json + RunLedger
        agents/
          graph/
            state.py               # ResearchState TypedDict (includes Re4.3: narrative_revisions, binding_validation)
            research_graph.py     # LangGraph builder (nodes + edges + conditional routing)
            stage_contract.py     # StageContract v1 (per-node reads/writes/error_code/dod)
            nodes/                # 24 graph nodes
            schemas/
              evidence_schema.py  # InnovationPoint, NarrativeRevision, WorkPackage, BindingValidationResult
            validators/
              binding_validator.py # Evidence chain consistency validator
              dependency_dag.py   # Work package dependency DAG (topo sort + milestones)
          prompts/                 # LLM prompt templates
        retrieval/
          adapters/                # 7 search adapters
        rag/                       # RAG module: PDF extraction, chunking, TF-IDF, retriever, QA, knowledge graph
        acp/                       # ACP: capabilities, registry, server, errors, examples
    tests/                         # 531 test files
  web/
    index.html                     # Legacy vanilla JS frontend
    e2e/                           # Playwright e2e tests
  web-react/
    src/                           # React + Vite + TypeScript
      pages/                       # Home, Workbench, RagPlaceholder
      components/                  # Layout, SourcePanel, EmptyState, ErrorState, LoadingDots
        reports/                  # FeasibilityReport, ReviewReport, InnovationReport, NarrativeRevisions, DagView, BindingValidation
      lib/                         # api.ts, sse.ts, nodeNames.ts
      types/                       # api.ts (TypeScript types)
    e2e/                           # Playwright e2e tests
docs/                              # Demo scripts, deployment runbook, testing matrix, project scope
Plan/                              # SOP documents (Re4.1–4.7, Re3.x)
scripts/                           # Utility scripts
```

### LangGraph Pipeline

The research pipeline is a LangGraph state machine. Each node receives the shared `ResearchState` TypedDict and returns a partial patch. Nodes **must not** mutate state in place.

Key nodes (in `apps/api/app/services/agents/graph/nodes/`):

| Node | Purpose |
|---|---|
| `intake` | Receive topic + user constraints |
| `topic_parser` | LLM-based keyword decomposition (method/task/object words) |
| `search_planner` | Generate query matrix for multi-source search |
| `search_agent` | Fan-out to 7 adapters (SourcePolicy-gated) |
| `quality_filter` | Pre-filter raw results |
| `verify` | Multi-round paper verification (accept / weak_reject / reject) |
| `citation_expander` | Seed paper → citation/reference expansion (SourcePolicy-gated) |
| `dataset_repo_extractor` | Extract dataset/repo candidates |
| `evidence_graph_builder` | Build evidence graph (nodes + edges) |
| `baseline_classifier` | Classify papers as baseline/parallel/survey |
| `feasibility_assessor` | Feasibility judgment (score + verdict) |
| `innovation_extractor` | Innovation points (Re4.3: candidate_ids + evidence_snippets + scores) |
| `sota_matcher` | Compare against SOTA |
| `narrative_builder` | Research narrative (Re4.3: append-only revision history + diff) |
| `work_package` | Work packages (Re4.3: objective/method/deliverable/prerequisite_ids) |
| `low_bar_review` | Rule-based review + Re4.3 binding validation + DAG |
| `optimization_advisor` | Suggest optimization directions |
| `devils_advocate_node` | Reflection loop (Re4.3: evidence_critiques targeting specific IDs) |
| `review` | Final quality review |

### ACP Layer

14 capabilities exposed via REST + JSON Schema at `/api/v1/acp/`:

| Capability | Permission | Description |
|---|---|---|
| `list_cases` | read | List all research cases |
| `get_run_status` | read | Check case run status |
| `get_evidence_graph` | read | Evidence graph (nodes + edges) |
| `get_papers` | read | Verified + user papers |
| `get_work_packages` | read | Work packages with DAG |
| `get_feasibility` | read | Feasibility report |
| `get_review` | read | Final review report |
| `get_innovation` | read | Innovation points with evidence binding |
| `search_literature` | write | Submit topic for research |
| `upload_paper` | write | Upload user-known paper |
| `ingest_pdf` | write | Ingest PDF for RAG indexing |
| `query_rag` | read | RAG question answering |
| `get_knowledge_graph` | read | Knowledge graph from RAG |
| `review_human_gate` | write | Human gate review (not yet implemented) |

Read capabilities are open by default; write capabilities require `X-ACP-Capability: write` header.

### RAG Layer

PDF → chunk → TF-IDF index → cosine retrieval → LLM Q&A → knowledge graph.

| Component | File | Description |
|---|---|---|
| PDF extraction | `rag/pdf_extractor.py` | Download + pypdf text extraction + cleaning |
| Chunking | `rag/chunker.py` | 500-char windows + 100-char overlap, paragraph-aligned |
| Indexer | `rag/indexer.py` | TF-IDF build + `merge_index` for multi-document + atomic_write_json |
| Retriever | `rag/retriever.py` | Cosine similarity top-K ranking |
| Q&A | `rag/qa.py` | LLM answer generation with chunk citations |
| Knowledge graph | `rag/knowledge_graph.py` | Paper → dataset/method node/edge extraction |

### LLM Provider Routing

| Profile | Provider | Purpose |
|---|---|---|
| `fast_json` | DeepSeek v4 flash (OpenCode proxy) | JSON-producing nodes |
| `execution` | StepFun | Simple execution |
| `premium_review` | VOAPI | Final review |

Controlled via env: `LLM_PROFILE`, `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_FLASH_MODEL`.

### SourcePolicy

Unified source enable/disable covering all adapters + citation_expander:
- `RATE_LIMITED_SOURCES_DISABLED=1` disables S2/OpenAlex in test/dev
- Per-source override: `SEMANTIC_SCHOLAR_ENABLED=1`
- SourceLedger records `enabled/skipped/rate_limited/failed` per source

### API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/research/` | Submit a topic (case_id auto-UUID if omitted) |
| GET | `/api/v1/research/` | List all case IDs |
| GET | `/api/v1/research/{case_id}/status` | Check run status |
| GET | `/api/v1/research/{case_id}/state` | Full ResearchState JSON |
| GET | `/api/v1/research/{case_id}/trace` | Per-node trace events |
| GET | `/api/v1/research/{case_id}/stream` | SSE stream of node progress |
| POST | `/api/v1/research/{case_id}/papers` | Upload user paper |
| GET | `/api/v1/research/{case_id}/work-packages` | Work packages + DAG |
| GET | `/api/v1/research/{case_id}/feasibility` | Feasibility report |
| GET | `/api/v1/research/{case_id}/review` | Final review |
| GET | `/api/v1/acp/capabilities` | ACP capability list (JSON Schema) |
| POST | `/api/v1/acp/invoke` | Invoke ACP capability |
| GET | `/api/v1/acp/examples` | Call examples for external tools |

Results persisted under `tmp_re13_eval/{case_id}/` (state.json, trace.json, evidence_graph.json, rag_index.json, acp_ledger.jsonl).

## Development Conventions

### Hardcoding Bans

- **No hardcoded domain fallbacks**, `domain_map`, short-keyword filtering, or domain-specific prompt examples.
- Use LLM judgment, not regex/blacklist for self-checking.

### Search Chain Rules

- All adapters share the same query list from `search_planner`.
- SourcePolicy gates all adapters + citation_expander: disabled source → zero HTTP requests.
- GitHub results go to `repo_candidates`, not `verified_papers`.

### JSON Parsing Robustness

- System prompts for reasoner models must be <100 tokens.
- `call_json` must pass `expected="dict"`.
- Prompt must end with an OUTPUT CONTRACT clause.
- 3-phase parse: direct → reasoning scan → fallback formatter.

### Async & Concurrency

- I/O operations use `asyncio.gather` / `asyncio.Semaphore`.
- SourcePolicy controls per-source concurrency + exponential backoff on 429.

### Re4 Engineering Conventions

- **case_id**: server-generated UUID or validated slug (`^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$`), path traversal rejected.
- **StageContract**: each node declares reads/writes/error_code/dod/version.
- **atomic_write_json**: state files written atomically (temp → rename, crash-safe).
- **RunLedger**: append-only JSONL event log per case.
- **Binding validator**: innovation → candidate_id, work_package → evidence, narrative → innovation, stale marking.
- **Narrative revisions**: append-only history with revision_id, parent_revision_id, diff.
- **DAG**: work package prerequisite_ids → topological sort + milestones + cycle detection.

### Code Style

- Python 3.12+ features (`str | None`, `dict[str, Any]`).
- `from __future__ import annotations` in most modules.
- Pydantic v2 for all schemas.
- Functions return partial state patches (LangGraph merge pattern).
- React frontend: TypeScript strict mode, `noUnusedLocals`, `noUnusedParameters`.

### Compliance Boundaries

- `rejected` evidence never cited; `pending` doesn't directly support.
- No bypassing paywalled databases (Semantic Scholar: metadata only).
- All LLM credentials from `.env` or runtime-registered via Provider Registry API.
- LLM path degrades to heuristic fallback without crashing.
- `THIRD_PARTY_NOTICES.md` records all reused external code (AutoResearchClaw MIT).

### LLM Provider Management (Re5.X)

- **ProviderRegistry**: runtime-switchable providers, loaded from `.env` at startup.
- **Cross-provider fallback**: when primary returns non-JSON, automatically tries fallback providers.
- **REST API**: `GET /api/v1/llm/providers` (list), `POST /providers` (register), `POST /active` (switch), `POST /test` (connectivity).
- **Schema validation**: every LLM output validated against node schema; wrong-node format (e.g. verify output in feasibility) is rejected and sent to LLM for repair.
- **`call_json_with_validation`**: recommended entry point for all graph nodes — validates output, auto-repairs via LLM, falls back to heuristic.

### Mandatory Test Report Rule

**每次使用 LLM 跑端到端 case 后，必须生成测试结果与标答汇总报告。**

报告格式和位置：
- 文件：`Plan/PaperAgent_{版本号}_端到端测试结果与标答汇总.md`
- 模板参照 `Plan/Arch/PaperAgent_Re3.9.4_6篇测试结果与标答.md`

报告必须包含：

1. **总览表**：Case ID / 题目 / 论文数 / Repo / Dataset / Baseline / 可行性 / 评审 / 耗时
2. **每个 case 的详细分析**：
   - 可行性裁决 + 理由
   - 复核裁决
   - 领域 / 方法关键词 / 对象关键词 / 任务关键词 / 关键词全英文检查
   - Search Steps（每步 tool + query + 结果数 + FAILED 标记）
   - Filter Results（total / kept / dropped / low_relevance）
   - Verified Papers 列表（标题 + 来源 + verdict + 中文译名 + URL + Abstract 摘要）
   - Weak Papers 列表
   - Repos 列表
   - Datasets 列表
   - Baselines 列表
   - Innovation Points 列表（含 Re4.3 candidate_ids + scores）
   - Stitching Plan（Baseline + Module B + Module C）
   - Narrative 摘要 + 模型昵称 + 三个问题
   - 叙事修订历史（Re4.3 revision_id + diff）
   - Binding Validation 结果（Re4.3）
   - Work Packages 列表（含 objective/method/deliverable/prerequisite_ids）
   - DAG 里程碑视图（Re4.3）
   - 证据图谱 nodes/edges
   - 节点执行序列与耗时
   - RAG 检索结果（如已入库 PDF）
   - ACP 能力调用结果
   - SourcePolicy 状态
3. **标答判定**：每个维度标注 ✅ 或 ⚠️ 并给出判定理由
4. **已知问题与修复方向**：列出异常项的根因和修复方案

报告生成时机：
- 每次修改 LLM 相关代码（prompt / provider / fallback / schema validation）后
- 每次完成一个 SOP Phase 的端到端验证后
- 每次切换 LLM provider 或 model 后
