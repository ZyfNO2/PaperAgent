# T7 Report: Integrate research modules into retrieval layer

## Scope

Hook the T2/T3 research modules (`research_topic_parser.parse_topic_rule_based`,
`research_query_builder.rule_fill_query_pack`) into the retrieval-layer query plan
so domain-aware queries are emitted alongside the existing heuristic layers.

## Files changed

- `apps/api/app/services/retrieval/query_plan.py` — added optional import,
  injected a `"research"` layer at the top of `paper_queries` / `dataset_queries`
  / `repo_queries` when the modules are importable and `raw_topic` is non-empty.

`orchestrator.py` was intentionally NOT modified. The existing `REGISTRY`-based
adapter dispatch already calls the same adapter functions as `research_tool_router`
(`arxiv_search`, `openalex_search`, etc.). The router adds trace-event uniformity
but the orchestrator already writes its own `retrieval_source_failed` /
`retrieval_run_started` / `retrieval_run_completed` events. Routing through the
router would be duplicate trace work without behavioral gain, so it stays optional
per the T7 brief.

## Design (ponytail ladder)

1. Does the change need to exist? Yes — domain routing is a T6 deliverable that
   retrieval needs to honour.
2. Already in the codebase? Research modules exist (T2/T3). Reuse.
3. Stdlib? No new dep needed.
4. Native platform? N/A.
5. Installed dep? Modules are already committed.
6. One line? The integration is ~10 lines, which is the minimum that preserves
   the fallback + handles errors.

Concretely:
- Import is wrapped in `try/except ImportError` with a `HAS_RESEARCH_MODULES`
  flag — silent fallback if modules missing (e.g., partial checkout).
- Call is wrapped in `try/except Exception` — silent fallback on runtime
  failure (e.g., LLM crash on import-time side-effect).
- The `"research"` layer is appended FIRST in the layer list. The orchestrator's
  `_queries_for()` concatenates all layers in order, so research queries fire
  first; heuristic queries (`L0-L5`, `dataset`, `repo`) still execute after as
  the existing fallback/补搜 layer.

## Layer ordering (output of `build_query_plan('p1', '基于三维成像的损伤智能检测')`)

```
paper:   [('research', 6), ('L0-L5', 5)]
dataset: [('research', 5), ('dataset', 3)]
repo:    [('research', 5), ('repo', 2)]
paper[0]: ['detection point cloud 3D imaging', '3D detection 3D imaging',
           'detection 3D point cloud']
```

The research layer surfaces domain-aware English queries (e.g. "3D detection
3D imaging" instead of the original Chinese). The heuristic layer still emits
the Chinese raw topic and the English hint concatenation, so if research fails
silently the original behaviour is preserved bit-for-bit.

## Backward compatibility

- `build_query_plan()` signature unchanged.
- `QueryPlan` schema unchanged (`extra='forbid'`).
- Layers are additive — the `L0-L5` / `dataset` / `repo` layers are still
  emitted after the `research` layer with the same content as before.
- Empty `raw_topic` returns the same empty plan as before (research path
  guarded by `if HAS_RESEARCH_MODULES and raw`).

## Regression checks

- `tests/test_session63_topic_driven_retrieval.py` — 13 passed (research
  module behaviour intact).
- `tests/test_session61_retrieval_enhancement.py` — 19 passed (orchestrator
  integration + gap report + retry + candidate actions unchanged).
- `tests/test_session14_multi_source_retrieval.py` — 19 passed, 1 skipped
  (full retrieval flow unchanged).

Total: 51 passed, 1 skipped, 0 failed.

## Skipped

- Routing adapters through `research_tool_router` inside the orchestrator.
  Existing `REGISTRY[source]` path already calls the same adapter functions.
  The router adds trace-event uniformity, but the orchestrator writes its own
  scoped trace events. Re-routing would duplicate writes without changing
  candidate output. Add when the orchestrator is refactored to delegate all
  trace emission to the router (future cleanup, not part of T7 scope).