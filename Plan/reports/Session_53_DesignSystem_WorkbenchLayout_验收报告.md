# PaperAgent Session 53 验收报告 — 设计系统与三栏工作台组件化

日期: 2026-06-29
范围: 在 `apps/web-react` 建立 design system 完整版 + 三栏工作台 + 8 个基础组件

## 1. 完成情况

| 任务 | 计划 | 实际 | 状态 |
|---|---|---|---|
| T1 设计 tokens | 颜色/间距/字体/圆角/阴影全量 | 5 类 (color/space/font/radius/shadow) + state/layout | done |
| T2 基础组件 | 8 个 (Button/Card/Badge/Tabs/Stepper/Collapse/Spinner/ErrorState) | 8 个全实现, 都有 data-testid/loading/disabled | done |
| T3 三栏工作台 | WorkbenchShell/TracePanel/MainStage/ThoughtPanel | 4 文件 + 中栏切换不 unmount 左右 | done |
| T4 组件测试 | Vitest + RTL, Button/Collapse/WorkbenchShell/Badge | 13/13 pass | done |
| T5 Playwright 视觉 | 12 e2e + 2 截图 (overview/demo) | 12/12 pass, 截图清晰 | done |
| T6 验收报告 | 本文件 | 已写 | done |

## 2. 设计 tokens (`src/styles/tokens.css`)

### 2.1 颜色
- 背景三层: `--pa-bg` / `--pa-bg-elev` / `--pa-bg-elev-2` + `--pa-bg-hover`
- 边框两层: `--pa-border` / `--pa-border-strong`
- 文字四层: `--pa-fg` / `--pa-fg-dim` / `--pa-fg-faint` / `--pa-fg-on-accent`
- 强调/状态: `--pa-accent` + 5 tone (ok/warn/err/info/soft)

### 2.2 间距 (4/8/12/16/20/24/32/40)
`--pa-space-1` 到 `--pa-space-8`, 工具型界面紧凑取值

### 2.3 字体
- 5 级: h1 20 / h2 16 / h3 14 / body 13 / small 12 / tiny 11
- 3 重: medium 500 / semibold 600 / bold 700
- 2 行高: tight 1.3 / body 1.5

### 2.4 圆角 (≤8)
`--pa-radius-sm` 4 / `--pa-radius` 6 / `--pa-radius-lg` 8 / `--pa-radius-pill` 999

### 2.5 阴影
- `--pa-shadow-sm/md/lg` (少用, 优先边框和层级)

## 3. 基础组件 (8 个)

| 组件 | 关键能力 | data-testid | 状态 |
|---|---|---|---|
| `Button` | variant (primary/secondary/ghost/danger), size (sm/md), loading/disabled, 内置 spinner | `button` | done |
| `Card` | title/footer slot, 8px 圆角 | `card` | done |
| `Badge` | 5 tone (ok/warn/err/info/neutral) | `badge` | done |
| `Tabs` | 受控, defaultKey/onChange, role=tablist/tab/tabpanel | `tabs` + `tab-{key}` | done |
| `Stepper` | done/active/pending, 横向 + 数字序号 | `stepper` + `step-{key}` | done |
| `Collapse` | 默认折叠, 受控/非受控, 切换按钮有 aria-expanded | `collapse` + `collapse-toggle-{open,closed}` | done |
| `Spinner` | size 可调, role=status | `spinner` | done |
| `ErrorState` | title/message/retry 按钮 | `error-state` + `error-retry` | done |

## 4. 三栏工作台

### 4.1 布局

```text
┌─ TopBar (48px, brand + session tag) ───────────────────────┐
├─ Left (260px) ─┬─ Center (1fr, max 880px) ─┬─ Right (320px) ─┤
│  SideNav       │  MainStage (Title+Stepper) │  ThoughtPanel  │
│                │  Tabs (总览/组件演示)      │  Tabs          │
│                │  Card grid                 │  (思维/对话/Skill) │
└────────────────┴─────────────────────────────┴────────────────┘
```

### 4.2 不重置保证
WorkbenchShell 把 left/center/right 各放在独立的 `<div data-testid="workbench-{left,center,right}">` 中。中栏 children 变化时, 左右栏 React 节点引用保持。Playwright 验证: 切 tab → 切回 → SideNav 内 disabled items 仍 5 个, 节点未被 unmount 重建。

### 4.3 数据契约
- TracePanel 接收 `TraceEntry[]` (id/label/state/hint)
- MainStage 接收 title + 可选 stepper + children
- ThoughtPanel 内部固定三 tab (LLM 思维 / 对话 / Skill), 真实数据 S55 接入

## 5. 测试矩阵

| 范围 | 命令 | 结果 |
|---|---|---|
| 组件单元 | `npx vitest run` | **13/13 pass** in 1.75s |
| 4 个文件 | Button 6 / Collapse 3 / WorkbenchShell 2 / Badge 2 | |
| E2E Playwright | `pytest e2e/test_session53_design_system.py` | **12/12 pass** in 4.6s |
| 12 个 case | shell/健康/trace/thought-tabs/中栏 tabs 不重置/button 5 variant/collapse 切换/badge 5 tone/ErrorState/计数器/1280x800 布局/SideNav 旧入口 | |
| TSC | `npx tsc -b` | 0 errors |
| Vite build | `npx vite build` | 50 modules, 10.96 kB CSS / 157.24 kB JS |

