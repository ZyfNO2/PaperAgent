# Error Handling & Observability（错误处理与可观测性）

> Session 18 整理的统一错误码、健康检查、结构化日志与前端空状态 / 错误提示规范。

---

## 1. 错误码清单（11 个）

| error_code | 场景 | HTTP | next_action |
|---|---|---|---|
| `PROJECT_NOT_FOUND` | project_id 不存在 | 404 | 先跑一次分析 (POST /analyze) 或检查 project_id 是否正确 |
| `EVIDENCE_NOT_FOUND` | evidence_id 不存在 | 404 | 刷新证据列表; 该 evidence 可能已被删除 |
| `RETRIEVAL_SOURCE_FAILED` | 单检索源失败 | 200 / partial | 稍后重试, 或切换 refresh=False 用上次结果 |
| `RETRIEVAL_ALL_FAILED` | 所有检索源失败 | 502 | 检查网络; 可改用手动添加 / 资料卡片化 |
| `VERIFY_FAILED` | URL 验证失败 | 200 / failed | URL 不可访问, 这条证据不会进 supports; 可手动确认后改 status |
| `MATERIAL_TOO_LARGE` | 上传文件超过限制 | 413 | 压缩文件 (上限 20MB) 或拆分后再上传 |
| `MATERIAL_TYPE_UNSUPPORTED` | MIME / 扩展名不支持 | 415 | 确认扩展名与 MIME 在白名单 (PDF / PNG / JPG / WEBP / TXT / MD) |
| `MATERIAL_PARSE_SKIPPED` | PDF 无文本层 / 图片无 OCR | 200 / skipped | PDF 无文本层 / 图片未做 OCR, 请人工确认或换格式 |
| `REPORT_QUALITY_LOW` | 报告质量低 | 200 | 按 revision_checklist 补强后重新生成 |
| `BASELINE_CONTRACT_FAILED` | Demo 基线失败 | test only | 检查 S17 baseline 是否被破坏, 修复代码或更新基线 |
| `INTERNAL_ERROR` | 未预期异常 | 500 | 看后端日志; 若是用户输入导致, 提供更详细复现 |

---

## 2. 错误响应结构

```json
{
  "error_code": "MATERIAL_TOO_LARGE",
  "message": "文件 30MB 超过 20MB",
  "detail": { "size_mb": 30 },
  "next_action": "压缩文件 (上限 20MB) 或拆分后再上传.",
  "request_id": "req_abc123...",
  "project_id": "ot_xxx"
}
```

FastAPI 内置 `HTTPException(detail={...})` 也兼容（detail 若已是 dict 且含 `error_code`，直接转 JSONResponse；否则包成 INTERNAL_ERROR + raw）。

---

## 3. Health 端点

### `GET /health`（基础）

```json
{
  "status": "ok",
  "phase": "one_topic_mvp",
  "session": "18"
}
```

### `GET /api/v1/health`（基础 + 时间戳 + 版本）

```json
{
  "status": "ok",
  "version": "0.1.0-rc1",
  "service": "paperagent-api",
  "time": "2026-06-19T..."
}
```

### `GET /api/v1/health/detailed`（详细诊断）

```json
{
  "status": "ok",
  "version": "0.1.0-rc1",
  "service": "paperagent-api",
  "time": "...",
  "runtime_dirs": {
    "traces":    { "ok": true, "path": "G:\\PaperAgent\\.runtime\\traces" },
    "materials": { "ok": true, "path": "..." },
    "retrieval": { "ok": true, "path": "..." }
  },
  "skills": {
    "enabled": 4,
    "issues": []
  },
  "external_sources": {
    "openalex":         "optional",
    "arxiv":            "optional",
    "github":           "optional",
    "huggingface":      "optional",
    "semantic_scholar": "placeholder",
    "kaggle":           "placeholder"
  }
}
```

**边界**：

- 不做真实网络探测作为默认 health；
- health 因外部网络失败而红 → 外部源状态只标 `configured / optional / placeholder`；
- `runtime_dirs.ok` 通过写探针文件验证可写。

