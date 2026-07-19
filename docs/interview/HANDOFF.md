# PaperAgent PR #28 Final Handoff

## Status

```text
Repository:       ZyfNO2/PaperAgent
Base:             master@4599053b6efda464aee1fe242db801427384a6c2
PR:               #28 (Draft)
Branch:           feat/gold-case-rag-interview-readiness
Validated SHA:    7b9cd752e63da6de04ebe851d86daaa69b6af7b0
Merge performed:  no
Release performed:no
Scientific PASS:  not claimed
```

PR #28 delivers one deterministic NPC/Game-AI Gold Case, layered RAG/evidence metrics, and
interview evidence. It remains separate from formal Gate L PR #26.

## Code Review fixes

1. **Report integrity** — Gold Case contract v2 recomputes its canonical SHA-256 on load, requires the
   complete acceptance-check set, derives checks from fields, and rejects status/check/digest drift.
2. **Evidence-domain separation** — a baseline paper no longer counts as proof that baseline training
   was reproduced. Reproduction remains trusted server-owned execution metadata.
3. **RAG contract hardening** — blank/duplicate identities, invalid ranks, unknown evidence links,
   impossible token accounting, vacuous success, invalid blocker state, out-of-range rates, duplicate
   aggregate case IDs, and inconsistent cutoff/distribution contracts are rejected.
4. **Exact-head binding** — CI explicitly checks out the PR head SHA, verifies `git rev-parse HEAD`,
   and stores that SHA in the artifact.
5. **Coverage fail-closed** — CI now uses `--cov-fail-under=90` and independently detects the
   coverage-failure message. The threshold was not lowered and no production file was excluded.

## Accepted evidence

```text
Gold Case run:        29692733977 — SUCCESS
Repository CI:        29692733976 — SUCCESS
Academic evaluation: 29692733975 — SUCCESS
Interview evidence:  29692733996 — SUCCESS
Release hardening:    29692733982 — SUCCESS
Artifact ID:          8444082250
Artifact digest:      sha256:891fdacda082d9ca2e57dcc671365936bab8bf737d3101185f347767944bc65a
Report digest:        92ca0f35d3bf3d44a1d8ee33469168d6730d266ed5a8ddd7fcd97034d695bbea
```

```text
Python 3.11 focused:  PASS
Python 3.12 focused:  PASS
Full tests:           408 passed / 11 skipped / 0 failed
JUnit:                419 tests / 0 failures / 0 errors / 11 skipped
Branch coverage:      90.64 percent
Required coverage:    90 percent
Artifact source SHA:  matched 7b9cd752e63da6de04ebe851d86daaa69b6af7b0
```

The earlier artifact showing `89.90%` coverage is preserved as negative evidence and is superseded.

## Gold Case result

```text
contract:             paperagent.gold-case.v2
case:                 npc-go-complete
decision / audit:     GO / GO
rubric:               100 / minimum 90
evidence scope:       synthetic_evaluation
readiness:            synthetic_evaluation_only
scientific ready:     false
Recall@1/3/5:         0.25 / 0.75 / 1.00
Precision@1/3/5:      1.00 / 1.00 / 1.00
citation support:     1.00
unsupported claims:   0.00
LLM calls/tokens/cost:0 / 0 / 0 USD
```

These values prove deterministic engineering contract convergence only. They do not prove real-paper
correctness, real baseline reproduction, novelty, empirical gains, live-provider quality, or formal
scientific acceptance.

## Reproduction

```bash
python -m pip install -e '.[dev,release]'
python scripts/run_gold_case_readiness.py --output build/gold-case/report.json
python scripts/build_interview_readiness.py \
  --input build/gold-case/report.json \
  --output build/gold-case/interview-readiness.md
```

## Interview framing

```text
Research contract
→ evidence cards
→ server-owned baseline facts
→ module contracts
→ canonical audit
→ GO / REVISE / NO_GO
→ RAG/evidence metrics
→ digest-bound report
```

State explicitly that citation support is a structural evaluator-owned Claim-to-Evidence metric.
Exact answer-span citation binding and independent semantic-entailment review belong to a future real
RAG benchmark and are not delivered by PR #28.
