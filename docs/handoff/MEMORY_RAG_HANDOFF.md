# Memory and Academic RAG Refactor Handoff

## Repository

- Repository: `ZyfNO2/PaperAgent`
- Base branch: `master`
- Base SHA: `ad44e6337f002aa8ecea3559cc0a2f213e1c8859`
- Development branch: `refactor/paperagent-memory-rag`
- Merge status: not merged

## Direction

The active product direction is upload-first project memory and academic RAG. Public scholarly
provider search is optional and is not treated as an unlimited internal database or a required
workflow dependency.

## Implemented so far

- additive research-project SQLite schema;
- versioned PDF, Markdown, and text ingestion;
- evidence units with paper, version, section, page, paragraph, offsets, and quote locators;
- deterministic local hybrid retrieval;
- proposed/approved/rejected project-memory write gate and audit trail;
- evidence-bound baseline and module planning with scientific BLOCKED reason codes;
- top-level CLI commands for projects, ingestion, retrieval, memory, and tailoring;
- ResNet plus ECA plus mixup vertical regression tests;
- recursive wheel inclusion for existing nested PWA assets.

## Branch and PR cleanup already performed

- Draft PR #61 closed as superseded; not merged.
- Draft PR #62 closed as a temporary CI trigger; not merged.
- Draft PR #60 remains open until its useful runtime semantics are selectively reimplemented.

## Pending repository administration

The current GitHub connector cannot create Git tags or delete branch refs. The following annotated
archive tags still need to be created through Git CLI before any later history rewrite:

```text
archive/paperagent-master-before-memory-rag
archive/paperagent-pr60-method-fixes
archive/paperagent-retrieval-resilience-experiment
```

Do not rewrite `master` until the full vertical acceptance flow passes and these tags exist.

## Verification classification

Local isolated verification before repository CI:

- seven focused project tests passed;
- all new Python files compiled;
- new source and tests satisfy the repository 100-character line limit.

This is offline control-flow and persistence verification. It is not a real training run, not a
real LLM run, and not evidence that the proposed ResNet/ECA/mixup method improves a metric.

## Next steps

1. Run repository Ruff, format, strict Mypy, pytest, coverage, and wheel build in CI.
2. Fix integration and coverage regressions introduced by the new boundary.
3. Selectively port production TaskBudget, provider attribution, scientific blocked routing, and
   quality trace semantics from Draft PR #60.
4. Close PR #60 after those semantics are covered by tests on the refactor branch.
5. Extend the API/PWA only after the CLI and repository boundary are stable.
6. Record the final CI run, commit SHA, limitations, and exact takeover commands in this file.
