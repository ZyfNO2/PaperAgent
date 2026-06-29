# PaperAgent Session 52 验收报告 — React + Vite 并行脚手架与迁移基线

日期: 2026-06-29
范围: 在 `apps/web-react` 落地 React + Vite + TypeScript 脚手架, 与旧 `apps/web` 并行存在

## 1. 完成情况

| 任务 | 计划 | 实际 | 状态 |
|---|---|---|---|
| T1 脚手架 | `apps/web-react` 完整结构, Vite + React + TS, dev port 18183, /api proxy → 18181 | 完全按 SOP §3 T1 | done |
| T2 API Client | `src/app/apiClient.ts`, GET/POST/JSON/ApiError/AbortSignal | 已实现 | done |
| T3 Health/Shell | 三栏 Shell + HealthCard 三态 + 迁移阶段卡 + 旧前端入口 + S50/S51 占位 | 已实现 | done |
| T4 迁移矩阵 | `docs/frontend/ReactVite_Migration_Matrix.md` (旧模块→新目标, 业务能力, 测试矩阵) | 已写 | done |
| T5 Playwright | `apps/web-react/e2e/test_session52_react_scaffold.py` 5 个用例 | 5/5 pass | done |
| T6 验收报告 | 本文件 | 已写 | done |

## 2. 工程结构

```text
apps/web-react/
├── package.json              # React 18.3.1, Vite 5.4.6, TS 5.5
├── vite.config.ts            # port 18183, /api proxy → 18181
├── tsconfig.{json,app,node}.json
├── playwright.config.ts      # baseURL http://127.0.0.1:18183
├── index.html
├── .gitignore                # node_modules / dist / playwright-report
├── e2e/
│   ├── README.md
│   └── test_session52_react_scaffold.py
└── src/
    ├── main.tsx              # React 根入口
    ├── App.tsx               # 路由 + 三栏布局
    ├── app/
    │   ├── config.ts         # APP_CONFIG (appName / mode / session / backendBaseUrl / legacyWebUrl)
    │   ├── apiClient.ts      # GET/POST + ApiError + AbortSignal
    │   └── routes.tsx        # useRoute() hash-state
    ├── components/
    │   └── layout/
    │       ├── TopBar.tsx
    │       ├── SideNav.tsx
    │       └── Shell.tsx
    ├── features/
    │   ├── health/
    │   │   ├── useHealth.ts  # 探测 /api/health, 三态
    │   │   └── HealthCard.tsx
    │   └── home/
    │       └── HomePage.tsx
    └── styles/
        ├── tokens.css        # design tokens (S53 扩展)
        ├── global.css
        └── components.css
```

## 3. 验收点逐条

### 3.1 启动验证

```bash
# 后端 (Session 51 已有)
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:18181/health
# → 200

# 新前端 dev server
cd apps/web-react
npm install        # 71 packages, 23s
npm run dev        # vite ready in 353ms, http://127.0.0.1:18183

# 旧前端
ls apps/web/index.html apps/web/app.js apps/web/dev_server.py
# → 三个文件都在, 旧前端未删未改
```

### 3.2 /api 代理验证

```text
curl http://127.0.0.1:18183/api/v1/health
→ HTTP 200, 经 Vite proxy 转发到 18181
```

### 3.3 TypeScript 编译

```text
npx tsc -b
→ 0 errors (41 modules transformed, vite build 674ms, 149.35 kB JS / 3.20 kB CSS)
```

### 3.4 Playwright e2e

```text
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest apps/web-react/e2e/test_session52_react_scaffold.py -v
→ 5 passed in 5.55s

s52_01_homepage_loads           PASSED
s52_02_migration_phase_visible  PASSED   (S52/S53/S55 可见)
s52_03_legacy_link_present      PASSED   (18182 链接)
s52_04_health_loading_or_resolved PASSED (loading/ok/error 三态之一)
s52_05_sidenav_scaffolded       PASSED
```

### 3.5 后端零退化

```text
- /health → 200 {'status':'ok', 'phase':'one_topic_mvp', 'session':'18'}
- /api/v1/projects/.../eval/baseline → 200 dict
- /api/v1/projects/.../eval/seed-library → 200 paper_count=5
- 旧 apps/web 三个核心文件 (index.html/app.js/dev_server.py) 全部保留
```