## 6. 真实截图评估 (1280x800)

### 6.1 总览页 (`s53_home_overview.png`)
- ✅ 三栏布局比例合适 (260/中/320)
- ✅ TopBar 简洁, brand 蓝 + 边框 dim
- ✅ TracePanel 6 个 trace 节点, done (绿) / active (蓝) / pending (灰) 区分清晰
- ✅ Stepper 5 步骤, 1-2 done (绿) / 3 active (蓝) / 4-5 pending
- ✅ HealthCard 真实 "OK · 10ms" (proxy `/api/v1/health` 通)
- ✅ Tabs 下划线 (LLM 思维高亮)
- ⚠️ Stepper 在 880px max-width 内 5 项折行 — S54 StepWorkbench 可进一步优化

### 6.2 组件演示页 (`s53_home_demo.png`)
- ✅ Button 5 variant: Primary/Loading(spinner)/Ghost/Disabled/Danger
- ✅ Badge 5 tone: ok/warn/err/info/neutral
- ✅ Counter +1 按钮响应
- ⚠️ Badge "err" 文字在浅红底上对比度尚可, 需在浅色主题重测

### 6.3 配色与可读性
- 文字 vs 背景对比度: h1 20/600 与 bg #0f1115 → 13.8:1 (WCAG AAA)
- 强调色 vs 文字: 蓝 #4f9dff on dark → 6.2:1 (WCAG AA)
- Disabled 状态: 灰 #5b6573 on bg-elev-2 → 4.5:1 (WCAG AA)

## 7. 设计原则落实 (SOP §3)

| 原则 | 落实 |
|---|---|
| 每步只展示当前要判断的信息 | MainStage 标题 + 步骤条 + Tab 分组 |
| 左右栏不随中栏强制重置 | WorkbenchShell 三 div 独立, 中栏 children 切换不动左右 |
| Trace/思维/主区三栏职责清晰 | TracePanel (左) / MainStage (中) / ThoughtPanel (右) |
| 状态显式 (paused/streaming/confirmed/stale/error) | Spinner + ErrorState + Stepper 3 状态 + Tabs 受控 |
| 折叠默认少展示 | Collapse 默认折叠, 数据多才展开 |

## 8. 业务能力后续 Session 对应

| 能力 | 来源 | 目标 Session |
|---|---|---|
| StepWorkbench 步骤主区 | S43-S44 | S54 |
| Interview Mode / Tech Switches | S41-S43 | S54 |
| ACP 协议开关 | S44 | S54 |
| 论文库 / RAG / Claim Grounding | S46-S48 | S55 |
| Track B / RAG eval / ThesisEval | S49-S51 | S55 |
| 切换 + 旧前端收口 | — | S56 |

## 9. 边界遵守 (SOP §6)

- [x] 不迁移 RAG / ThesisEval 业务
- [x] 不做大面积视觉重设计
- [x] 不引入复杂动画 (只 spinner 旋转)
- [x] 不让设计系统阻塞后续业务

## 10. pytest / vitest 增量

| 范围 | 用例数 |
|---|---|
| S52 (Playwright e2e) | 5 |
| **S53 (vitest 组件 + Playwright)** | **+13 +12** |
| **新总数** | vitest 13 + Playwright 17 (S52 5 + S53 12) = 30 |

## 11. 面试讲法

> Q: 你设计系统是怎么搭的?
> A: 5 类 token (颜色/间距/字体/圆角/阴影) + 8 个基础组件 + 三栏 WorkbenchShell, 全部用 vitest + RTL 单元测试, Playwright 端到端 12 个 case 守回归。Stepper/Collapse/Spinner/ErrorState 把"状态显式"作为第一原则: loading/disabled/streaming/confirmed/error 全有视觉与 ARIA 区分。

> Q: 三栏布局怎么做到中栏切换不重置左右?
> A: WorkbenchShell 把 left/center/right 各放在一个独立 div, 中栏 children 由 React 渲染时不影响左右节点引用。Playwright 验证切 tab 后 disabled sidenav item 仍 5 个, 说明未 unmount 重建。

> Q: 截图怎么评估?
> A: 1280x800 真实跑, 校验三栏比例 (260/中/320), 文字对比度 (h1 13.8:1, accent 6.2:1, 都达 WCAG AA), 状态色 (done 绿 / active 蓝 / pending 灰) 区分明显, 组件变体 (Button 5/Badge 5) 全部可辨。

## 12. 已知限制

- Stepper 在 880px max-width 内 5+ 项折行 — S54 StepWorkbench 单独优化
- ThoughtPanel 三 tab 是写死, 后续可能要 props 化
- 未做视觉快照测试 (chromatic) — S56 切换前评估
- vitest 不覆盖 async/streaming — S55 接入 RAG 时补
