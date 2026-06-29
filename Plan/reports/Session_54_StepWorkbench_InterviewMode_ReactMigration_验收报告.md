# PaperAgent Session 54 验收报告 — StepWorkbench + Interview Mode React 迁移

日期: 2026-06-29
范围: 旧前端 step_workbench.js / app.js 核心工作流迁移到 React, 第一条业务主线

## 1. 完成情况

| 任务 | 计划 | 实际 | 状态 |
|---|---|---|---|
| T1 数据 + reducer | stepTypes + STEPS + reducer | 6 文件 (stepTypes/reducer/Provider/6 组件) | done |
| T2 StepWorkbench 主壳 | 6 组件 (Nav/Card/Gate/Trace/Thought/Chat) | 全实现, 中栏切换不重置左右 | done |
| T3 Interview Mode | DemoCaseLoader + DeepDiveDrawer + TechSwitchPanel | 8 tech switches + 9 interview modules | done |
| T4 Protocol Map | MCP/A2A/ACP + ACP design-only | ProtocolMapPanel + 诚实边界声明 | done |
| T5 路由 | hash 路由 (3 mode: home/interview/protocols) | 手写 60 行, 不引 react-router (省 50kB) | done |
| T6 测试 + 截图 | vitest + Playwright + 2 截图 | 7 vitest + 17 e2e + 3 截图 | done |

## 2. 关键产物

### 2.1 状态机 (ponytail: 拒绝过度设计)

`WorkbenchState` 12 字段:

```text
activeStepIndex  steps[]  trace[]  llm[]  tools[]  chat[]
streamPhase      commandPreview    demoLoaded    demoTopic    demoDisclaimer    chatDraft    topic
```

8 status 完整: `locked / running / paused_for_review / needs_revision / approved / completed / failed / stale`

切 activeStep **不动** trace/llm/chat 任何一项 — 不可变式。

### 2.2 组件 (12 个)

| 路径 | 用途 |
|---|---|
| `step-workbench/WorkbenchProvider.tsx` | Context 共享 state |
| `step-workbench/StepWorkbenchPage.tsx` | 主壳 |
| `step-workbench/components/StepNavigator.tsx` | 5 步横向切换 (大步骤条 + 子导航) |
| `step-workbench/components/StepCard.tsx` | KV 列表 + 状态色 + 确认/修改按钮 |
| `step-workbench/components/StepGate.tsx` | 暂停确认提示 |
| `step-workbench/components/EvidenceTrace.tsx` | 左侧 Trace 列表, 5 类 kind 区分 |
| `step-workbench/components/ThoughtStream.tsx` | 右侧 LLM 流 |
| `step-workbench/components/WorkbenchChat.tsx` | 对话式编辑 + preview |
| `interview-mode/InterviewShell.tsx` | 包装 + 3min/10min 脚本切换 |
| `interview-mode/DemoCaseLoader.tsx` | 固定 Demo Case (YOLO 钢材缺陷) |
| `interview-mode/TechSwitchPanel.tsx` | 8 tech switches, 3 status |
| `interview-mode/DeepDiveDrawer.tsx` | 9 module 抽屉 + 4 过滤 |
| `protocols/ProtocolMapPanel.tsx` | MCP/A2A/ACP + 诚实边界 |

### 2.3 路由 (手写 hash router)

```text
#/                  → HomePage (默认, 总览)
#/?mode=interview   → InterviewShell (interview mode + 5 步 + tech switches + 协议图)
#/protocols         → InterviewShell (协议图高亮 nav 入口)
```

`useHashRoute()` 监听 `hashchange` + 初始化解析。

## 3. 测试矩阵

| 范围 | 命令 | 结果 |
|---|---|---|
| 组件单元 | `npx vitest run` | **20/20 pass** in 1.85s |
| S54 reducer (7 个) | 5 步初始 / 切 step 不清空 / staleReason / LOAD_DEMO_CASE / ADD_CHAT / SET_STEP_RESULT / STEPS 顺序 | |
| TSC | `npx tsc -b` | 0 errors |
| Vite build | `npx vite build` | 16.01 kB CSS / 184.11 kB JS (gzip 61 kB) |
| E2E Playwright | `pytest test_session54_step_workbench.py` | **17/17 pass** in 9.35s |
| 17 个 case | home / 路由 / 5 步导航 / Demo Case 加载 / 切 step 不重置 / chat preview / accept / 8 tech switch / DeepDive 9 module + 过滤 / Protocol map 3 行 + 诚实边界 / 路由高亮 / 3 截图 | |

