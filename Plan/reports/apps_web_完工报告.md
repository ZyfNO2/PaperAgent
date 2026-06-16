# apps/web 完工报告：静态前端 + Playwright e2e 闭环

> 触发：用户需求"apps/web 建立一个简单的进行 Playwright 进行测试"
> 日期：2026-06-16
> 状态：**176/176 pytest 全过（含 6 条 web e2e：3 条原 HTTP 模拟 + 3 条新增真页面点击）**

---

## 1. 解决了什么问题

按 MVP 总报告 §8 P0 列表："建 apps/web (Next.js) 接入 21 端点 + Playwright happy/blocked path 测试"——本次**降级为 MVP 范围**：

- 不引入 Next.js / React / Vite 任何构建工具
- **纯 HTML + CSS + vanilla JS**（共 3 文件，~600 行）
- 接入 21 后端端点（Phase 01-08 完整闭环）
- Playwright **真浏览器真点击**走 happy + blocked path

## 2. 做了哪些工作

### 2.1 文件清单

```
apps/web/
├── index.html         100 行   8 Phase 卡片 + 表单 + 阻断 banner
├── styles.css          140 行   极简样式 (无构建工具, 纯 CSS)
├── app.js              300 行   状态机 + fetch 调用 21 端点
├── dev_server.py        40 行   http.server 在 18182 端口 serve 静态文件
└── e2e/
    └── test_web_e2e.py  190 行  3 条 Playwright 真页面测试
```

### 2.2 前端状态机

8 Phase 卡片，初始全部 disabled（除 Phase 01 表单）。每 Phase 完成后**逐步解锁**：

```text
Phase 01 表单提交
  ↓ POST /projects (201) → state.project_id
  ↓ POST /intake/validate (200 OK) → 解锁 Phase 02
Phase 02 题目拆解
  ↓ POST /topic/decompose → 解锁 Phase 03
...
Phase 08 最终材料
  ↓ POST /final_package/build → 拼 Markdown 初稿
GET /final_package/markdown → 浏览器下载 proposal_{id}.md
```

D 评级 → 阻断 banner 显示 + 6 个 Phase 卡片全部 disabled。

### 2.3 端点接入（21 → 全部）

前端 `app.js` 把每个按钮的 `data-action` 绑到对应端点（hepler `bindPhaseAction(phase, action, handler)`）：

| data-action | HTTP |
|---|---|
| decompose | POST .../topic/decompose |
| search-plan | POST .../search/plan |
| evidence-build | POST .../evidence/build |
| risk-evaluate | POST .../risk/evaluate |
| work-package | POST .../work_package/plan |
| proposal | POST .../proposal/draft |
| committee | POST .../committee/review |
| final-package | POST .../final_package/build |
| export-md | GET .../final_package/markdown（下载附件） |
| get-spec / get-plan / get-ledger / get-risk / get-work-package | 对应 GET |

### 2.4 Playwright 真页面测试（3 条）

`test_web_e2e.py`：

| 测试 | 验证 |
|---|---|
| `test_happy_path_01_to_08_via_real_browser` | 真填表 + 真点击 8 Phase 按钮 → 最终输出含 `ready_for_thesis: true` + `backend: PASS` |
| `test_blocked_path_d_rating_shows_banner` | 通过 API 建 D 项目 → 注入 state → banner 显示 + 6 个 phase 卡片 disabled |
| `test_refresh_persistence_get_endpoints` | 真走前 4 Phase → 新 context GET 3 个端点（模拟浏览器重启）全部 200 |

**关键差异** vs 原有 `test_browser_smoke.py`：

- 原 e2e 用 `page.request.post()`（HTTP stack 模拟）—— 不渲染页面
- 新 e2e 用 `page.click()` 真点击按钮 —— **真 Chromium 渲染 + 真 JS 执行 + 真 fetch 跨域**

### 2.5 后端 CORS 配置

前端 18182 → 后端 18181 跨域，加 `CORSMiddleware`：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:18182", "http://localhost:18182"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2.6 dev_server.py

`http.server.SimpleHTTPRequestHandler` 静态文件服务，端口 18182，conftest 自动启动（如果未运行）。

## 3. 数据流：真浏览器真点击 8 Phase

