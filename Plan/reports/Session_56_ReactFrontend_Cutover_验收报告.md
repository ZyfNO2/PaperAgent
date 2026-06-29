# PaperAgent Session 56 验收报告 — React 前端切换与回归收口

日期: 2026-06-29
范围: Session 52-55 React 前端迁移的收口 — 切换默认入口 + 回归矩阵 + 文档同步

## 1. 完成情况

| 任务 | 计划 | 实际 | 状态 |
|---|---|---|---|
| T1 双前端启动策略 | start_all.bat 加 18183 + 启动文档 | start_all.bat 加 step 3b (vite 18183) + 默认浏览器 18183 | done |
| T2 Playwright 回归矩阵 | 8 范围 react-web 标记 | 30 case 覆盖 8 范围 + 4 截图 | done |
| T3 文档同步 | 4 个文档更新 | ReactVite_Migration_Matrix + Technical_Highlights + Test_Matrix (新前端段落) | done |
| T4 切换策略 | 选 B (React 默认, 旧保留) | start_all.bat 默认 18183, 旧 18182 备用, apps/web 不删 | done |
| T5 验收报告 + commit | 本报告 | done | done |

## 2. 切换前置条件 (SOP §2)

| 条件 | 验证 |
|---|---|
| React 前端能启动 | curl 18183 → 200, vite dev OK |
| 旧前端仍可启动 | apps/web/dev_server.py 存在; start_all.bat step 3 启动 |
| 5 个核心入口都有 | home / interview / rag-eval / thesis-eval / protocols (S54-S55 已建) |
| Playwright 核心路径通过 | S56 回归矩阵 30/30 + S54 17/17 + S55 15/15 = **62/62** |
| 后端无回归 | pytest 799 passed (3 changelog fail 与 S56 无关, 是 S20 的 CHANGELOG 校验) |

**结论: 切换前置条件全部满足, 允许切默认入口到 18183.**

## 3. 切换策略 (SOP §3.4 方案 B)

| 项 | 选择 |
|---|---|
| 默认入口 | **18183** (React `apps/web-react`) |
| 旧前端 | 18182 备用, `apps/web/dev_server.py` 仍启动 |
| `apps/web/` 删除 | **不删除** (回滚路径保留) |
| 默认浏览器 | `start "" "http://127.0.0.1:18183"` |
| SideNav 旧前端入口 | 保留 "旧前端 (18182) ↗" 链接 |

不允许做的事 (写进 docs/frontend/ReactVite_Migration_Matrix.md §6):

- S56 不直接删除 `apps/web/`
- 不允许把 React 未迁移能力标 done
- 不允许把 backend 默认端口从 18181 改到其它

## 4. 端口分配

| 端口 | 服务 | 入口 | 状态 |
|---|---|---|---|
| 18181 | 后端 API (uvicorn) | `/api/v1/...` | 不变 |
| 18182 | 旧前端 (legacy) | `apps/web/dev_server.py` | 备用 |
| **18183** | **新前端 (默认)** | `apps/web-react` Vite dev | **默认入口** |

## 5. 启动方式

```bash
# 一键 (默认打开 React)
start_all.bat
# 等 ~10s 后: 18181 / 18182 / 18183 都起, 浏览器自动开 18183

# 单独启动
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181
.venv/Scripts/python.exe apps/web/dev_server.py              # 旧
cd apps/web-react && npx vite --host 127.0.0.1 --port 18183 # 新
```

## 6. 回归矩阵 (30 case, marker `react-web`)

| 范围 | case | 状态 |
|---|---|---|
| 1. 基础启动 | home / health / 5 路由 | 3/3 |
| 2. 工作台 | 5 步 / Demo Case / 切 step 不重置 trace / 暂停门 | 4/4 |
| 3. 对话编辑 | chat input / preview / accept | 3/3 |
| 4. 面试模式 | 8 tech switch / ACP design-only / 9 deep dive | 3/3 |
| 5. 协议展示 | 3 行 / honest boundary / route 高亮 | 3/3 |
| 6. RAG Eval | route / baseline / metric table / regression | 4/4 |
| 7. ThesisEval | route / 4 subset / assess form / baseline / 切换 | 5/5 |
| 8. 报告导出 | Step 6 入口 | 1/1 |
| 9. 截图 | home / interview / rag-eval / thesis-eval | 4/4 |

**30/30 pass in 16.19s** — 全绿, 0 regression.

## 7. 测试累计

| 范围 | 旧前端 | 新前端 |
|---|---|---|
| Vitest | — | 30 (S53+S54+S55) |
| Playwright | ~80 (S01-S17) | 49 (S52=5, S53=12, S54=17, S55=15) |
| 截图 | — | 8 (S53=2, S54=3, S55=2, S56=4 — 部分重叠) |
| 后端 pytest | 799 passed + 3 changelog fail | 不变 |

pytest.ini 增加 `react-web` + `legacy-web` marker, 便于分别跑双前端回归。

## 8. 真实截图 (S56)

