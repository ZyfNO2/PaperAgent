# Known Limitations

## Local Mode (current)

| Limitation | Impact | Workaround |
|---|---|---|
| No persistent provider storage | Provider configs lost on restart | Re-add via Settings wizard |
| Single process API server | No horizontal scaling | Run one instance |
| SQLite state storage | Case data lost if DB deleted | Export results to Markdown |
| No multi-user isolation | All requests share provider configs | Dedicated instance per user |
| API keys in environment variables | Keys in shell/process memory | Rotate keys regularly |
| No TLS on local API | HTTP only (port 18181) | Use on trusted network only |
| Rate limiting is client-side only | 429s from provider still possible | Lower `LLM_RPM_LIMIT` |
| No automated retry on full failure | Must resubmit topic manually | Check Runbook §4 |
| DeepSeek-v4-flash and big-pickle only | Two model whitelist | Cannot add third model |
| Windows line ending drift | LF → CRLF on checkout | Cosmetic only, no functional impact |

## Single-User Server (planned, not implemented)

| Limitation | Impact |
|---|---|
| No authentication | Anyone on network can submit topics |
| No per-user budgets | One user can exhaust provider quota |
| No persistent session across restarts | Re-add providers after each restart |

## Multi-User Server (not planned)

| Limitation | Impact |
|---|---|
| No tenant isolation | Cross-user data leakage possible |
| No role-based access control | All actions available to all users |
| No usage metering or billing | Cannot track per-user costs |
