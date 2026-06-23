# PaperAgent Session 18 SOP：错误处理、空状态与可观测性整理

> 日期：2026-06-19  
> 阶段定位：Session 17 已固化 Demo 回归基线，本轮在不扩展业务能力的前提下，统一错误处理、空状态提示和本地可观测性。  
> 本轮目标：让系统在外部 API 失败、无候选、上传失败、验证失败、报告质量低分等场景下给出明确原因和下一步，同时提供最小 health / diagnostic 能力。

---

## 1. Session 17 验收判断

已审阅：

```text
Plan/reports/Session_17_Demo_Baseline_验收报告.md
docs/demo/baselines/README.md
```

判断：

```text
Session 17 可过验收；
可以进入 Session 18；
若不做中间审查，低风险链路可继续到 Session 20。
```

依据：

```text
1. Demo baseline 已固化；
2. 后端 S17 15 passed，全量后端 207 passed, 1 skipped；
3. Playwright S17 10 passed；
4. S17 未改 evidence / verification / trace 核心规则；
5. baseline 已覆盖 rejected / pending / failed 不进 supports。
```

Session 18 可以依赖 S17 baseline 判断是否破坏主流程。

---

## 2. 本阶段不做什么

| 不做 | 原因 |
|---|---|
| 不新增核心业务能力 | 当前目标是可诊断性 |
| 不改 EvidenceRef / Verification supports 规则 | 防止破坏证据合同 |
| 不引入复杂监控平台 | 本地 MVP 不需要 |
| 不做生产级日志采集 | 先做结构化本地诊断 |
| 不新增外部依赖服务 | 避免部署复杂化 |
| 不重构前端整体布局 | 只整理错误、空状态和提示 |

---

## 3. 核心交付

建议新增 / 修改：

```text
apps/api/app/errors.py
apps/api/app/services/health.py
apps/api/app/api/v1/health.py
apps/web/app.js
apps/web/styles.css
docs/project/Error_Handling_And_Observability.md
apps/api/tests/test_session18_error_observability.py
apps/web/e2e/test_one_topic_session18_error_states.py
Plan/reports/Session_18_Error_Observability_验收报告.md
```

如果不想新增 router，也可把 health 暂挂在现有 API 下：

```text
GET /api/v1/health
GET /api/v1/health/detailed
```

---

## 4. 错误码规范

新增统一错误结构：

```json
{
  "error_code": "RETRIEVAL_SOURCE_FAILED",
  "message": "OpenAlex 暂时不可用，已保留其他来源结果。",
  "detail": {},
  "next_action": "稍后重试，或使用手动导入 / 资料卡片化。",
  "request_id": "req_...",
  "project_id": "ot_..."
}
```

建议错误码：

| error_code | 场景 | HTTP |
|---|---|---|
| `PROJECT_NOT_FOUND` | project_id 不存在 | 404 |
| `EVIDENCE_NOT_FOUND` | evidence_id 不存在 | 404 |
| `RETRIEVAL_SOURCE_FAILED` | 单检索源失败 | 200 / partial |
| `RETRIEVAL_ALL_FAILED` | 所有检索源失败 | 502 |
| `VERIFY_FAILED` | URL 验证失败 | 200 / failed |
| `MATERIAL_TOO_LARGE` | 上传文件超过限制 | 413 |
| `MATERIAL_TYPE_UNSUPPORTED` | MIME / 扩展名不支持 | 415 |
| `MATERIAL_PARSE_SKIPPED` | PDF 无文本层 / 图片无 OCR | 200 / skipped |
| `REPORT_QUALITY_LOW` | 报告质量低 | 200 |
| `BASELINE_CONTRACT_FAILED` | Demo 基线失败 | test only |

注意：

```text
业务可降级场景不要全部变成 500；
能 partial 的地方就返回 partial + warning；
真实 500 只保留给未预期异常。
```

---

## 5. Health / Diagnostic

新增：

```text
GET /api/v1/health
GET /api/v1/health/detailed
```

`/health` 返回：

```json
{
  "status": "ok",
  "version": "dev",
  "time": "2026-06-19T..."
}
```

`/health/detailed` 返回：

