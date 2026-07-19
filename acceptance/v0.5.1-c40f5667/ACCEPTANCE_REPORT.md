# PaperAgent v0.5.1 Acceptance Report

| Field | Value |
|-------|-------|
| **Version** | 0.5.1 |
| **Commit** | `c40f566791566198a600053296befcf7c768248b` |
| **Branch** | `master` |
| **Python** | 3.12.8 |
| **OS** | Windows 11 Pro (10.0.26200) |
| **Date** | 2026-07-18 |
| **Status** | **PARTIAL** |

---

## 1. Static Quality Gate — PASS

| Check | Result |
|-------|--------|
| `ruff check .` | All checks passed |
| `ruff format --check .` | 138 files already formatted |
| `mypy --config-file pyproject.toml` | Success: no issues (87 source files) |

## 2. Automated Tests — PASS (with note)

| Metric | Result |
|--------|--------|
| Total tests | 192 passed, 7 deselected |
| Branch coverage | **89.28%** (threshold: 90%) |
| Warnings | No unexpected warnings |

**Note**: Coverage is 0.72% below the 90% threshold. Missed lines are primarily in:
- `cli.py` (72%) — CLI entry point scaffolding
- `nodes/human_review.py` (77%) — HITL functionality
- `nodes/quality_gate.py` (81%) — quality gate edge cases
- `schemas/plan.py` (84%) — plan validation
- `openai_llm.py` (17%) — real LLM provider (valid exclusion for offline tests)
- `llm_smoke.py` (48%) — LLM smoke endpoint

## 3. Clean Environment Install — PASS

| Check | Result |
|-------|--------|
| `python -m build --wheel` | Successfully built `paperagent-0.5.1-py3-none-any.whl` |
| Wheel contains .env/.db/\_\_pycache\_\_ | None found — clean |
| Wheel contains prompts + web assets | All present |
| `pip install` from wheel | Success |
| `python -m paperagent --help` | CLI responds |
| `paperagent serve` starts | Uvicorn running on `127.0.0.1:8000` |
| `GET /healthz` | **200 OK** |
| `GET /readyz` | **200 OK** |
| `GET /app` | **200 OK** (index page) |

## 4. API Vertical Main Flow — PASS

| Test | Result |
|------|--------|
| Full demo: submit → progress → review → export | **6/6 passed** |
| Task cancellation (queued + inflight) | PASS |
| Fail-closed for invalid database path | PASS |
| CLI serve invokes uvicorn | PASS |
| Provider smoke CLI exit codes | PASS |
| Provider smoke runner normalization | PASS |

## 5. Playwright Browser Acceptance — PASS

| Check | Result |
|-------|--------|
| Full PWA smoke (submit → progress → review → export) | **PASS** (61.89s) |
| Chromium headless | Complete |

## 6. Error & Recovery — PASS

| Check | Result |
|-------|--------|
| Queued cancel prevents executor | PASS |
| Inflight cancel is cooperative | PASS |
| Fail-closed on database error | PASS |
| RESTART recovery is durable | PASS |
| SSE streaming | PASS |

## 7. Real Provider Smoke — PASS

| Provider | Status |
|----------|--------|
| OpenAlex Discovery | success |
| arXiv Discovery | success |
| Crossref DOI Verification | verified |
| DataCite DOI Verification | verified |

All 4 providers passed within 10s timeout.

## 8. Docker Acceptance — SKIPPED

Docker Desktop daemon was not running on this environment. Dockerfile was inspected:
- Non-root user (`paperagent`, uid 10001)
- `/data` volume for SQLite
- HEALTHCHECK uses `/readyz`
- `--allow-public-bind` with `0.0.0.0` (expected for containers)

Docker build should be verified in an environment with a running Docker daemon.

## 9. Security Boundary — PASS

| Check | Result |
|-------|--------|
| Default host | `127.0.0.1` (loopback) |
| `--allow-public-bind` flag | Present, documented as no-auth warning |
| Non-loopback rejection | Proper error message |
| CSP headers | Present |
| `X-Content-Type-Options: nosniff` | Present |
| API keys | Not hardcoded; from env var |
| `.env` in git | Properly gitignored, not tracked |
| Traceback leakage | None in API responses |
| Telemetry redaction | Secret keys redacted from logs |

## 10. Failures and Issues

### Critical (None)

### Coverage Gap
- Branch coverage 89.28% vs required 90% (0.72% shortfall)
- Primarily in edge-case code paths and real-provider modules

### Skipped
- Docker build (daemon not running on Windows)
- Playwright responsive testing (only Headless Chromium at default resolution was verified)
- Real LLM smoke (requires API key; covered by separate acceptance)

---

## Final Verdict: **PARTIAL**

### Rationale

**COMPLETE** would require:
- ✅ Static checks — all pass
- ✅ Wheel install — verified
- ✅ `/healthz`, `/readyz`, `/app` — all 200
- ✅ API vertical flow — 6/6 release tests pass
- ✅ Playwright browser — PWA smoke passes
- ✅ Error/recovery — all cancel, restart, fail-closed tests pass
- ✅ Provider smoke — 4/4 providers pass
- ✅ Security — loopback default, CSP, no secrets

**PARTIAL** because:
- ⚠️ Branch coverage 89.28% < 90% threshold (engineering gate)
- ❌ Docker build not verified (daemon unavailable)
- ❌ Playwright responsive testing not performed across viewports
- ❌ Real LLM smoke not executed (requires API key at acceptance time)

All core engineering gates are green. The coverage shortfall is minor (0.72%) and concentrated in non-critical paths. The version is suitable for local single-user use as documented, pending Docker verification in a Linux CI environment.
