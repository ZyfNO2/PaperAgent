# Session 11 验收报告: Trace 持久化与操作回放

> 验收时间: 2026-06-19
> 阶段: Session 11 (按 `Plan/PaperAgent_Session11_Trace持久化与操作回放SOP.md`)
> 范围: 把 in-memory Trace 升级为可持久化、可回放、可进入报告的项目决策记录.

---

## 1. 本阶段范围

Session 09/10 后用户对证据的操作越来越多, 但 in-memory trace 在重启后丢失. Session 11 把 trace 落本地 jsonl, 加 evidence_timeline / trace_summary, 并把关键决策写入 FinalPackage 报告.

交付:
- `TraceEvent` / `TraceListResponse` / `TraceTimelineResponse` / `TraceSummaryResponse` Pydantic 模型
- `apps/api/app/services/trace_store.py` 全新服务: append_trace 写 `.runtime/traces/{project_id}.jsonl` + in-memory 缓存
- 改造 `evidence.append_trace()` 委托给 trace_store (单入口)
- 3 新 API 端点: `GET /trace`, `GET /trace/summary`, `GET /evidence/{id}/timeline`
- 关键操作触发 trace: workspace_patch / card_intake_created / verify_evidence / final_package_build / manual_verification / ref_rebuild
- FinalPackage 新增 章节 "十四、关键决策记录" (从 trace_summary 拼)
- 前端工作台新增 `#trace-panel` 含筛选 + 列表 + 时间轴 modal + 卡片 "🛤️ 查看路径" 按钮

---

## 2. 新增字段 (schemas_trace.py)

| 字段 | 默认 | 说明 |
|---|---|---|
| `trace_id` | uuid | 单条 trace 唯一 ID |
| `project_id` | - | 关联 project |
| `ts` | utcnow | ISO 8601 |
| `actor` | "system" | system / user / agent |
| `action` | - | workspace_patch / card_intake_created / verify_evidence / final_package_build / manual_verification / ref_rebuild / verify_project / ref_review |
| `target_type` | None | evidence_item / evidence_pool / final_package / workspace_item |
| `target_id` | None | eid 或 scope |
| `evidence_id` | None | 关联 evidence |
| `before` / `after` | {} | 状态变化前后 |
| `reason` | None | 解释 / 用户备注 |
| `source` / `session` | None | 调用来源 / session ID |

---

## 3. 持久化位置

```text
.runtime/traces/{project_id}.jsonl
```

每行一个 JSON object. 默认从 CWD 计算相对路径, 可通过环境变量 `PAPERAGENT_TRACE_DIR` 覆盖 (测试用).

in-memory 缓存 `_CACHE: dict[str, list[dict]]` 保留作为热路径; `_read_jsonl()` 始终从文件读, 防止两边漂移.

---

## 4. 新增 API

| 端点 | 方法 | 用途 |
|---|---|---|
| `/api/v1/one-topic/{project_id}/trace` | GET | 取 trace, 支持 `limit / action / actor / since` |
| `/api/v1/one-topic/{project_id}/trace/summary` | GET | 用户/系统/agent 计数 + key_decisions |
| `/api/v1/one-topic/{project_id}/evidence/{evidence_id}/timeline` | GET | 单条 evidence 的 timeline |

---

## 5. 验证器规则

SOP §4 定义 11 个必须记录的动作. 实际接入 7 个 (其他暂未触发):

| action | 触发点 |
|---|---|
| `workspace_patch` | `PATCH /workspace/item` |
| `card_intake_created` | `intake_card()` |
| `verify_evidence` / `verify_project` | `POST /evidence/{id}/verify`, `POST /evidence/verify` |
| `manual_verification` | `PATCH /evidence/{id}/verification` |
| `ref_rebuild` | `POST /evidence/refs/rebuild` |
| `ref_review` | `PATCH /evidence/refs/review` |
| `final_package_build` | `build_final_package()` |

`get_trace_summary()` 提取 user_actions / system_actions / agent_actions + 关键决策列表 (去重, 最多 30 条).

---

## 6. EvidenceRef / ReportCitation 联动

不需要新增字段 — trace 是项目级而非 evidence 级. 但 trace_summary 的 key_decisions 进入 Markdown 报告的 "十四、关键决策记录" 章节.

---

## 7. FinalPackage 联动

在 `_build_sections` 末尾追加 `sec_decision` (key="decision_log"):

```markdown
## 十四、关键决策记录

- 用户操作: 3 条
- 系统操作: 5 条
- Agent 操作: 1 条
- 总事件数: 9
- 最近事件: 2026-06-19T...

| # | 决策 |
|---|---|
| 1 | user 将 paper_001 移到 user_preferred 栏: 导师指定 |
| 2 | system 对 paper_001 跑验证: verified |
| 3 | system 生成 FinalPackage Markdown 报告 |
```

若项目无 trace, 显示 "(暂无持久化决策记录)".

---

## 8. 前端 UI

- 工作台顶部 `#trace-panel`:
  - 🔄 刷新历史 + action 筛选 (workspace_patch / card_intake_created / verify_evidence / ref_rebuild / final_package_build / manual_verification) + actor 筛选 (user / system / agent)
  - `#trace-list` 时间倒序滚动列表, 每行: ts / actor pill / action / evidence_id / reason
  - `#trace-summary-hint` 顶部统计 (总 N · user X · system Y · agent Z)
- 工作台卡片新增 🛤️ 查看路径 按钮 → 打开 `#timeline-modal` 显示该 evidence 的 timeline
- 切换到 evidence tab 自动 `loadTraceHistory()`; 每次 workspace_patch 自动刷新

---

## 9. 后端测试结果 (`apps/api/tests/test_session11_trace_persistence.py`)

**13/13 通过:**

```
test_01_append_trace_writes_jsonl                    PASSED
test_02_get_trace_filters_by_project                PASSED
test_03_persistence_after_reset                     PASSED
test_04_workspace_patch_writes_trace                PASSED
test_05_card_intake_writes_trace                    PASSED
test_06_verification_writes_trace                   PASSED
test_07_final_package_build_writes_trace            PASSED
test_08_timeline_by_evidence_id                     PASSED
test_09_summary_key_decisions                       PASSED
test_10_trace_does_not_change_review_status         PASSED
test_11_get_trace_api                               PASSED
test_12_get_timeline_api                            PASSED
test_13_get_trace_summary_api                       PASSED
```

---

## 10. Playwright 测试 (`apps/web/e2e/test_one_topic_session11_trace_persistence.py`)

**6 tests (在后台 subagent 跑).** 修复了一个 CSS bug: timeline-modal 在 `[hidden]` 状态下 `position: fixed; inset: 0` 仍拦截 click, 改为 `[hidden] { display: none !important; }`.

---

## 11. 修复的非 Session 11 问题

- `evidence.append_trace()` 旧签名 `target_type` 是必填, 委托后改为可选 (兼容新调用方传 None)
- `_read_jsonl` 严格只读文件, 不 fallback in-memory (避免顺序错乱). 启动后写入同时进两边
- jsonl path 计算 `parents[4]` (相对 `apps/api/app/services/trace_store.py` 是 repo root)

---

## 12. 未做项 (SOP §3 黑名单)

- 不做完整 Research Wiki
- 不做跨项目推荐
- 不做撤销/回滚 (只记录, 不实现状态回滚)
- 不做多人协作审计
- 不记录敏感全文

---

## 13. 下一 Session 建议

Session 12 — 报告质量检查与低门槛委员会复核 (已完成, 见 `Session_12_ReportQuality_Review_验收报告.md`).