```json
{
  "status": "ok",
  "runtime_dirs": {
    "traces": true,
    "materials": true,
    "retrieval": true
  },
  "skills": {
    "enabled": 4,
    "issues": []
  },
  "external_sources": {
    "openalex": "optional",
    "github": "optional",
    "huggingface": "optional",
    "semantic_scholar": "placeholder",
    "kaggle": "placeholder"
  }
}
```

边界：

```text
不做真实网络探测作为默认 health；
避免 health 因外部网络失败而红；
外部源状态只说明 configured / optional / placeholder。
```

---

## 6. 前端空状态整理

统一空状态：

```text
没有检索候选；
没有证据；
没有 Trace；
没有 ReportQuality 结果；
没有 Skill；
没有 Material 草稿；
没有 FinalPackage；
```

每个空状态必须包含：

```text
标题；
原因；
下一步操作；
相关按钮或入口；
```

示例：

```text
暂无可用数据集证据
可能原因：当前检索结果未发现公开数据集，或候选仍未审核。
下一步：运行多源检索中的 dataset scope，或手动添加 HuggingFace / Kaggle / 论文项目页链接。
```

---

## 7. 前端错误提示整理

重点场景：

```text
1. OpenAlex / GitHub / HF 检索失败；
2. URLVerified failed；
3. PDF 上传超过 20MB；
4. PDF 无文本层；
5. 图片无 OCR；
6. 重复导入候选；
7. ReportQuality verdict=需修改 / 不建议；
8. Demo baseline 失败（仅开发态说明）。
```

要求：

```text
错误提示必须给下一步，不只显示 status code；
用户可降级处理时必须给入口；
开发态细节可折叠显示，不默认暴露长 traceback。
```

---

## 8. 结构化日志

MVP 只做本地结构化日志 helper，不引入日志平台。

建议字段：

```text
ts；
level；
request_id；
project_id；
action；
target_type；
target_id；
status；
duration_ms；
message；
```

可选落地：

```text
.runtime/logs/app.jsonl
```

边界：

```text
不记录用户上传全文；
不记录敏感文件内容；
只记录 id / 状态 / 摘要。
```

---

## 9. 测试要求

新增：

```text
apps/api/tests/test_session18_error_observability.py
apps/web/e2e/test_one_topic_session18_error_states.py
```

后端至少覆盖：

```text
1. /health 返回 ok；
2. /health/detailed 返回 runtime_dirs / skills / external_sources；
3. unsupported material type 返回规范错误；
4. material too large 返回规范错误；
5. retrieval 单 source failed 仍 partial；
6. project_not_found 返回规范错误；
7. health 不依赖真实外部 API；
8. structured log 不记录正文内容；
9. S17 baseline 仍通过。
```

Playwright 至少覆盖：

```text
1. Trace 空状态友好；
2. Materials 空状态友好；
3. 检索失败提示有 next action；
4. 上传失败提示可读；
5. ReportQuality 低分显示下一步；
6. health/detailed 可在开发态访问或被文档说明。
```

---

## 10. 回归要求

必须跑：

```text
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session17_demo_baseline.py apps/api/tests/test_session18_error_observability.py -v
.venv/Scripts/python.exe -m pytest apps/web/e2e/test_one_topic_session17_demo_baseline.py apps/web/e2e/test_one_topic_session18_error_states.py -v
```

建议跑：

```text
.venv/Scripts/python.exe -m pytest apps/api/tests -q
```

验收报告必须说明是否跑了全量。

---

## 11. 验收标准

通过条件：

```text
1. 统一错误结构可用；
2. /health 与 /health/detailed 可用；
3. 关键空状态有原因和下一步；
4. 关键错误提示不再只是 status code；
5. 外部源失败不导致整条流程无解释崩溃；
6. 结构化日志不记录敏感正文；
7. S17 baseline 继续通过；
8. 后端新增测试通过；
9. Playwright 新增测试通过；
10. 新增 Session18 验收报告。
```

---

## 12. 完工报告要求

完成后新增：

```text
Plan/reports/Session_18_Error_Observability_验收报告.md
```

报告必须写：

```text
错误码清单；
health 输出；
空状态覆盖；
错误提示覆盖；
结构化日志策略；
测试结果；
是否改动证据规则；
是否影响 S17 baseline。
```

---

## 13. 下一 Session

Session 19：

```text
轻量学校模板与开题报告 Markdown 适配
```

进入条件：

```text
S18 不破坏 S17 baseline；
错误提示和 health 可支撑模板适配阶段的问题定位。
```