```text
浏览器 (18182)            后端 uvicorn (18181)         DB
                POST /api/v1/projects
                ────────────────────────────→  projects.payload
                ←──────────── 201 + id
                POST /api/v1/projects/{id}/intake/validate
                ────────────────────────────→
                ←──────────── 200 OK
                [前端 JS 解锁 Phase 02 按钮]
                POST /api/v1/projects/{id}/topic/decompose
                ────────────────────────────→  topic_specs.payload
                ←──────────── 200
                POST /api/v1/projects/{id}/search/plan
                ────────────────────────────→  search_query_plans.payload
                POST /api/v1/projects/{id}/evidence/build
                ────────────────────────────→  evidence_ledgers.payload
                POST /api/v1/projects/{id}/risk/evaluate
                ────────────────────────────→  risk_evaluations.payload
                POST /api/v1/projects/{id}/work_package/plan
                ────────────────────────────→  work_package_plans.payload
                POST /api/v1/projects/{id}/proposal/draft
                ────────────────────────────→  proposal_drafts.payload
                POST /api/v1/projects/{id}/committee/review
                ────────────────────────────→  committee_reviews.payload
                POST /api/v1/projects/{id}/final_package/build
                ────────────────────────────→  final_packages.payload
                GET /api/v1/projects/{id}/final_package/markdown
                ←──────────── 200 text/markdown
                [前端触发浏览器下载 proposal_{id}.md]
```

## 4. 验收对照

| §5.x 验收点 | 状态 |
|-------------|------|
| §5.1 Happy Path | ✓ `test_happy_path_01_to_08_via_real_browser` |
| §5.2 Blocked Path | ✓ `test_blocked_path_d_rating_shows_banner` |
| §5.3 导出验收：Markdown 可导出 | ✓ `bindPhaseAction(8, "export-md")` 调 `final_package/markdown` 端点 + 浏览器下载 |
| 刷新后 GET 端点恢复 | ✓ `test_refresh_persistence_get_endpoints` (真新 context) |

## 5. 过程中修复的真实 Bug

### Bug 1：浏览器 fetch 跨域失败

**现象**：Phase 01 表单提交后 `#out-01` 一直不可见。

**原因**：浏览器跨域策略阻止 18182 → 18181 fetch。后端 FastAPI 默认无 CORS header。

**修复**：加 `CORSMiddleware`，`allow_origins` 显式列 18182。

### Bug 2：`#out-01` 元素不存在

**现象**：`Cannot set properties of null (setting 'className')` —— `setOutput` 里 `document.getElementById('out-01')` 返 null。

**原因**：HTML 里 8 个 phase 卡片只有 Phase 02-08 有 `<div class="phase-output" id="out-0N">`，Phase 01 漏了。

**修复**：Phase 01 form 后追加 `<div class="phase-output" id="out-01"></div>`。

### Bug 3：测试断言大小写

**现象**：`AssertionError: 'ready_for_thesis: True' in ...` 失败。

**原因**：JSON 序列化把 Python `True` 转成小写 `true`，断言期望大写。

**修复**：测试断言改为 `assert "ready_for_thesis: true" in final`。

## 6. 与原计划的偏离

| 原计划（总报告 §8） | 实际 MVP | 升级方向 |
|---|---|---|
| Next.js (TypeScript) | 纯 HTML+CSS+vanilla JS | 加 Next.js + shadcn/ui |
| Playwright happy + blocked path | ✓ 3 条真页面 + 3 条原 HTTP 模拟 = 6 条 | 加更多 UI 流程断言 |
| React Flow 状态图 | 不接（无流程可视化） | Phase 09+ |
| ECharts 风险雷达图 | 不接 | Phase 09+ |
| Langfuse 追踪 | 不接 | Phase 10+ |

**降级原因**：MVP 优先把"端到端闭环 + 真浏览器验证"跑通，UI 美化留 Phase 09+。

## 7. 与规约的偏离

无字段偏离。两条**实现细节**标注：

1. **CORS 只允许 18182** —— MVP 范围；生产应加域名白名单
2. **每个按钮 click → fetch 一次端点** —— 没用 React/状态管理；MVP 简单 DOM 操作

## 8. 不在本工作的范围

- 状态机可视化（React Flow / ECharts）
- 用户登录 / 多项目
- 实时进度（WebSocket / SSE）
- DOCX / PDF 导出按钮（仍走 Markdown）

## 9. 一句话总结

> `apps/web` 用 3 个静态文件（HTML+CSS+JS）+ 1 个 dev_server 实现 8 Phase 真页面；3 条 Playwright 真浏览器测试覆盖 happy + blocked + refresh persistence，**3/3 全过**；`CORSMiddleware` 解决跨域；共 6 条 web e2e（3 新 + 3 原），全 176/176 pytest 通过。**MVP UI 层闭环**。
