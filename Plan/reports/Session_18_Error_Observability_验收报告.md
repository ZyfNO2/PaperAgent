# Session 18 验收报告：错误处理 / 空状态 / 可观测性

> 完成日期: 2026-06-19  
> 测试: backend 12/12 ✓ Playwright 10/10 ✓  
> 范围: 统一错误码 + health 端点 + 结构化日志 + 前端空状态

---

## 1. 目标达成

| 目标 | 结果 |
|---|---|
| 错误结构统一 (error_code / message / detail / next_action / request_id) | ✅ `apps/api/app/errors.py` 11 个错误码 |
| `/health` + `/api/v1/health` + `/api/v1/health/detailed` | ✅ 3 端点全部 200 |
| 结构化 JSONL 日志 (`.runtime/logs/app.jsonl`) | ✅ `apps/api/app/services/structured_log.py` |
| 前端 `emptyStateHTML({kind, nextAction})` 增强 | ✅ `apps/web/app.js` 顶部 |
| `explainUploadFailure` / `explainReportQuality` 等 helper 升级 | ✅ 返回 `{message, next_action}` |
| 测试覆盖 (backend 12 + e2e 10) | ✅ 全绿 |

---

## 2. 产物清单

### 后端

| 文件 | 类型 | 说明 |
|---|---|---|
| `apps/api/app/errors.py` | 新增 | AppError + 11 个错误码 + handlers |
| `apps/api/app/services/health.py` | 新增 | `build_basic_health()` / `build_detailed_health()` |
| `apps/api/app/api/v1/health.py` | 新增 | `/health` + `/api/v1/health[/detailed]` 路由 |
| `apps/api/app/services/structured_log.py` | 新增 | info/warn/error + `timed()` 上下文 |
| `apps/api/app/main.py` | 修改 | 注册 health router + exception handlers |
| `apps/api/tests/test_session18_error_observability.py` | 新增 | 12 后端测试 |

### 前端

| 文件 | 类型 | 说明 |
|---|---|---|
| `apps/web/app.js` | 修改 | `emptyStateHTML` 增强 + `explain*` 升级 |
| `apps/web/styles.css` | 修改 | `.empty-state--warn/error` + `.empty-state__next` |
| `apps/web/e2e/test_one_topic_session18_error_states.py` | 新增 | 10 e2e 测试 |

### 文档

| 文件 | 类型 |
|---|---|
| `docs/project/Error_Handling_And_Observability.md` | 新增 (SOP §9) |

---

## 3. 错误码清单 (11 个)

| error_code | HTTP | 触发场景 | next_action |
|---|---|---|---|
| `PROJECT_NOT_FOUND` | 404 | project_id 不存在 | 先跑一次 analyze 或检查 ID |
| `EVIDENCE_NOT_FOUND` | 404 | evidence_id 不存在 | 刷新证据列表 |
| `RETRIEVAL_SOURCE_FAILED` | 200/partial | 单检索源失败 | 重试 / refresh=False |
| `RETRIEVAL_ALL_FAILED` | 502 | 所有检索源失败 | 检查网络 / 手动添加 |
| `VERIFY_FAILED` | 200/failed | URL 不可访问 | 改 status 或删 |
| `MATERIAL_TOO_LARGE` | 413 | 文件 > 20MB | 压缩或拆分 |
| `MATERIAL_TYPE_UNSUPPORTED` | 415 | MIME/扩展不在白名单 | 用 PDF/PNG/JPG/TXT/MD |
| `MATERIAL_PARSE_SKIPPED` | 200 | PDF 无文本层 | 人工确认或换格式 |
| `REPORT_QUALITY_LOW` | 200 | 报告质量低 | 按 checklist 补强 |
| `BASELINE_CONTRACT_FAILED` | test | S17 baseline 破坏 | 检查 S17 |
| `INTERNAL_ERROR` | 500 | 未预期异常 | 看后端日志 |

---

## 4. Health 端点

### `/health` (root, liveness)

```json
{"status": "ok", "phase": "one_topic_mvp", "session": "18"}
```

### `/api/v1/health` (basic + 时间戳 + 版本)

```json
{"status": "ok", "version": "0.1.0-rc1", "service": "paperagent-api", "time": "..."}
```

### `/api/v1/health/detailed` (诊断)

包含:
- `runtime_dirs`: traces / materials / retrieval (ok 布尔 + path)
- `skills`: enabled 数 + issues 列表
- `external_sources`: 6 个源 (openalex/arxiv/github/huggingface/semantic_scholar/kaggle)，标 `optional` 或 `placeholder`

**不触发真实外部 HTTP**，避免 health 因网络抖动红。

---

## 5. 结构化日志

落点: `.runtime/logs/app.jsonl` (可被 `PAPERAGENT_LOG_DIR` 覆盖)。

```python
from app.services.structured_log import info, warn, error, timed

info("material_uploaded", project_id="ot_xxx", action="material_uploaded",
     target_type="material", target_id="mat_abc", duration_ms=42)

with timed("retrieval_run", project_id="ot_xxx"):
    do_retrieval()
```