---

## 4. 结构化日志

落地：`.runtime/logs/app.jsonl`（可被 `PAPERAGENT_LOG_DIR` 覆盖）。

字段：

```text
ts, level, request_id, project_id, action,
target_type, target_id, status, duration_ms, message, extra
```

helper：

```python
from app.services.structured_log import info, warn, error, timed

info("material_uploaded", project_id="ot_xxx", action="material_uploaded",
     target_type="material", target_id="mat_abc", duration_ms=42)

with timed("retrieval_run", project_id="ot_xxx"):
    do_retrieval()
```

**边界**：

- 不记录用户上传全文；
- 不记录敏感文件内容；
- 只记录 id / 状态 / 摘要；
- 写盘失败不阻塞业务（吞掉 OSError）。

---

## 5. 前端空状态

统一 `emptyStateHTML({icon, title, hint, nextAction?, kind?})`，覆盖 6 类场景：

| 场景 | icon | next_action |
|---|---|---|
| Trace 无事件 | 🛰️ | 跑一次分析 / 移动证据 |
| Materials 无草稿 | 📎 | 切换上方 3 个 tab (上传 / 文字 / 备注) |
| 检索 0 候选 | 🔍 / ⚠️ | 换关键词 / 手动添加链接 |
| 检索部分失败 | ⚠️ | 刷新一次 / refresh=False 复用上次结果 |
| 暂无论文 / 数据集 / baseline | 📑 / 📦 / 🛠️ | 跑对应 scope 或手动加链接 |
| 无证据引用 | 🔗 | 移到 accepted / core 再回此处 |

`kind`: `info`（默认）/ `warn`（黄色边框）/ `error`（红色边框）。

---

## 6. 前端错误提示

`explain*()` helper 家族：

| helper | 输入 | 输出 |
|---|---|---|
| `explainUploadFailure(status, body)` | HTTP code | `{message, next_action}` |
| `explainReportQuality(verdict, score)` | PASS/WARN/FAIL/需修改/不建议 | `{message, next_action}` |
| `explainRetrievalFailure({failed_sources, status})` | 检索 partialFailure | 中文短句 + 下一步 |
| `explainVerifyFailure(item)` | evidence dict | 状态解释 + 是否进 supports |
| `explainVerificationFailure(result)` | 验证结果对象 | 中文短句 |

调用示例：

```js
const u = explainUploadFailure(r.status, t);
showError(`上传失败: ${u.message} — ${u.next_action}`);
```

**要求**：

- 错误提示必须给下一步，不只显示 status code；
- 用户可降级处理时必须给入口；
- 开发态细节可折叠显示，不默认暴露长 traceback。

---

## 7. 关键安全 / 行为约束

- 不记录用户上传全文到 `.runtime/logs/`；
- 不把任何凭据写日志（即使 `.env` 已被加载）；
- health 端点不触发真实外部 HTTP 请求；
- AppError 通过 `error_code` 自动匹配 next_action；
- 错误结构含 `request_id` 方便关联日志；
- 不破坏 evidence / verification / trace / supports 核心规则。

---

## 8. 相关文件

- 后端错误：[apps/api/app/errors.py](../apps/api/app/errors.py)
- Health：[apps/api/app/services/health.py](../apps/api/app/services/health.py) + [apps/api/app/api/v1/health.py](../apps/api/app/api/v1/health.py)
- 结构化日志：[apps/api/app/services/structured_log.py](../apps/api/app/services/structured_log.py)
- 前端 helper：[apps/web/app.js](../apps/web/app.js)（顶部）
- 样式：[apps/web/styles.css](../apps/web/styles.css)（`.empty-state--warn/error`）
- 测试：[apps/api/tests/test_session18_error_observability.py](../apps/api/tests/test_session18_error_observability.py) + [apps/web/e2e/test_one_topic_session18_error_states.py](../apps/web/e2e/test_one_topic_session18_error_states.py)
- 验收报告：[Plan/reports/Session_18_Error_Observability_验收报告.md](../../Plan/reports/Session_18_Error_Observability_验收报告.md)