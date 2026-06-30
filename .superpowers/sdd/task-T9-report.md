# T9 Report: Frontend Step-by-Step Confirmation Flow

## Summary

Added a 7-state machine to `UserWorkbenchPage.tsx` that splits the research
planning flow into human checkpoints: keyword parsing → search plan →
evidence → direction. Each stage renders a dedicated confirmation card
with editable tags and explicit confirm buttons. The flow now stops at
direction confirmation — no proposal generation, per the task brief.

## Changes

### State machine (file: `UserWorkbenchPage.tsx`)

- New types: `SearchPlan`, `DirectionAdvice`, `ResearchState`.
- New state variables: `researchState`, `parsedKeywords`, `searchPlan`,
  `evidenceData`, `direction`.
- New transitions: `confirmKeywords`, `confirmSearchPlan`,
  `collectEvidence`, `confirmDirection`.
- `onStart` now seeds `parsedKeywords` from the existing
  `analyze` response and transitions to `keywords_confirm`.

### Render cards

- `renderKeywordsConfirm` — five chip groups
  (method/task/object/scenario/metric + risk), each chip removable
  via `×` button. Confirm advances to `searching`.
- `renderSearchPlan` — three collapsible `<details>` sections
  (paper / dataset / repo queries). Confirm advances to `evidence`.
- `renderEvidence` — three EvidenceList cards reusing the existing
  component (papers / datasets / baselines). Collect button advances
  to `direction`.
- `renderDirection` — three Cards (safe / enhancement / fallback),
  each item is a `pa-uw-result-item` with Badge. Confirm button
  advances to `confirmed` and pushes a system message; no proposal
  is generated.

### Derivation strategy

The step-by-step UI reuses the single existing
`/api/v1/one-topic/analyze` response — no new endpoints, no new
backend calls. The intermediate states (`searchPlan`, `direction`)
are computed client-side from `parsedKeywords` and
`analysis.evidence_summary`. This keeps the deliverable scoped to
the frontend flow per the brief's "API integration" note.

## Wiring

After `AnalysisResults`, the JSX conditionally renders one of:

```tsx
{researchState === 'keywords_confirm' ? renderKeywordsConfirm() : null}
{researchState === 'searching'       ? renderSearchPlan()     : null}
{researchState === 'evidence'        ? renderEvidence()       : null}
{researchState === 'direction' || researchState === 'confirmed' ? renderDirection() : null}
```

## Out of scope (per brief)

- No new backend endpoints.
- TopBar / SideNav unchanged.
- RAG Eval / Thesis Eval pages untouched.

## Verification

- `npx tsc --noEmit` — clean, no errors.
- All new state vars and render functions are referenced in the
  final JSX — no unused-symbol warnings remain.