# CODELY.md — PaperAgent Project Context

## Project Overview

**PaperAgent** (TopicPilot-CN) is an interactive evidence workbench for Chinese graduate students' thesis topic selection. Users input a single topic + target tier, and the system produces keyword decomposition, multi-source retrieval, evidence verification, citation expansion, feasibility assessment, and a traceable opening-proposal Markdown report.

**Not** a full thesis generator — it organizes papers, datasets, GitHub baselines, PDF/screenshot/web materials into an auditable evidence chain. All AI-extracted results default to `pending` and require human review before being promoted to `accepted/core/background`.

### Core Pipeline

```
Input topic → Keyword decomposition → Multi-source retrieval → Workbench review
            → URL verified → Evidence cards → Trace persistence
            → FinalPackage Markdown → ReportQuality 8-dim review
```

### Tech Stack

| Layer | Technology |
|---|---|
| Language | Python ≥3.12 |
| Backend | FastAPI + uvicorn |
| Graph Engine | LangGraph (state machine for research pipeline) |
| Schema | Pydantic v2 |
| HTTP | httpx (async) |
| Frontend | Vanilla JS (mounted as StaticFiles) |
| Testing | pytest + pytest-asyncio + Playwright |
| Linting | ruff |
| Package Mgmt | uv (uv.lock) + setuptools |
| PDF Parsing | pypdf |

## Building and Running

### Environment Setup

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
.venv/Scripts/python.exe -m playwright install chromium
```

Copy `.env.example` → `.env` and fill in API keys (DeepSeek recommended as primary LLM).

### Start Backend + Frontend (one command)

```bash
# Windows
start_frontend.bat
# Or manually:
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181
```

- Frontend: <http://127.0.0.1:18181/web/>
- API docs: <http://127.0.0.1:18181/docs>
- Health: <http://127.0.0.1:18181/health>

### Tests

```bash
# All tests
.venv/Scripts/python.exe -m pytest

# Backend only
.venv/Scripts/python.exe -m pytest apps/api/tests -v

# Frontend e2e only
.venv/Scripts/python.exe -m pytest apps/web/e2e -v

# Specific session
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session66_agent.py -v
```

Pytest config: `asyncio_mode=auto`, testpaths = `apps/api/tests`, `apps/web/e2e`. Markers: `react-web`, `legacy-web`, `re02`, `re03`, `network`.

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
      main.py                     # FastAPI entry, CORS, route registration, static mount
      api/v1/research.py          # Main REST router (submit, status, SSE stream, evidence graph, papers)
      services/
        llm_router.py             # Provider profile → concrete provider mapping (fast_json / execution / premium_review)
        llm.py                    # Low-level LLM client (DeepSeek, StepFun, VOAPI)
        json_repair.py             # 3-phase JSON parsing: direct → reasoning scan → fallback formatter
        agents/
          graph/
            state.py               # ResearchState TypedDict — shared state for all graph nodes
            research_graph.py     # LangGraph builder (nodes + edges + conditional routing)
            nodes/                # 20 graph nodes (intake → topic_parser → search_planner → retrieve → quality_filter → verify → citation_expander → feasibility → ... → review)
          *.py                     # Agent modules (candidate_pool, evidence_review, retrieval_orchestrator, etc.)
          prompts/                 # LLM prompt templates
        retrieval/
          adapters/                # 7 search adapters: arxiv, crossref, github, openalex, semantic_scholar, huggingface, core
    tests/                         # 90+ test files, one per session/feature
  web/
    index.html                     # Vanilla JS frontend (single-page evidence workbench)
    e2e/                           # Playwright e2e tests
docs/                              # Demo scripts, deployment runbook, testing matrix, project scope
Plan/                              # SOP documents (Re3.0/Re3.1 design specs)
scripts/                           # Utility scripts (eval dataset builder, retrieval smoke test)
```

### LangGraph Pipeline

The research pipeline is a LangGraph state machine. Each node receives the shared `ResearchState` TypedDict and returns a partial patch. Nodes **must not** mutate state in place.

Key nodes (in `apps/api/app/services/agents/graph/nodes/`):

| Node | Purpose |
|---|---|
| `intake` | Receive topic + user constraints |
| `topic_parser` | LLM-based keyword decomposition (method/task/object words) |
| `search_planner` | Generate query matrix for multi-source search |
| `retrieve` | Fan-out to 7 adapters in parallel (arXiv, Crossref, GitHub, OpenAlex, S2, HuggingFace, Core) |
| `quality_filter` | Pre-filter raw results (heuristic + LLM judge) |
| `verify` | Multi-round paper verification (accept / weak_reject / reject) |
| `citation_expander` | Seed paper selection → citation/reference expansion |
| `dataset_repo_extractor` | Extract dataset/repo candidates from verified papers |
| `feasibility_assessor` | 5-tier feasibility judgment |
| `innovation_extractor` | Identify innovation points |
| `sota_matcher` | Compare against SOTA |
| `narrative_builder` | Construct research narrative |
| `optimization_advisor` | Suggest optimization directions |
| `devils_advocate_node` | Reflection loop (counter-based revision) |
| `review` | Final quality review |