字段: `ts, level, request_id, project_id, action, target_type, target_id, status, duration_ms, message, extra`

**约束**:
- 不记录用户上传全文；
- 不记录凭据；
- 写盘失败不阻塞业务 (吞 OSError)。

---

## 6. 前端空状态统一

`emptyStateHTML({icon, title, hint, nextAction?, actionHtml?, kind?})`:

| kind | 边框色 |
|---|---|
| `info` (默认) | 默认 |
| `warn` | 黄色 |
| `error` | 红色 |

覆盖 6 类场景 (trace / materials / retrieval / papers / datasets / baselines)：
- Trace 无事件 → "跑一次分析或移动证据"
- Materials 无草稿 → "切换上方 3 个 tab (上传 / 文字 / 备注)"
- 检索 0 候选 → "换关键词 / 手动添加链接"
- 检索部分失败 → "刷新 / refresh=False 复用上次结果"

---

## 7. 错误提示 explain 系列

```js
const u = explainUploadFailure(r.status, body);
showError(`上传失败: ${u.message} — ${u.next_action}`);
```

| helper | 输入 | 输出 |
|---|---|---|
| `explainUploadFailure` | HTTP code | `{message, next_action}` |
| `explainReportQuality` | verdict + score | `{message, next_action}` |
| `explainRetrievalFailure` | partialFailure | 同上 |
| `explainVerifyFailure` | evidence | 同上 |
| `explainVerificationFailure` | verify result | 同上 |

**要求**: 错误必须给下一步，不只显示 status code。

---

## 8. 测试覆盖

### Backend (`test_session18_error_observability.py`)

| # | 测试 | 结果 |
|---|---|---|
| 1 | `/health` 返回 ok | ✅ |
| 2 | `/api/v1/health` 返回 time + version | ✅ |
| 3 | `/api/v1/health/detailed` 含 runtime_dirs/skills/external_sources | ✅ |
| 4 | `make_error` shape + status_for 映射 | ✅ |
| 5 | AppError 序列化含 request_id | ✅ |
| 6 | project 不存在 (不强制 404) | ✅ |
| 7 | health 不调用 urlopen | ✅ |
| 8 | structured log 不记正文 | ✅ |
| 9 | `timed()` context manager | ✅ |
| 10 | log 写盘失败不抛 | ✅ |
| 11 | health.detailed 字段完整 | ✅ |
| 12 | 错误码 6+ | ✅ |

### Playwright (`test_one_topic_session18_error_states.py`)

| # | 测试 | 结果 |
|---|---|---|
| 1 | `/health` + `/api/v1/health/detailed` | ✅ |
| 2 | 不存在 project 不挂 | ✅ |
| 3 | 上传 .exe 不挂 | ✅ |
| 4 | `/evidence` 结构稳定 | ✅ |
| 5 | `/trace` 结构稳定 | ✅ |
| 6 | `/evidence/verify` 返回 verified/partial/failed/skipped | ✅ |
| 7 | UI trace empty state | ✅ |
| 8 | UI quality panel | ✅ |
| 9 | UI materials 3 tab | ✅ |
| 10 | UI materials empty state 含 next_action | ✅ |

---

## 9. 与基线一致性

- S17 baseline 套件未触动 (`apps/api/tests/test_session17_*` 全绿)。
- 支持规则未变: rejected / pending+unverified / failed 不进 supports。
- Report Quality 8 维度检查未变。
- Skill Registry 4 个内部 skill 未变。

---

## 10. 数据流

```
客户端错误
   ↓
HTTP / JSONResponse
   ↓
[AppError handler | HTTPException handler]
   ↓
{error_code, message, detail, next_action, request_id, project_id?}
   ↓
[前端 fetch 解析]
   ↓
[explain*() 把 error_code 翻译成中文 + 建议]
   ↓
[emptyStateHTML({kind, nextAction}) 渲染]

后端日志
   ↓
[slog.info/warn/error/timed]
   ↓
.runtime/logs/app.jsonl
```

---

## 11. 已知缺口 / 后续

1. **ProjectIntake / TopicSpec / SearchQueryPlan / EvidenceLedger 等 4 个前阶段端点尚未全部走 AppError 包装** — 已注册 handler，但实际抛 HTTPException 的地方优先走 handler；下一次大改时统一。
2. **structured_log 当前未注入 request_id 中间件** — 待加一个 FastAPI middleware 让 `request_id` 自动贯通；现在靠业务显式传。
3. **health.detailed 的 `external_sources` 是静态声明** — 接真实配置 (`ExternalSourceConfig`) 时再细化。

---

## 12. 验收签字

- 测试: backend **12/12** ✓ | Playwright **10/10** ✓
- commit: 见 `git log -1 --format=%s`
- 范围: 错误结构 + 可观测性 + 空状态 (S18 SOP §4-§9)
- 下一站: Session 19 报告模板适配