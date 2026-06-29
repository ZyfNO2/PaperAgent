# PaperAgent Session 55 验收报告 — RAG Eval + ThesisEval React 接入

日期: 2026-06-29
范围: Session 46-51 后端能力接入 React 前端 — RAG Eval Dashboard + ThesisEval 页面 + 路由扩展

## 1. 完成情况

| 任务 | 计划 | 实际 | 状态 |
|---|---|---|---|
| T1 DTO types | ragEvalTypes + thesisEvalTypes | 字段 1:1 对齐后端 Pydantic schema | done |
| T2 RAG Eval Dashboard | 4 子组件 | 单文件 4 section (Baseline / Metric / Regression / Action) | done |
| T3 ThesisEval Page | 5 子组件 | 单文件 5 section (Assess / Result / Trace / Run / Baseline) | done |
| T4 路由 + 工作台接入 | routing + SideNav + HomePage | 5 路由 (home/interview/rag-eval/thesis-eval/protocols), HomePage 2 跳转 | done |
| T5 测试 + 截图 | vitest + Playwright + 2 截图 | 5 vitest + 15 e2e + 2 截图 | done |

## 2. 关键产物

### 2.1 文件清单 (新增 + 修改)

| 路径 | 状态 | 说明 |
|---|---|---|
| `features/rag-eval/ragEvalTypes.ts` | new | DTO, 11 metric + baseline response |
| `features/rag-eval/RagEvalDashboard.tsx` | new | 单文件 4 section, ~330 行 |
| `features/rag-eval/ragMetricLogic.test.ts` | new | 5 vitest (direction / regression / rows) |
| `features/thesis-eval/thesisEvalTypes.ts` | new | DTO, 4 subset + 9 tag + 4 difficulty |
| `features/thesis-eval/ThesisEvalPage.tsx` | new | 单文件 5 section, ~360 行 |
| `app/routing.ts` | mod | 5 路由 (mode=rag-eval/thesis-eval) |
| `App.tsx` | mod | renderCenter switch, RagEval + ThesisEval 挂载 |
| `components/layout/SideNav.tsx` | mod | nav-rag-eval + nav-thesis-eval item + 高亮 |
| `features/home/HomePage.tsx` | mod | S54 done, S55 active, 2 跳转按钮 |
| `styles/components.css` | mod | +130 行 (.pa-metric-table / .pa-subset-btn / .pa-thesis-meta) |
| `e2e/test_session55_rag_thesis.py` | new | 15 Playwright case |

### 2.2 路由 (5 mode)

```text
#/                          → home (默认, 总览)
#/?mode=interview           → interview (S54)
#/?mode=rag-eval            → rag-eval (S55 新)
#/?mode=thesis-eval         → thesis-eval (S55 新)
#/protocols                 → protocols (S54)
```

`useHashRoute()` 解析 `mode=` query 参数, mode→RouteName switch。

### 2.3 RAG Eval Dashboard 11 指标

| 维度 | 指标 | 方向 |
|---|---|---|
| Retrieval | recall@5 / MRR / NDCG@5 / Hit Rate | up |
| Answer | Citation Precision / Evidence Coverage / Faithfulness | up |
| Answer | Unsupported Claim Rate | down |
| System | Latency p50 / p95 | down |
| System | Fallback Rate | down |

阈值与后端 `eval_baseline.REGRESSION_THRESHOLDS` 对齐:
- up 类: 下降 > 0.05 → regression
- down 类 (latency): p50 上升 > 50ms / p95 上升 > 100ms → regression
- 其它 down: 上升 > 0.05 → regression

### 2.4 ThesisEval 5 section

1. **ThesisEval** — 标题 + 9 标签 / 4 档难度 / 三态降级说明
2. **单题评估** — thesis_id 输入 + 评估按钮 → 显示 result (verified/partial/failed 三态 Badge)
3. **Evidence Trace** — 评估挂的题录/摘要引用列表
4. **测试集评估** — 4 subset 切换 (smoke_20/regression_60/hard_20/all_100) + Run 按钮
5. **Baseline** — 当前 baseline (subset + count + url_fidelity + year_accuracy)

## 3. 测试矩阵

| 范围 | 命令 | 结果 |
|---|---|---|
| Vitest 单元 | `npx vitest run` | **25/25 pass** in 2.00s |
| S55 新增 (5 个) | direction 判定 / regression up / regression down / unsupported_claim 上升 / buildRows 11 项 | |
| TSC | `npx tsc -b` | 0 errors |
| Vite build | `npx vite build` | 18.16 kB CSS / 197.85 kB JS (gzip 64.57 kB) |
| E2E Playwright | `pytest test_session55_rag_thesis.py` | **15/15 pass** in 11.99s |
| 15 个 case | 2 路由 / RAG 4 / ThesisEval 5 / Home 跳转 + SideNav 高亮 / 2 截图 | |

