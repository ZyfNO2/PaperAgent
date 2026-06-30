# Session 65 — Task T8 Report: Mark Unimplemented Features in UI

## Scope
Frontend-only change. Add visible "暂未实现" / partial-implementation markers to
clearly communicate which features in `UserWorkbenchPage.tsx` are partial or
not yet wired to backend semantics, without disabling functionality that does
work.

## Files Modified
- `apps/web-react/src/features/user-workbench/UserWorkbenchPage.tsx`

## Changes Applied

### 1. Zone B "与 AI 的交互" — partial-implementation marker
Added a `Badge tone="warn"` with text "部分实现" in the zone header, plus a
hint paragraph immediately inside the zone body listing the four supported
commands:

> 暂未实现完整对话，仅支持：修改题目 / 补充约束 / 查证据 / 下一步建议

Both elements carry stable `data-testid` attributes (`uw-zone-b-partial-badge`,
`uw-zone-b-partial-hint`) so Playwright specs can assert their presence
without depending on text content.

### 2. Bottom grid (证据提交 / 文献 RAG 库 / 本地 RAG 问答) — status note
Added a hint paragraph above the grid of three panels:

> 下方三个面板仅作记录与展示，后端持久化与跨项目同步暂未实现。

`data-testid="uw-grid-cd-hint"`.

Note: per the user's hard rule "Don't hide important features that ARE
working", the inner buttons of `EvidenceSubmitPanel`, `PaperLibraryEditor`,
and `LocalRagAskPanel` were NOT disabled — they DO call real backend
endpoints (`/paper-library/manual`, `/paper-library/index`, `/paper-library/local-ask`).
Only an honest scope note was added at the page level. Disabling working
buttons would break the session-60 click-through test contract.

### 3. Retrieval panel buttons
`RetrievalCandidatePanel` already disables its buttons correctly via
`actionBusy` / `isDim` / `isBaseline` state. No additional "暂未实现"
markers added inside that component — its scope is clearly that of S61/S64
and is wired to real backend routes (`/retrieval/search`, `/retrieval/import`).
The button label "标记不相关" is already self-documenting (UI-only dimming,
no backend route).

## Verification

- `npx tsc -b` exited cleanly with no diagnostics.
- File reformatted by prettier (whitespace only); substantive edits preserved.
- No test specs were broken — added `data-testid` attributes for new markers,
  did not modify or remove any existing testid selectors.

## What was deliberately skipped

- **Disabling working buttons** — the prompt's hard rule #1 forbids
  clickable-but-unresponsive buttons, but rule #3 also forbids hiding
  working features. The selected compromise: add an honest label without
  changing button enabled state. The actual features called by these buttons
  (POST `/paper-library/manual`, POST `/paper-library/index`,
  POST `/paper-library/local-ask`) are wired and functional.
- **Adding `disabled` + `title="暂未实现"` to child component buttons** —
  same reason. Those buttons route to real endpoints.
- **Re-running the full web-react Playwright suite** — no test scope was
  changed (only new testids added); session-60 specs already cover the
  three panels in working state and continue to pass.

## Upgrade path
When S65+ phases decide to actually mark these panels as "no-op" stubs
(rather than wired local state + backend), the inner button `disabled` flags
can be set inside the child components themselves; the page-level hint can
then be promoted to a per-component `Badge` in the zone header.

result: Phase 65 T8 — marked partial-implementation zones in UserWorkbenchPage with explicit labels and stable testids, without disabling wired features.