### LLM Provider Routing

Profiles map to providers via `llm_router.py`:

| Profile | Default Provider | Purpose |
|---|---|---|
| `fast_json` | DeepSeek (fallback: StepFun) | JSON-producing nodes (parser, planner, verifier) |
| `execution` | StepFun | Simple execution, no final judgment |
| `premium_review` | VOAPI | Final sampling review only |

Controlled via env: `LLM_PROFILE`, `FAST_JSON_PRIMARY`, `DEEPSEEK_API_KEY`, `STEPFUN_API_KEY`.

### API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/research/` | Submit a topic for background research graph run |
| GET | `/api/v1/research/` | List all case IDs with results on disk |
| GET | `/api/v1/research/{case_id}/status` | Check run status |
| GET | `/api/v1/research/{case_id}/state` | Full final ResearchState JSON |
| GET | `/api/v1/research/{case_id}/trace` | Per-node trace events |
| GET | `/api/v1/research/{case_id}/evidence-graph` | Evidence graph (nodes + edges) |
| GET | `/api/v1/research/{case_id}/stream` | SSE stream of node progress (real-time) |
| POST | `/api/v1/research/{case_id}/papers` | Upload a user-known paper (enriched via Crossref/arXiv) |
| GET | `/api/v1/research/{case_id}/feasibility` | Feasibility report |
| GET | `/api/v1/research/{case_id}/review` | Final review report |

Results are persisted under `tmp_re13_eval/{case_id}/` (state.json, trace.json, evidence_graph.json).

## Development Conventions

### Hardcoding Bans (from `rules.md`)

- **No hardcoded domain fallbacks** — never default to `"deep learning"` or fixed domain strings.
- **No hardcoded `domain_map`** — LLM is the primary path, not pattern matching.
- **No short-keyword filtering** by length — "YOLO" (4), "SLAM" (4), "GAN" (3) must pass.
- **No domain-specific words in prompt examples** — LLM will mimic example direction.
- **No hardcoded regex/blacklist** for self-checking — use LLM judgment.

### Search Chain Rules

- All adapters share the same query list from `search_planner`.
- Empty queries → use topic text, never a fixed string.
- One adapter 429/timeout must not block the pipeline (other adapters proceed independently).
- GitHub results go to `repo_candidates`, not `verified_papers`.

### JSON Parsing Robustness (from `CLAUDE.md`)

- System prompts for reasoner models must be <100 tokens.
- `call_json` calls must pass `expected="dict"` for structured nodes.
- Prompt must end with an OUTPUT CONTRACT clause.
- 3-phase parse: direct → reasoning field scan → fallback formatter (with schema hint).
- No silent error swallowing — retries must log warnings.

### Async & Concurrency

- I/O-intensive operations must use `asyncio.gather` / `asyncio.Semaphore`.
- Cross-source searches (Crossref/GitHub/arXiv) are inherently parallel — no serial waiting.
- API calls need rate limiting (Semaphore 3-5 concurrent, exponential backoff on 429).
- Tasks >60s should be delegated to subagents; main thread does productive work while waiting.

### Testing Strategy (from `AGENTS.md`)

- Independent test cases with total runtime >60s **must** be parallelized via subagents.
- Single tests <10s or total <60s → run serially (subagent overhead not worth it).
- >10 test cases: first 3 get full assertions, rest degrade to smoke test (no crash + non-empty output).
- Main thread must not idle while subagents run — review code, write prompts, check docs.
- Results are batch-summarized, not processed one-by-one.

### API Compatibility

- New backend/provider/adapter must not modify or delete existing call code.
- New features coexist with old ones, switched via config/parameters.
- All changes must be backward-compatible.

### Compliance Boundaries

- `rejected` evidence is never cited; `pending` doesn't directly support; `failed verification` doesn't support.
- No bypassing paywalled databases (Semantic Scholar: metadata only; Kaggle: listing only).
- No uploading user files to third-party services.
- All LLM credentials read from `.env` (never committed to git).
- LLM path can degrade to heuristic fallback without crashing the service.

### Code Style

- Python 3.12+ features are expected (e.g., `str | None`, `dict[str, Any]`).
- `from __future__ import annotations` is used in most modules.
- Pydantic v2 for all schemas.
- Functions return partial state patches (LangGraph merge pattern), not in-place mutation.
- Extensive trace event logging (`trace_events` list in ResearchState).
