# Release / No-Go Checklist — Re6.x

## Hard No-Go Conditions

All must be ✅ before production release.

- [ ] **NG-01: No raw API key in logs.** Grep for key patterns; all occurrences redacted.
- [ ] **NG-02: No raw API key in trace.** All trace JSON files audited; keys replaced with `<REDACTED>`.
- [ ] **NG-03: No raw API key in git.** `git log --all -p | grep -i api_key` returns 0 matches.
- [ ] **NG-04: No raw API key in SSR/SSRF error pages.** Error responses only contain `"api_key_set": true`.
- [ ] **NG-05: No false evidence generation.** 10-case cross-domain verification passes P0 (0 fabricated papers/repos/datasets).
- [ ] **NG-06: All contracts pass L0 tests.** `python -m pytest apps/api/tests/test_re6/ -q` → 100% pass.
- [ ] **NG-07: No regression on Re5 search.** 100-paper search regression: ≥90% completion, 0 crashes.
- [ ] **NG-08: RAG citations traceable.** All RAG answers with `cited_chunks` must have `location_verified=True`.

## Soft Go Conditions

Recommended but not blocking for MVP:

- [ ] **SG-01:** L2 replay: provider chain identical for same (prompt, contract, policy).
- [ ] **SG-02:** L3 hidden-OOD: ≥60% verdict agreement across 12 cross-domain cases.
- [ ] **SG-03:** Fallback ledger: all fallback events have error classification.
- [ ] **SG-04:** Snapshot viewer displays run provenance (Settings → Snapshots).
- [ ] **SG-05:** Role Routing Matrix save/persist works (Settings → Role Matrix).
- [ ] **SG-06:** Evolution log tracks all novelty status changes.

## Security Pre-Release Audit

| Check | Method | Result |
|---|---|---|
| API keys in log files | `rg -i 'sk-' logs/` | — |
| API keys in git history | `git log -p \| rg 'sk-'` | — |
| API keys in trace JSON | `rg 'api.key' tmp_re*/trace.json` | — |
| SSRF: provider URL validated | Settings → Add Provider → Step 3 | — |
| SSRF: PDF URL validated | RAG ingest rejects internal IPs | — |
| XSS in error messages | `<script>` in query → escaped | — |
| XSS in RAG answers | Ingested PDF with scripts → escaped | — |

## Release Steps

1. Run `python -m pytest apps/api/tests/test_re6/ -v` — all green
2. Run smoke test with 3 topics (engineering, medical, NLP)
3. Check Runbook covers all 9 scenarios
4. Verify Known Limitations document is accurate
5. Tag release: `git tag v0.4.0-re6`
6. Update CHANGELOG.md
