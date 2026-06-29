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
| `step_workbench.js` | ~74 KB | `features/step-workbench/` | S54 | pending |
| `step_deck.js` | ~42 KB | `features/legacy-step-deck/` (optional) | S54 | optional |
| `workspace_board.js` | ~13 KB | `features/evidence-workbench/` | S54 | pending |
| `stream_client.js` | ~4 KB | `features/streaming/` | S54 | pending |
| `prompt_protocol.js` | ~10 KB | `features/protocols/` | S54 | pending |
| `committee_review.js` | ~7 KB | `features/review/` | S54 | pending |
| `feasibility_card.js` | ~6 KB | `features/review/` (内嵌) | S54 | pending |
| `proposal_draft.js` | ~7 KB | `features/proposal/` | S54 | pending |
| `evidence_promotion.js` | ~6 KB | `features/evidence/` | S54 | pending |
| `render_protocol.js` | ~10 KB | `app/renderProtocol.ts` | S54 | pending |
| `component_registry.js` | ~15 KB | `app/componentRegistry.ts` | S53 | pending |
| `app.js` | ~118 KB | 拆分到 `features/*` | S54-S55 | pending |
| `index.html` | ~35 KB | `apps/web-react/index.html` (已建) | S52 | done (scaffold) |
| `styles.css` | ~70 KB | tokens + components + design system | S53 | in-progress (token 已建) |

## 3. 业务能力矩阵

| 能力 | 来源 Session | 新前端入口 | 状态 |
|---|---|---|---|
| 一题 → 关键词 → 检索 → 可行性 → 报告 | Phase 01-04 | `features/one-topic/` | S54 |
| Interview Mode (Tech Switches) | S41-S43 | `features/interview-mode/` | S54 |
| ACP 协议开关 + agent 通信治理 | S44 | `features/protocols/acp/` | S54 |
| RealityCheck 资源四层 | S45 | `features/reality-check/` | S54 |
| 个人论文库 (arXiv/PDF) | S46 | `features/paper-library/` | S55 |
| 论文 RAG 检索问答 | S47 | `features/paper-rag/` | S55 |
| Claim Grounding + Evidence Ledger 联动 | S48 | `features/claim-grounding/` | S55 |
| 已有小论文扩展 Track B | S49 | `features/small-paper/` | S55 |
| RAG 评估指标 + 回归基线 | S50 | `features/rag-eval/` | S55 |
| 工科学位论文可行性评估 | S51 | `features/thesis-eval/` | S55 |

## 4. 测试矩阵

| 测试 | 旧前端 | 新前端 |
|---|---|---|
| 后端 API | pytest (apps/api/tests) | 同左, 不变 |
| 旧 web e2e | Playwright `apps/web/e2e` | 保持运行直到 S56 |
| 新 web e2e | — | Playwright `apps/web-react/e2e` (S52 起) |
| 视觉/组件测试 | — | 评估 (S53 决定) |
| 类型 | — | `tsc -b` (S52 起) |

## 5. 启动与停止

```bash
# 后端 (不变)
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181

# 旧前端 (不变)
.venv/Scripts/python.exe apps/web/dev_server.py
# 访问 http://127.0.0.1:18182

# 新前端 (S52 起)
cd apps/web-react
npm install
npm run dev
# 访问 http://127.0.0.1:18183
```

## 6. 禁止事项 (来自总规划)

- 禁止在 Session 52 直接删除旧前端。
- 禁止一次性迁移全部页面。
- 禁止引入大型 UI 框架作为默认依赖, 除非先写明理由。
- 禁止把 API URL 写死在业务组件里 (必须经 `apiClient` + `APP_CONFIG.backendBaseUrl`)。

## 7. 验收状态

- [x] S52: 脚手架与迁移基线
- [ ] S53: 设计系统与三栏工作台组件化
- [ ] S54: StepWorkbench 与 Interview Mode 迁移
- [ ] S55: RAG、论文库与 ThesisEval 前端接入
- [ ] S56: React 前端切换与回归收口
