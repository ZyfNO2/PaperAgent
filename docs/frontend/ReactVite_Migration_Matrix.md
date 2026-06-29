# PaperAgent · React + Vite 迁移矩阵

> Session 52 起始文档。来源: [PaperAgent_ReactVite前端重构_Session总规划](../../Plan/PaperAgent_ReactVite前端重构_Session总规划.md)
> 原则: **并行迁移**, 不在第一阶段直接覆盖 `apps/web`。

## 1. 工程对照

| 项 | 旧前端 | 新前端 |
|---|---|---|
| 路径 | `apps/web/` | `apps/web-react/` |
| 端口 | 18182 | 18183 |
| 启动脚本 | `apps/web/dev_server.py` | `npm run dev` (Vite) |
| 代理 | 无 (浏览器直连 18181) | Vite proxy `/api` → 18181 |
| 路由 | hash + query string | hash-state (S52) → 评估 react-router (S54) |
| 状态 | 模块级 var + DOM | `useState` / `useReducer` / Context |
| 样式 | 单文件 `styles.css` | tokens + components (S53 拆 design system) |
| 类型 | 纯 JS | TypeScript |
| 测试 | Playwright (apps/web/e2e) | Playwright (apps/web-react/e2e) |

## 2. 模块迁移矩阵

| 旧模块 | 文件大小 | 新 React 目标模块 | 目标 Session | 状态 |
|---|---|---|---|---|
| `step_workbench.js` | ~74 KB | `features/step-workbench/` | S54 | **done** (useReducer + Context, 5 步 8 status) |
| `step_deck.js` | ~42 KB | `features/legacy-step-deck/` (optional) | — | skipped (S56 收口决定) |
| `workspace_board.js` | ~13 KB | 合并到 `features/step-workbench/` | S54 | **done** |
| `stream_client.js` | ~4 KB | `features/step-workbench/components/ThoughtStream.tsx` | S54 | **done** (占位, S56 接真实) |
| `prompt_protocol.js` | ~10 KB | `features/protocols/ProtocolMapPanel.tsx` | S54 | **done** (MCP/A2A/ACP) |
| `committee_review.js` | ~7 KB | `features/interview-mode/DeepDiveDrawer.tsx` | S54 | **done** (9 module + 4 过滤) |
| `feasibility_card.js` | ~6 KB | 内嵌 StepCard | S54 | **done** |
| `proposal_draft.js` | ~7 KB | 内嵌 StepCard | S54 | **done** |
| `evidence_promotion.js` | ~6 KB | `features/step-workbench/components/EvidenceTrace.tsx` | S54 | **done** |
| `render_protocol.js` | ~10 KB | `app/renderProtocol.ts` | S54 | skipped (设计原则: 设计原则由 components 直接管) |
| `component_registry.js` | ~15 KB | `components/ui/` (8 个 base) | S53 | **done** |
| `app.js` | ~118 KB | 拆分到 `features/*` | S54-S55 | **done** (StepWorkbench / Interview / Protocols / RAG / ThesisEval) |
| `index.html` | ~35 KB | `apps/web-react/index.html` | S52 | **done** |
| `styles.css` | ~70 KB | tokens + components + design system | S53 | **done** (tokens + components.css ~880 行) |

## 3. 业务能力矩阵

