# PaperAgent Local Runbook

## Quick Start
```bash
# Start API server (port 18181)
cd G:\PaperAgent
python -m apps.api.app.main

# Start React dev server (port 18183, proxies to 18181)
cd apps\web-react
npm run dev
```

## Common Operations

### 1. No API Key / Bad API Key
**Symptom:** `LLMUnavailable: API key not set`
**Fix:** Set `DEEPSEEK_API_KEY` or `OPENCODE_API_KEY` in `.env`:
```env
OPENCODE_API_KEY=sk-xxxxx
OPENCODE_MODEL=big-pickle
DEEPSEEK_API_KEY=sk-xxxxx
```
Restart API server after changing.

### 2. Context Window Exceeded
**Symptom:** `HTTP 400: context_length_exceeded` or truncated output
**Fix:** Reduce prompt size — verified papers list is automatically truncated to top 10 for novelty review. If persistent, reduce `LLM_THINKING_BUDGET`:
```env
LLM_THINKING_BUDGET=4000
```

### 3. Provider Rate Limited (429)
**Symptom:** `HTTP 429` with long pauses
**Fix:** The system retries with exponential backoff (2s, 4s). If persistent:
```env
LLM_RPM_LIMIT=5
```
Reduce concurrency or wait 1-2 minutes.

### 4. All Providers Exhausted
**Symptom:** `ContractResult.error = "all providers exhausted"`
**Fix:** Check:
1. API keys are valid (not expired)
2. Base URLs are reachable
3. No firewall blocking outgoing HTTPS
4. Provider status via `GET /api/v1/research/health/providers`

### 5. Empty Repair / No Recovery
**Symptom:** JSON repair fails, fallback exhausted
**Fix:** Set `allow_heuristic=true` in ModelPolicy for affected role (Settings page → Role Matrix). This returns partial results when structured output fails.

### 6. Invalid Provider URL
**Symptom:** `ConnectionError` or DNS failure
**Fix:** Base URL must be HTTPS. Localhost URLs are warned. Validate via Settings → Add Provider → Validate step.

### 7. Model Discovery Fails
**Symptom:** "Auto-discovery unavailable" in wizard
**Fix:** Enter model ID manually. Allowed values: `deepseek-v4-flash`, `big-pickle`.

### 8. Research Never Completes
**Symptom:** Stuck on a node for >5 minutes
**Fix:** Check SSE stream for error events. The pipeline will exhaust retries and return partial results. Cancel via stopping the API request.

### 9. Frontend Shows Blank / Errors
**Symptom:** White page, console errors
**Fix:**
1. Verify API server is running (`curl http://127.0.0.1:18181/api/v1/research/`)
2. Check CORS: API must allow `http://localhost:18183`
3. Clear browser cache and reload
