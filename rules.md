# PaperAgent Project Rules

> Consolidated from Re1.1 through Re3.0 design SOPs.
> All contributors and agents MUST follow these rules.

## 1. Hardcoding Bans

- **No hardcoded domain fallbacks** — never default to `"deep learning"` or any fixed domain string. When atoms/domain are empty, use the topic text as-is.
- **No hardcoded `domain_map`** — LLM is the primary path for domain inference, not pattern matching. Do not maintain a static domain→query mapping.
- **No short-keyword filtering by length** — keywords like "YOLO" (4), "SLAM" (4), "GAN" (3) must pass. Minimum length is 2 characters (`len(q) >= 2`).
- **No domain-specific words in prompt examples** — LLM will mimic example direction. Use neutral, abstract examples only.
- **No hardcoded regex/blacklist for self-checking** — use LLM judgment for quality filtering, not pattern-based blacklists.

## 2. Search Chain Rules

- All adapters share the same query list from `search_planner`.
- Empty queries → use topic text, never a fixed string.
- One adapter 429/timeout must not block the pipeline (other adapters proceed independently).
- GitHub results go to `repo_candidates`, not `verified_papers`.
- Cross-source deduplication uses normalized title (strip punctuation, collapse whitespace) + DOI priority.
- Crossref `component`/`book-section`/`book-part`/`book-series` types are filtered out in quality_filter.

## 3. JSON Parsing Robustness

- System prompts for reasoner models must be <100 tokens.
- `call_json` calls must pass `expected="dict"` for structured nodes, `expected="list"` for batch verifiers.
- Prompt must end with an OUTPUT CONTRACT clause.
- 3-phase parse: direct → reasoning field scan → fallback formatter (with schema hint).
- No silent error swallowing — retries must log warnings.

## 4. Async & Concurrency

- I/O-intensive operations must use `asyncio.gather` / `asyncio.Semaphore`.
- Cross-source searches are inherently parallel — no serial waiting.
- API calls need rate limiting (Semaphore 3-5 concurrent, exponential backoff on 429).
- In FastAPI BackgroundThreads, use `_run_tool_sync` (not bare `asyncio.run()`) to avoid event loop nesting crashes.
- Tasks >60s should be delegated to subagents; main thread does productive work while waiting.

## 5. Graph Configuration

- `recursion_limit` must be set to 100 (LangGraph default 25 is insufficient for 20+ node graph with repair + citation + devils_advocate loops).
- `MAX_REPAIR_ROUNDS` reads from env `PAPERAGENT_MAX_REPAIR_ROUNDS` (default 2) — do not hardcode.
- Nodes return partial state patches (LangGraph merge pattern), never mutate state in place.
- `research_narrative` (singular) is the canonical field name — not `research_narratives` (plural).

## 6. Testing Strategy

- Independent test cases with total runtime >60s should be parallelized via subagents.
- Single tests <10s or total <60s → run serially (subagent overhead not worth it).
- >10 test cases: first 3 get full assertions, rest degrade to smoke test (no crash + non-empty output).
- Main thread must not idle while subagents run — review code, write prompts, check docs.
- Results are batch-summarized, not processed one-by-one.
- Real LLM end-to-end tests (3-case minimum) must be run before declaring a SOP complete.

## 7. API Compatibility

- New backend/provider/adapter must not modify or delete existing call code.
- New features coexist with old ones, switched via config/parameters.
- All changes must be backward-compatible.
- New adapters must be registered in `adapters/__init__.py` REGISTRY and exposed in `search_agent` available_tools.

## 8. Compliance Boundaries

- `rejected` evidence is never cited; `pending` doesn't directly support; `failed verification` doesn't support.
- No bypassing paywalled databases (Semantic Scholar: metadata only; Kaggle: listing only).
- No uploading user files to third-party services.
- All LLM credentials read from `.env` (never committed to git).
- LLM path can degrade to heuristic fallback without crashing the service.
- VOAPI/MiniMax must not be used unless explicitly required (default: DeepSeek/StepFun only).

## 9. Code Style

- Python 3.12+ features are expected (e.g., `str | None`, `dict[str, Any]`).
- `from __future__ import annotations` is used in most modules.
- Pydantic v2 for all schemas.
- Functions return partial state patches (LangGraph merge pattern), not in-place mutation.
- Extensive trace event logging (`trace_events` list in ResearchState).

## 10. Prompt Hygiene

- No domain-specific example words (steel, crack, concrete, defect, inspection) in prompt templates.
- "concrete" as an English adjective (meaning "specific/tangible") is acceptable.
- Method-name examples (YOLO, SLAM) in prompts are acceptable as generic method references.
- Every LLM prompt must end with an OUTPUT CONTRACT specifying the exact JSON schema expected.

## 11. Self-Verification

- After code changes, run the project's test suite: `python -m pytest`.
- After structural changes, run `python -m ruff check .` for linting.
- After adapter/graph changes, verify with at least a 3-case smoke test.
- After prompt changes, verify no domain bias leakage in outputs.