| 能力 | 来源 Session | 新前端入口 | 状态 |
|---|---|---|---|
| 一题 → 关键词 → 检索 → 可行性 → 报告 | Phase 01-04 | `features/one-topic/` (workbench 5 步) | **done** (S54) |
| Interview Mode (Tech Switches + Deep Dive) | S41-S43 | `features/interview-mode/` | **done** (S54) |
| ACP 协议开关 + agent 通信治理 | S44 | `features/protocols/ProtocolMapPanel.tsx` | **done** (S54, design-only 诚实边界) |
| RealityCheck 资源四层 | S45 | 内嵌 `interviewData.ts` | **done** (S54) |
| 个人论文库 (arXiv/PDF) | S46 | `features/rag-eval/` 引用 | **partial** (S55 接 RAG, paper-library 入口未单独建) |
| 论文 RAG 检索问答 | S47 | `features/rag-eval/RagEvalDashboard.tsx` | **done** (S55, 评估入口; 问答 UI 待补) |
| Claim Grounding + Evidence Ledger 联动 | S48 | `features/step-workbench/components/EvidenceTrace.tsx` | **done** (S54, trace 组件) |
| 已有小论文扩展 Track B | S49 | TechSwitchPanel 显示 status | **done** (S54, status 标签) |
| RAG 评估指标 + 回归基线 | S50 | `features/rag-eval/RagEvalDashboard.tsx` | **done** (S55, 11 指标 + baseline diff) |
| 工科学位论文可行性评估 | S51 | `features/thesis-eval/ThesisEvalPage.tsx` | **done** (S55, 4 subset + 三态降级) |

## 4. 测试矩阵

| 测试 | 旧前端 | 新前端 |
|---|---|---|
| 后端 API | pytest (apps/api/tests) | 同左, 不变 |
| 旧 web e2e | Playwright `apps/web/e2e` (marker `legacy-web`) | 保留运行, 不删除 |
| 新 web e2e | — | Playwright `apps/web-react/e2e` (marker `react-web`) |
| 视觉/组件测试 | — | **30 vitest** (S53+S54+S55) |
| 类型 | — | `tsc -b` 0 errors |

### 4.1 新前端 e2e 范围 (S56 回归矩阵)

| 范围 | 用例 |
|---|---|
| 基础启动 | 首页 / health / 5 路由 |
| 工作台 | 5 步导航 / Demo Case / 切 step 不重置 trace / 暂停门 |
| 对话编辑 | chat 输入 / preview / accept |
| 面试模式 | 8 tech switch / ACP design-only / 9 deep dive module |
| 协议展示 | 3 行 / honest boundary / route 高亮 |
| RAG Eval | route / baseline / metric table / regression alert |
| ThesisEval | route / 4 subset / assess form / baseline / 切换 |
| 报告导出 | Step 6 入口 |
| 截图 | home / interview / rag-eval / thesis-eval |

## 5. 启动与停止

```bash
# 一键启动 (S56 切换后, 默认打开 React)
start_all.bat
# 启动后: backend 18181 + 旧 web 18182 + React web 18183 + 自动开 18183

# 单独启动 (调试用)
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181
.venv/Scripts/python.exe apps/web/dev_server.py                                # 旧 18182
cd apps/web-react && npx vite --host 127.0.0.1 --port 18183                   # 新 18183
```

### 端口分配

| 端口 | 服务 | 入口 |
|---|---|---|
| 18181 | 后端 API (uvicorn) | `/api/v1/...` |
| 18182 | 旧前端 (legacy) | `apps/web/dev_server.py` |
| 18183 | **新前端 (默认)** | `apps/web-react` (Vite dev) |

## 6. 切换策略 (S56)

选择方案 **B**: React 默认入口 (18183), 旧前端保留为备用 (18182)。

- `start_all.bat` 默认浏览器 → 18183
- `start_all.bat` 同时启动 18182 (失败不阻塞)
- `apps/web/` 不删除, 不归档, 保留回滚路径
- SideNav 的 "旧前端 (18182) ↗" 入口保留

不允许:

- 在 S56 直接删除 `apps/web/`
- 在 S56 把 React 未迁移能力标 done
- 把 backend 默认端口从 18181 改到其它 (会破坏旧前端回滚路径)

## 7. 验收状态

- [x] S52: 脚手架与迁移基线
- [x] S53: 设计系统与三栏工作台组件化
- [x] S54: StepWorkbench 与 Interview Mode 迁移
- [x] S55: RAG、论文库与 ThesisEval 前端接入
- [x] S56: React 前端切换与回归收口 (默认入口已切 18183)
