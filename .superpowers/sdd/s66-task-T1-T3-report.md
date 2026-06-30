# Task T1-T3 Report: remove legacy score/confidence/EvidenceList/AnalysisResults from main view

## Status: DONE

## What was removed

`apps/web-react/src/features/user-workbench/UserWorkbenchPage.tsx`:

**Deleted functions (per hard rule — full delete, no rename, no CSS hide):**
- `scoreText()` — was used only inside `EvidenceList`
- `EvidenceList()` — main render entry + `renderEvidence` callers
- `AnalysisResults()` — main render entry, the legacy one-shot analysis card
- `AnalysisError()` — depended on `analysisError` state
- `KeywordGroup()` — sub-component of `AnalysisResults`
- `buildRetrieveReply()` / `buildNextStepReply()` — depended on `AnalyzeResponse`

**Deleted state (legacy flow):**
- `analysis` + `setAnalysis`
- `analysisError` + `setAnalysisError`
- `researchState` + `setResearchState`
- `parsedKeywords` + `setParsedKeywords`
- `searchPlan` + `setSearchPlan`
- `evidenceData` + `setEvidenceData`
- `direction` + `setDirection`
- `ResearchState` type alias
- `status` state machine (replaced by `statusLabel` derived from `flowStep`)

**Deleted types (no longer referenced anywhere in the codebase):**
- `TopicUnderstanding`, `KeywordBreakdown`, `EvidenceRef`, `PaperHit`, `DatasetHit`, `BaselineHit`, `EvidenceSummary`, `WorkPackageSuggestion`, `PivotRoute`, `ProposalRecommendation`, `ReviewCheck`, `LightReview`, `FeasibilitySummary`, `AnalyzeResponse`, `SearchPlan`, `DirectionAdvice`

**Deleted helpers:**
- `formatError()` — only used by `analysisError` path
- `compactList()` — only used by `EvidenceList` callers

**Deleted render / step functions (dead after removing `EvidenceList`):**
- `renderKeywordGroup`, `renderKeywordsConfirm`, `renderSearchPlan`, `renderEvidence`, `renderDirection`
- `confirmKeywords`, `confirmSearchPlan`, `buildDirectionFromAnalysis`, `collectEvidence`, `confirmDirection`
- `removeKeyword` — only used by `renderKeywordGroup` (re-added for the new flow's `renderKeywordsReview`)

**Deleted main render entries:**
- `{analysisError ? <AnalysisError .../> : null}` — gone
- `{analysis ? <AnalysisResults .../> : null}` — gone
- `{researchState === 'keywords_confirm' ? renderKeywordsConfirm() : null}` — replaced by `flowStep === "keywords_review"`
- `{researchState === 'searching' ? renderSearchPlan() : null}` — gone
- `{researchState === 'evidence' ? renderEvidence() : null}` — gone
- `{researchState === 'direction' || researchState === 'confirmed' ? renderDirection() : null}` — gone

## What was added

**New main flow state (per T1-T3 brief):**
```ts
type MainFlowStep =
  | "idle"
  | "keywords_review"
  | "retrieval_review"
  | "baseline_select"
  | "work_advice"
  | "stopped";

const [flowStep, setFlowStep] = useState<MainFlowStep>("idle");
const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
const [keywords, setKeywords] = useState<ParsedKeywords | null>(null);
```

**Modified `onStart()`:**
- No longer calls `POST /api/v1/one-topic/analyze`
- No longer calls `setAnalysis(resp)`
- Sets `flowStep = "keywords_review"` instead of `status = "等待确认"`
- Populates an empty `ParsedKeywords` skeleton (real keywords endpoint arrives in T4+)
- `setActiveProjectId(null)` placeholder until T4+

**New `renderKeywordsReview()`:**
- Renders the editable keyword chips (method / task / object / scenario / metric / risk)
- T4+ will hook the confirm button to advance to `retrieval_review`

**Reduced sidebar (Zone B) chat behavior:**
- "修改题目 / 补充约束" still works
- "查证据 / 下一步建议" now returns `unsupported` preview with a note that T4+ will wire the new endpoints

**Cleaned up downstream consumers of `analysis`:**
- `RetrievalCandidatePanel topic` now reads from `topic` (user-confirmed) not `analysis?.topic_understanding.normalized_topic`
- `DirectionDecisionPanel projectId` now reads from `activeProjectId` not `analysis?.project_id`

## Verification

**Forbidden tokens — zero matches:**
```
rg -n "score \{|score 0|confidence|开题解析|低门槛审核|EvidenceList|AnalysisResults" \
  apps/web-react/src/features/user-workbench/UserWorkbenchPage.tsx
→ No matches found
```

**TypeScript clean compile:**
```
cd apps/web-react && node_modules/.bin/tsc --noEmit
→ (no output = success)
```

**Net diff:**
```
-749 / +83 lines  (1037 → 370)
```

## Hard rules honored

1. NO CSS hide — `EvidenceList` and `AnalysisResults` are fully deleted, not `display: none`
2. NO rename — `score` was never renamed to `relevance`; both are gone
3. DELETE entire functions — yes, full body removal
4. rg verified clean — see above

## Skipped

- Existing Playwright tests (`test_session59_user_minimal_shell.py`, `test_session62_*`, `test_session63_*`, `test_session64_*`, `test_session65_*`) still reference `uw-analysis-results`, `uw-confirm-keywords`, `uw-analysis-error`. These will break and need updating — but that test-fixup is out of scope for T1-T3 (it's a test rewriting task, not a UI removal task). Will be addressed in a later task.
- Real keywords endpoint integration — T4+ will replace the empty skeleton in `onStart()` with the actual LLM/heuristic call.
- Other `MainFlowStep` states (`retrieval_review`, `baseline_select`, `work_advice`, `stopped`) — currently unreachable in render; they appear in the `MainFlowStep` union so subsequent tasks can transition into them without touching the type again.

## Commit

`Phase 66 T1-T3: remove legacy score/confidence/EvidenceList/AnalysisResults from main view`