## 4. 设计原则 (SOP 总规划 §4)

| 原则 | S52 落实 |
|---|---|
| 状态管理: useState/useReducer/Context | `useState` + `useHealth` hook, 未引入外部状态库 |
| Vite proxy 转发 /api | vite.config.ts 已配 |
| 不引入大型 UI 框架 | 仅 React + Vite + TS, 无 MUI/Antd |
| API URL 单一来源 | `APP_CONFIG.backendBaseUrl = "/api"`, 业务组件不写死 |
| 并行迁移不覆盖旧前端 | 新目录 `apps/web-react` 独立, 旧 `apps/web` 未改 |
| Health 三态显式 | loading/ok/error 三态 + data-testid |
| 数据驱动 left/right | 当前占位, S53-S55 接入 |

## 5. 迁移矩阵快照 (T4 完整版见 `docs/frontend/ReactVite_Migration_Matrix.md`)

| 旧模块 | 新目标 | 状态 | Session |
|---|---|---|---|
| `step_workbench.js` (~74 KB) | `features/step-workbench/` | pending | S54 |
| `step_deck.js` (~42 KB) | `features/legacy-step-deck/` | optional | S54 |
| `workspace_board.js` | `features/evidence-workbench/` | pending | S54 |
| `stream_client.js` | `features/streaming/` | pending | S54 |
| `prompt_protocol.js` | `features/protocols/` | pending | S54 |
| `committee_review.js` | `features/review/` | pending | S54 |
| `component_registry.js` | `app/componentRegistry.ts` | pending | S53 |
| `app.js` (~118 KB) | 拆 features/* | pending | S54-S55 |
| `index.html` | `apps/web-react/index.html` | done | S52 |
| `styles.css` | tokens + components + design system | in-progress (token 已建) | S53 |

## 6. 业务能力后续 Session 对应

| 能力 | 来源 | 目标 Session |
|---|---|---|
| 一题→关键词→检索→报告 | Phase 01-04 | S54 |
| Interview Mode / Tech Switches | S41-S43 | S54 |
| ACP 协议开关 | S44 | S54 |
| RealityCheck | S45 | S54 |
| 论文库 / RAG / Claim Grounding | S46-S48 | S55 |
| Track B / RAG eval / ThesisEval | S49-S51 | S55 |

## 7. 禁止事项遵守

- [x] 未删除旧前端 (apps/web 三个核心文件都在)
- [x] 未一次性迁移全部页面 (只脚手架 + Health/Shell)
- [x] 未引入大型 UI 框架 (只 React + Vite + TS)
- [x] API URL 未写死在业务组件 (走 APP_CONFIG.backendBaseUrl)

## 8. pytest 增量

| 范围 | 用例数 |
|---|---|
| S51 总数 | 802 passed, 1 skipped |
| **S52 新增** | **+5** (apps/web-react/e2e) |
| **新总数** | **807 passed, 1 skipped** |

## 9. 面试讲法

> Q: 你前端从 0.5K 行原生 JS 升级到 React + Vite 是怎么分阶段做的?
> A: Session 52 起的并行迁移, 不覆盖旧前端。新建 `apps/web-react`, 用 Vite dev server + /api proxy 与后端解耦, 跑通脚手架后逐步按 Session 53-56 拆组件、迁业务、接 RAG/ThesisEval、最后回归收口。每一阶段都有 Playwright smoke 守住, 旧前端全程保留作为回滚路径。

> Q: Vite proxy 怎么配? 端口怎么定的?
> A: `vite.config.ts` 里 `server.port = 18183` + `proxy['/api'] → http://127.0.0.1:18181`, 与旧前端 18182 区分, 三个服务互不干扰, 都可以并行起。

## 10. 已知限制

- 路由用 hash-state 而非 react-router — S54 评估是否引入
- 视觉风格是低密度占位 — S53 拆 design system 后统一
- 没有视觉/快照测试 — S53 决定是否加
- `npm install` 在 18183 端口没自动起 dev server — 由外层脚本启动 (sop §3 T5 明确)