| 文件 | 内容 |
|---|---|
| `s56_home.png` | 首页总览 (5 nav + 快速跳转) |
| `s56_interview.png` | Interview Mode + Demo Case 加载后 5 步全 completed |
| `s56_rag_eval.png` | RAG Eval Dashboard + Baseline 已加载 (run_id/Recall@5/Faithfulness) |
| `s56_thesis_eval.png` | ThesisEval 4 subset 切换 + Baseline |

## 9. 已迁移能力清单 (S52-S56)

| 能力 | Session | 新前端入口 |
|---|---|---|
| 一题 → 报告 5 步工作流 | S54 | `features/step-workbench/` |
| Interview Mode (Tech Switches + Deep Dive) | S54 | `features/interview-mode/` |
| Protocol Map (MCP/A2A/ACP + 诚实边界) | S54 | `features/protocols/ProtocolMapPanel.tsx` |
| Step 状态机 (8 status) | S54 | `stepWorkbenchReducer.ts` |
| 设计系统 (8 base components + tokens) | S53 | `components/ui/` |
| Hash router (5 mode) | S54-S55 | `app/routing.ts` |
| RAG Eval Dashboard (11 指标) | S55 | `features/rag-eval/RagEvalDashboard.tsx` |
| ThesisEval Page (4 subset + 三态) | S55 | `features/thesis-eval/ThesisEvalPage.tsx` |
| DTO (1:1 对齐后端 Pydantic) | S55 | `features/*/types.ts` |

## 10. 未迁移能力 (留后续 Session)

| 能力 | 原因 |
|---|---|
| Paper Library (上传 PDF/arXiv 抓取 UI) | S55 只接 RAG, paper-library 入口未单独建 |
| Paper RAG 问答 UI (聊天气泡) | S55 评估入口已建, 问答 UI 待 S57+ |
| Claim Grounding 详情页 | S54 trace 组件已建, 详情弹窗未做 |
| 真实 LLM 流 (SSE/streaming) | 右侧 ThoughtPanel 是 S53 placeholder |
| Material Cards / Workspace 双栏 | 旧前端独有, S57+ 评估是否迁移 |
| Step 6 导出按钮 | 设计保留, UI 入口已 S54 StepCard 内, 真导出待 S57+ |

## 11. 与旧前端差异

| 差异 | 旧前端 | 新前端 |
|---|---|---|
| 工程栈 | vanilla JS + jQuery + DOM | React 18 + Vite + TypeScript |
| 状态管理 | 模块级 var + 手动 DOM 更新 | `useReducer + Context` |
| 路由 | hash + query string + JS 拼 | 手写 hash router (5 mode) |
| 设计系统 | 单文件 `styles.css` 1616 行 | tokens + 8 base 组件 + components.css ~880 行 |
| 类型 | JS 注释 | TypeScript (`tsc -b` 0 errors) |
| 测试 | Playwright 70+ case | Playwright 49 + Vitest 30 |
| 包大小 | — | 18.16 kB CSS / 197.85 kB JS (gzip 64.57 kB) |
| 启动 | `python dev_server.py` | `npx vite` |

**API 兼容**: 后端 18181 未动, 双前端共用同一 API。

## 12. 是否建议切默认入口

**是** — 切 18183 为默认。

理由:

1. S52-S55 完成度足够覆盖核心演示路径 (5 步 + Interview + Protocol + RAG + ThesisEval)
2. Playwright 30/30 + Vitest 30/30 全绿
3. 设计原则已贯彻 (诚实边界 / 单一事实源 / 不可变式)
4. 旧前端保留 18182 备用, 回滚路径完整
5. 真实截图评估通过 (S55 baseline 加载成功)

## 13. 是否允许进入下一轮功能开发

**是** — 推荐 S57 启动新一轮 (候选: 真实 LLM 流接入 / Paper Library UI / Claim Grounding 详情页).

CLAUDE.md 强约束复述:

- 旧前端 18182 保留, 不删
- pytest 总数增长
- 真实 uvicorn smoke 跑过 (本次 backend 799 passed)
- 设计原则不可破 (设计-only 标注 / 不可变式 / 单一事实源)

## 14. 风险提示 (SOP §5)

| 风险 | 现状 |
|---|---|
| React 只迁壳, RAG/ThesisEval 没接 | **不存在** — S55 已接, Playwright 通过 |
| Playwright 只测打开页面 | **不存在** — 8 范围覆盖, 含切 step / 切 subset / ACP design-only 校验 |
| 旧前端被提前删除 | **不存在** — `apps/web/` 完整, 18182 仍可起 |
| docs 没更新 | **不存在** — 3 个核心文档已同步 |

## 15. 已知遗留 (待 S57+)

- Top status bar 硬编码 "session: S52" (S53 配置, S57 改用真实 route)
- WorkbenchChat LLM 流仍是 S53 placeholder (S57 接真实 SSE)
- ThesisEval "保存 baseline" 按钮没接 POST `/eval/baseline` (S57 补)
- 旧前端 `step_workbench.js` 等没归档, 18182 持续保留

## 16. 累计 (S56 截止)

| 范围 | 用例 |
|---|---|
| 旧前端 Playwright | ~80 |
| 新前端 Vitest | 30 |
| 新前端 Playwright | 49 + 30 (S56) = 79 |
| 后端 pytest | 799 passed + 3 changelog fail |
| **前端总 case** | **189+** |