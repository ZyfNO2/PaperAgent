# H3 cross-paper acceptance package

`scenarios.v1.json` freezes two baseline/module scenario identities but deliberately
does not contain expected decisions or gold claims. Run:

```powershell
python -m paperagent.academic.acceptance `
  evals/academic_rag_h3/scenarios.v1.json `
  --output output/academic-h3/acceptance-package.json
```

Exit code `2` and status `blocked_by_human_review` are expected until a human reviewer
fills `expected_decision`, `expected_claims`, and `reviewer_notes`. A FakeModel,
deterministic draft, or LLM must not populate those fields and call them human gold.