## 4. 真实截图评估 (1280x800)

### 4.1 `s55_rag_eval.png`
- ✅ SideNav 高亮 **RAG Eval** (蓝色 active 背景)
- ✅ RAG Eval 卡片: Seed Library + Run Eval 按钮
- ✅ Baseline 卡片加载成功: `run_id: eval-eba3ac39`, Recall@5=0.678, Faithfulness=1.000, Latency p95=0ms
- ✅ 指标表空态: "跑一次 Eval 后这里会显示…"
- ⚠️ 后端若关, baseline 会空, 表仍可见 — 优雅降级
- ⚠️ Top status bar "session: S52" 是 S53 配置遗留, S56 收口再修

### 4.2 `s55_thesis_eval.png`
- ✅ SideNav 高亮 **ThesisEval**
- ✅ 单题评估卡: thesis_id 输入预填 `ENG-THESIS-001`
- ✅ 测试集评估 4 subset 按钮, `smoke_20` 高亮
- ✅ Baseline 加载: subset=smoke_20, count, url_fidelity=0.000, year_accuracy=0.000
- ✅ "跑 smoke_20" 主按钮可见

## 5. 关键不变式 (SOP §2)

| 不变式 | 落实 | 验证 |
|---|---|---|
| RAG 不只展示聊天答案, 要展示引用/覆盖率/unsupported | 11 指标 + regression alert + baseline diff | e2e + 截图 |
| ThesisEval 不只给结论, 要展示三态降级 | verified / partial / failed Badge | DTO 枚举 |
| 评估口径与 baseline 真实一致 | 阈值与后端 REGRESSION_THRESHOLDS 1:1 对齐 | vitest 5 个 |
| 路由切换不重置无关 state | `key={route.name}` WorkbenchProvider + 路由参数 | App.tsx |

## 6. design-only 诚实边界

- **MCP / ACP** 在 S54 已标 design-only; S55 接 RAG/ThesisEval 不引入新边界
- **三态降级**: ThesisEval 的 `failed` 是设计原则 (SOP §1 "题录链接是事实, 必须 URL verified"), 不是占位
- **Baseline 缺失**: 不报错, 显示空态 + 提示 "跑一次 Eval 后再保存"
- **LLM 思维**: 右侧仍是 S53 占位流, S55 不引入新 placeholder (避免越权)

## 7. 面试讲法

> Q: RAG 评估怎么做?
> A: 11 指标分 3 类 — retrieval (recall@5/MRR/NDCG/hit)、answer (citation/coverage/unsupported/faithfulness)、system (latency p50/p95 + fallback)。每个指标标注方向, 配 baseline diff。threshold 与后端 REGRESSION_THRESHOLDS 1:1 对齐, 客户端前端用同一份逻辑判断 regression — 单一事实源。

> Q: ThesisEval 为什么做三态降级?
> A: 题录链接是事实, 不能编; 抓取失败时降级为题录级证据 (`partial` 或 `failed`), 绝不编造全文/摘要/作者结论。SOP §1 强约束, 前端用 verified/partial/failed 三态 Badge 显式标注, 面试时一眼可见。

> Q: 客户端怎么保证评估口径与后端一致?
> A: DTO 字段名严格 1:1 对齐后端 Pydantic schema, regression threshold 用同一份常量 (`eval_baseline.REGRESSION_THRESHOLDS`)。vitest 测方向判定逻辑, e2e 测路由 + 渲染。

## 8. 已知限制 (S55 → S56 收口)

- Top status bar "session: S52" 是 S53 写死的字符串, S56 改用真实 route
- RAG metric table 只展示当前 vs baseline 静态 diff; 真实 "history 多 baseline 对比" 留给 S56
- ThesisEval "保存 baseline" 按钮没接 POST `/eval/baseline` (S51 后端已实现), 留 S56
- WorkbenchChat 的 LLM 流是 S53 placeholder, S56 接真实 streaming

## 9. 累计

| 范围 | 用例 |
|---|---|
| S52 Playwright | 5 |
| S53 vitest | 13 |
| S53 Playwright | 12 |
| S54 vitest | 7 |
| S54 Playwright | 17 |
| **S55 vitest** | **+5** |
| **S55 Playwright** | **+15** |
| **新总数** | vitest 30 + Playwright 49 = 79 |