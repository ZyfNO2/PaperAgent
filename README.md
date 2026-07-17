# PaperAgent

PaperAgent `v0.1` is a clean, test-driven rebuild of the research workflow skeleton. The branch
contains no imports from the legacy Re1-Re8 implementation.

## Current status

```text
Version: v0.1
Stage: offline implementation complete
Implementation: bounded LangGraph skeleton
Development method: mandatory TDD
Release status: Draft PR / real-provider smoke pending
```

## Implemented scope

- frozen Pydantic schema and TypedDict State contracts;
- versioned production prompt registry and deterministic Fake LLM/Search providers;
- bounded Retrieval subgraph with verification, coverage routing, and two-round hard limit;
- structured planning, evidence synthesis, method design, and report workflows;
- deterministic Quality Gate with independent retrieval and method-repair budgets;
- LangGraph Human-in-the-Loop interrupt/resume using checkpoint state;
- redacted Trace metadata and idempotent in-memory final snapshot persistence;
- graph, integration, failure, OOD, leakage, lint, type-check, and coverage gates;
- GitHub Actions verification on Python 3.11 and 3.12.

## Verification

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
mypy --config-file pyproject.toml
pytest -q
pytest --cov=paperagent --cov-branch --cov-report=term-missing -q
```

Default tests are offline and do not read API keys or access the network. The current Draft PR runs
the same quality gates on Python 3.11 and 3.12.

## Development contract

1. [Execution plan](docs/v0.1/EXECUTION_PLAN.md)
2. [Graph and nodes](docs/v0.1/GRAPH_AND_NODES.md)
3. [State and schema contracts](docs/v0.1/STATE_CONTRACTS.md)
4. [TDD strategy](docs/v0.1/TDD_STRATEGY.md)
5. [LLM fixture contract](docs/v0.1/LLM_TEST_FIXTURES.md)
6. [Development workflow](docs/v0.1/DEVELOPMENT_WORKFLOW.md)
7. [Acceptance gates](docs/v0.1/ACCEPTANCE.md)
8. [Implementation handoff](docs/v0.1/HANDOFF.md)

## Later versions

- [Roadmap after v0.1](docs/ROADMAP_AFTER_V0.1.md)
- [v0.2 literature retrieval plan](docs/planning/V0.2_LITERATURE_RETRIEVAL.md)

These later-version documents are planning material only. They do not expand the v0.1 implementation
scope.

## Branch policy

- `master`: clean release line;
- `feat/v0.1-offline-skeleton`: current reviewed implementation branch;
- `v0.1`: design and bootstrap history retained for audit;
- `backup/legacy-pre-v0.1-20260716`: read-only legacy backup.

Do not merge the Draft PR into `master` until review and any explicitly required real-provider smoke
checks are complete.
