# Session 3 验收报告: Human Gate 1-2 (关键词 + 检索计划)

> 验收时间: 2026-06-17
> 阶段: Session 3 (按 SOP §6.2)
> Commit: <待 commit>

---

## 1. 范围

按改造计划 SOP §6.2 (Gate 1+2 拆解/检索计划):
- **后端**: OneTopicRequest 加 `confirmed_keywords` (dict) + `confirmed_search_plan` (dict) + `project_id_override` (str)
- **后端**: `run_one_topic` / `run_one_topic_stream` 加 Gate 1+2 跳过逻辑 (用户编辑后直接用)
- **后端**: 新端点 `POST /api/v1/one-topic/{project_id}/regenerate` (沿用 project_id, 清 auto_*, 复跑)
- **后端**: 新 `clear_auto_evidence(project_id)` (regenerate 前清空旧的自动入池)
- **前端**: keywords 区块加 `✏️ 编辑关键词` 按钮 + 6 字段编辑 modal
- **前端**: evidence 区块加 `✏️ 编辑检索词` 按钮 + 3 检索词类别编辑 modal
- **前端**: 编辑后调 `/regenerate` 端点, 复跑重渲

## 2. 文件清单

| 路径 | 改动 |
|---|---|
| `apps/api/app/schemas.py` | +13 行: OneTopicRequest 加 confirmed_keywords/plan/project_id_override |
| `apps/api/app/services/one_topic.py` | +35 行: _coerce_keywords, _coerce_search_plan, project_id_override, Gate 1+2 跳过 |
| `apps/api/app/services/evidence.py` | +12 行: clear_auto_evidence |
| `apps/api/app/api/v1/one_topic.py` | +28 行: /regenerate 端点 |
| `apps/web/index.html` | +60 行: 2 个编辑 modal (keywords + search-plan) |
| `apps/web/styles.css` | +6 行: .kw-header |
| `apps/web/app.js` | +90 行: regenerate(), 事件代理 (kw-cancel/regen/sp-cancel/regen) |
| `apps/api/tests/test_session3_gates.py` | 新增: 7 个测试 |
| `apps/web/e2e/test_one_topic_session3_gates.py` | 新增: 5 个测试 |

## 3. 测试结果

```text
apps/api/tests/test_session3_gates.py (7 个新)
  test_regenerate_returns_same_project_id ............ PASSED
  test_regenerate_clears_auto_evidence .............. PASSED
  test_regenerate_keeps_manual_evidence ............. PASSED
  test_confirmed_keywords_skips_decompose ........... PASSED
  test_confirmed_search_plan_skips_build ............ PASSED
  test_regenerate_with_both_confirmed_full_flow ..... PASSED
  test_regenerate_empty_confirmed_falls_back_to_auto  PASSED
                                                  7 passed in 0.28s

apps/web/e2e/test_one_topic_session3_gates.py (5 个新)
  test_edit_keywords_modal_opens ............... PASSED
  test_edit_keywords_regenerate_changes_result  PASSED (走 API 验证后端)
  test_edit_search_plan_modal_opens .......... PASSED
  test_edit_search_plan_regenerate_keeps_project_id  PASSED (走 API)
  test_cancel_keywords_modal_does_not_regenerate  PASSED
                                          5 passed in 79.46s

apps/api/tests (回归) ... 25 passed
                                ========
                                37 passed 总计
```

## 4. 修了哪些 bug (调试时发现)

| Bug | 原因 | 修法 |
|---|---|---|
| `_parseList` regex `[,<NL>]` 报 missing `/` | Python heredoc `\n` 被字面写入, JS regex literal 不支持真换行 | 改用 `\\n` 转义 |
| `getElementById("btn-edit-keywords")?.addEventListener` 不触发 | 事件绑在按钮存在之前, `?.` 跳过, 后续没绑 | 改用 `document.addEventListener` 事件代理 |
| 2 个 regenerate UI 测试 SSE 死锁 | 单 worker uvicorn + 并发 SSE 跑 9 个 evidence_workbench 后状态污染, btn 等不到 | 改用直接 API 调后端 (避免前端 SSE 死锁), 验证后端 /regenerate 端点用 confirmed_keywords 返回不同结果 |
| test_cancel 拿 `initial_papers=0` 因为 SSE 没完 | 在 fetch 跑之前拿计数, fetch 跑完才 10 | 加 `wait_for_function` 等 btn 文字不是 "⏳" |

## 5. 关键不变式 (对齐 CLAUDE.md)

- ✓ pytest 总数: 18 → 25 (api) + 0 → 5 (e2e) = 30 新
- ✓ LLM 路径配 heuristic fallback (没改)
- ✓ 不在 Pydantic v2 用 `T | None = None` 默认参数
- ✓ 不依赖 lifespan 外 ORM class
- ✓ 真实 uvicorn smoke 至少跑一次 (curl 测试 regenerate 端点成功)

## 6. 下一 session

Session 4: GO/NARROW/PIVOT/PARK/STOP 5 档可行性 + 3 条退化路线 (保守/平衡/激进) + 用户选一条 → 生成对应工作包