## 4. 真实截图评估 (1280x800)

### 4.1 `s54_interview_mode.png` (Interview 模式 + Demo Case 加载)
- ✅ Step Workbench · Demo Case 标题
- ✅ 5 步状态条 (上) + 5 步子导航 (下) — 双层指示清晰
- ✅ Step 1 题目理解 KV 列表 (direction / task_type / possible_object / possible_route / ambiguous_terms)
- ✅ Demo Case 加载后 5 步全部 completed (绿框)
- ✅ Trace / 证据收集: demo_case 事件
- ✅ LLM 思维 / 对话: assistant_reply 流
- ✅ 对话式编辑输入框 + 预览按钮
- ⚠️ 右侧 ThoughtPanel 是 S53 占位流 (S55 接入真实 LLM)

### 4.2 `s54_deep_dive.png` (Deep Dive 抽屉)
- ✅ 右侧 9 个 Module: Workflow / RAG / Evidence / Memory / MCP / Agent / Failure / Tests / Protocols
- ✅ 每个 module 2 个折叠: 常见问题 + 代码/测试/文档/边界
- ✅ 状态色 3 种: 已实现 (绿) / 轻量 (黄) / 架构预留 (蓝)
- ✅ Tech Switches 8 项可见, Paper RAG / Reality Check / Claim Grounding / Track B / ThesisEval / RAG Eval / MCP / ACP

## 5. 关键不变式 (SOP §3)

| 不变式 | 落实 | 验证 |
|---|---|---|
| 中间步骤翻页只改 currentStep | reducer 切 activeStep 不动其他 | test_s54_14 |
| 左侧 Trace 不因翻页清空 | state.trace 独立, 切 step 不重置 | test_s54_14 |
| 右侧 Thought / Chat 不因翻页清空 | state.llm + state.chat 独立 | test_s54_15/16 |
| Step 状态独立保存 | 8 status + staleReason 字段 | reducer test |
| Step 1 折叠入口 | StepNavigator 横向 + StepCard KV | visual |

## 6. design-only 诚实边界 (SOP §3 重要)

ProtocolMapPanel 显式标 `design-only`, 并有 **诚实边界** 区块:

```text
协议对照表仅用于架构讲解, 不接入真实 runtime。
ACP 是设计预留, 不参与当前主链路执行。
```

Tech Switches 8 项的 status 区分:
- **implemented** (已实现): Paper RAG / Reality Check / Claim Grounding / Track B Extractor / RAG Evaluator
- **lightweight** (轻量): ThesisEval (有评估但口径有限)
- **design-only** (架构预留): MCP / ACP Admission Control

## 7. 面试讲法

> Q: 旧前端 step_workbench.js 怎么迁到 React?
> A: 5 步状态机 → `useReducer` + Context; 6 步骤组件 (Navigator/Card/Gate/Trace/Thought/Chat) 各自职责清晰; 不引 react-router, 手写 hash 路由 (省 50kB); 切 activeStep 是 reducer 一次更新, Trace/LLM/Chat 状态独立保留; 7 个 reducer 单元 + 17 个 Playwright 端到端 + 3 真实截图。

> Q: Interview Mode 怎么保证诚实?
> A: 8 Tech Switches 用 3 status (implemented/lightweight/design-only) 显式标注; 9 Deep Dive Module 必带 boundary 字段; ProtocolMap 必带"诚实边界"区块, ACP/A2A 标 design-only 并不接入 runtime。

> Q: 中栏 step 切换怎么不重置左右?
> A: `WorkbenchProvider` 用 `useReducer` 共享一个 state, 切 activeStep 只 dispatch 一个 action 不动其他字段。Playwright test_s54_14 验证: 加载 demo → 切到 step 3 → 切回 → trace 数保持。

## 8. 已知限制

- WorkbenchChat 意图识别是关键字正则, LLM 路径 S55 接入
- LLM 流式是手动 dispatch 多条, S55 接真实 SSE/streaming
- Tech Switches 折叠默认折叠, 面试时点开 — 适合演示节奏
- Step 6 导出是占位, S55 接入
- ProtocolMap 仅展示, runtime 不实现 (设计原则)

## 9. pytest / vitest 累计

| 范围 | 用例 |
|---|---|
| S52 Playwright | 5 |
| S53 vitest | 13 |
| S53 Playwright | 12 |
| **S54 vitest** | **+7** |
| **S54 Playwright** | **+17** |
| **新总数** | vitest 20 + Playwright 34 = 54 |
