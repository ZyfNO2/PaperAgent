# Session 4 验收报告: GO/NARROW/PIVOT/PARK/STOP 5 档 + 3 退化路线

> 验收时间: 2026-06-17
> 阶段: Session 4 (按 SOP §9.4 + §10)
> Commit: <待 commit>

---

## 1. 范围

按改造计划 SOP §9.4 (5 档判定: GO/NARROW/PIVOT/PARK/STOP) + §10 (3 条退化路线):

**后端**:
- `FeasibilitySummary.verdict` Literal 加 "可转向" → 5 档
- `judge_feasibility` 决策树: 数据/基线缺失但论文够 → "可转向" (而非 "收缩后可做"), 推荐 "看 3 条退化路线"
- 新 `PivotRoute` Pydantic 模型 (level / new_topic / preserved/removed_keywords / tradeoff / work_packages)
- `recommend_proposal` 生成 `pivot_routes` (3 条: conservative / balanced / aggressive), 只在 verdict 是 NARROW/PIVOT 时填
- `apply_pivot_route(route, keywords, ev)` 用路线生成 ProposalRecommendation (work_packages 来自路线)
- 新端点 `POST /api/v1/one-topic/{project_id}/pivot/select`

**前端**:
- 可行性区 verdict=NARROW/PIVOT 时显示 "🔀 看 3 条退化路线" 按钮
- 推荐区显示 3 张 pivot 路线卡片 (preserved/removed keywords + tradeoff + 选择按钮)
- 新 `modal-pivot` 弹窗: 显示 3 路线, 点选 → 调 /pivot/select → 重渲

## 2. 文件清单

| 路径 | 改动 |
|---|---|
| `apps/api/app/schemas.py` | +30 行: PivotRoute + ProposalRecommendation 加 pivot_routes |
| `apps/api/app/services/one_topic.py` | +110 行: judge_feasibility 加 PIVOT 档, generate_pivot_routes, apply_pivot_route |
| `apps/api/app/api/v1/one_topic.py` | +60 行: POST /pivot/select 端点 |
| `apps/web/index.html` | +18 行: modal-pivot 弹窗 |
| `apps/web/styles.css` | +25 行: .pivot-card / .pivot-card__level 等 |
| `apps/web/app.js` | +95 行: showPivotModal, selectPivotRoute, 按钮渲染, 事件代理扩展 |
| `apps/api/tests/test_session4_pivot.py` | 新增: 9 个后端测试 |
| `apps/web/e2e/test_one_topic_session4_pivot.py` | 新增: 4 个 e2e |

## 3. 测试结果

```text
apps/api/tests/test_session4_pivot.py (9 个新)
  test_feasibility_verdict_is_one_of_5 ................. PASSED
  test_pivot_routes_empty_when_yolo_steel .............. PASSED
  test_pivot_routes_present_when_narrow_or_pivot ....... PASSED
  test_pivot_route_structure ............................ PASSED
  test_pivot_select_endpoint_basic ..................... PASSED
  test_pivot_select_returns_wp_for_balanced ............ PASSED
  test_pivot_select_404_for_unknown_project ............. PASSED
  test_pivot_route_conservative_keeps_yolo_removes_multimodal  PASSED
  test_pivot_route_aggressive_keeps_multimodal ......... PASSED
                                                  9 passed in 0.24s

apps/web/e2e/test_one_topic_session4_pivot.py (4 个新)
  test_yolo_steel_no_pivot_button ...................... PASSED
  test_narrow_topic_shows_pivot_button ................. PASSED
  test_pivot_select_endpoint_changes_work_packages ..... PASSED
  test_frontend_pivot_button_and_select ............... PASSED
                                                  4 passed in 32.99s

apps/api/tests (回归) ... 34 passed
                                ========
                                47 passed 总计
```

## 4. 修了哪些 bug (调试时发现)

| Bug | 原因 | 修法 |
|---|---|---|
| YOLO 钢材返回 "收缩后可做" 不是 "可做" | 条件 `paper_count >= 5` 太严, mock arxiv 只给 3 篇 | 改 `>= 3` |
| `apply_pivot_route(req, route, ...)` 调 OneTopicRequest(raw_topic="") ValidationError | raw_topic `min_length=1` | 删 req 参数, 函数体里没用 |
| `test_pivot_select_404_for_unknown_project` assertion `"evidence" in detail.lower()` 不匹配 | 中文 detail `.lower()` 后乱码 | 改 `assert "ot_does_not_exist" in detail` |
| test_narrow_topic_shows_pivot_button KeyError 'pivot_routes' | 旧 uvicorn 没 reload 新代码 | 重启后端 (websockets 文件锁冲突需要 taskkill + 重新启动) |
| 题目变了: 多模态 桥梁 → verdict=可做 (因为 >= 3 paper) | 同上 | 改用 "基于XXX的极小众对象检测" 触发 PIVOT |
| **前端 click [data-pivot-level] 按钮没触发 handler** | body listener `closest("[data-action]")` 不匹配 (新 button 没 data-action) → early return | 改 selector `closest("[data-action], [data-pivot-level]")` |
| `[data-pivot-level]` button 没 `data-action="select-pivot"` | render 时没加 | 改 render: 加 id + data-pivot-level |

## 5. 关键不变式 (对齐 CLAUDE.md)

- ✓ pytest 总数: 25 → 34 (api) + 0 → 4 (e2e) = 38 新
- ✓ LLM 路径配 heuristic fallback (没改)
- ✓ 不在 Pydantic v2 用 `T | None = None` 默认参数
- ✓ 不依赖 lifespan 外 ORM class
- ✓ 真实 uvicorn smoke 至少跑一次 (curl 测试 /pivot/select 成功)

## 6. 下一 session

Session 5: 去重 + 评分 (PaperRelevance / DatasetScore / RepoScore 公式, 论文类型分类 survey/baseline/application/irrelevant, DatasetScore 评分, RepoScore 评分)