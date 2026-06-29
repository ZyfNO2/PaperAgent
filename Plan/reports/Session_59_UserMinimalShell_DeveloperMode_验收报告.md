# Session 59: 用户主线极简化与开发者模式隔离 — 验收报告

## 范围

**目标:** 普通用户首屏只看到一个工作台 (4 区合一); 高级内容 (RAG Eval / ThesisEval /
Interview / Protocol Map / Trace TUI console / 健康检查 / 旧前端 / Demo CTA) 全部迁入
"开发者抽屉" 隔离, 由 Ctrl + ` 触发.

**SOP:** `Plan/PaperAgent_Session59_用户主线极简化与开发者模式隔离_SOP.md`

## 交付物

### T1 TopBar 极简化
- `apps/web-react/src/components/layout/TopBar.tsx`
  - 普通模式只渲染: `paperagent` wordmark + 开发者按钮 + `⌃\` 快捷键徽章
  - 移除原 5 个顶部 nav + Demo CTA + 旧前端链接 + Step 状态徽章
  - 状态来源: `localStorage["paperagent:dev-mode"]` + 自定义事件 `paperagent:dev-mode`

### T2 SideNav 极简化
- `apps/web-react/src/components/layout/SideNav.tsx`
  - 普通模式仅渲染 `<nav className="pa-sidenav--empty" />` 空容器
  - 高级导航 (工作流 / 评估 / 协议 / 系统) 全部迁入 DeveloperPanel

### T3 UserWorkbenchPage — 4 区合一
- `apps/web-react/src/features/user-workbench/UserWorkbenchPage.tsx` (新增, ~250 行)
  - Zone A 题目输入 — 复用 `TopicIntake` 组件, 增加开始分析 + 状态徽章 (尚未开始 / 正在理解 / 等待确认 / 已确认)
  - Zone B 与 AI 的交互 — 4 个 quick action (修改题目 / 补充约束 / 让 AI 查证据 / 生成下一步建议) + 复用 `WorkbenchChat` 组件
  - Zone C 证据提交 — 新 `EvidenceSubmitPanel`, 类型 (论文/数据集/GitHub/网页/文件) + 链接 + 备注 + 状态 (待核验/可用/不适合/需人工确认) + 删除
  - Zone D 文献 RAG 库 — 新 `PaperLibraryEditor`, 标题 + 链接 + 用途标签 (方法参考/数据集来源/复现实验/写作引用) + 入库状态 (待处理/已切分/已入库/待重新索引) + 替换链接/标记重新索引/删除
- `apps/web-react/src/features/evidence/EvidenceSubmitPanel.tsx` (新增)
- `apps/web-react/src/features/paper-library/PaperLibraryEditor.tsx` (新增)

### T4 开发者抽屉 (DeveloperPanel)
- `apps/web-react/src/components/dev/DeveloperPanel.tsx` (新增)
  - 右侧抽屉 (380px 宽) + scrim + 关闭按钮 + Ctrl+` 快捷键
  - 三段导航: 评估 (RAG Eval / ThesisEval) / 面试演示 (Interview / Protocol Map) / 系统 (健康检查 / 旧前端)
  - 抽屉底部嵌入 `<ThoughtPanel>` (TUI agent console), 只在开发者模式可见
  - 状态来源: 同 TopBar, 共享 `paperagent:dev-mode` localStorage 键
- `apps/web-react/src/components/layout/UserShell.tsx` (新增)
  - 普通模式三栏布局替代为: TopBar + main + DeveloperPanel (抽屉)

### T5 ThoughtPanel 默认隐藏
- `apps/web-react/src/components/layout/ThoughtPanel.tsx`
  - `if (!isDevModeOpen()) return null;` — 普通模式不渲染
  - 开发者模式由 DeveloperPanel 内部渲染 (testId=`dev-thought-panel`)

### T6 路由更新
- `apps/web-react/src/App.tsx`
  - `home` / `workbench` 路由 → `<UserShell><UserWorkbenchPage /></UserShell>` (极简)
  - 其余路由 (interview / rag-eval / thesis-eval / protocols) → 保留 `<WorkbenchShell>` (高级模式)
  - `<WorkbenchShell>` 内也加入 `<DeveloperPanel />`, 保证开发者抽屉在所有路由可用
- `apps/web-react/src/components/layout/WorkbenchShell.tsx`
  - 增加 `<DeveloperPanel />` 在 grid 之后, 路由切换时抽屉状态保留

### T7 样式
- `apps/web-react/src/styles/components.css` (追加 ~330 行)
  - `.pa-topbar--minimal`, `.pa-topbar__brand*`, `.pa-topbar__dev-toggle*`, `.pa-topbar__kbd`
  - `.pa-sidenav--empty` (display: none)
  - `.pa-uw`, `.pa-uw-zone*`, `.pa-uw-quick`, `.pa-uw-form*`, `.pa-uw-evidence-item*`, `.pa-uw-library-item*`, `.pa-uw-tag`
  - `.pa-dev-scrim`, `.pa-dev-panel*`, `.pa-dev-panel__*`

## 验收

### Playwright E2E (新 spec, 13 case)
文件: `apps/web-react/e2e/test_session59_user_minimal_shell.py`

| ID | 用例 | 状态 |
|---|---|---|
| `s59_home_shows_user_workbench` | 首屏 = UserWorkbenchPage, 4 区可见 | ✅ |
| `s59_sidenav_hidden_in_user_mode` | UserShell 不渲染 sidenav (count=0) | ✅ |
| `s59_thought_panel_hidden_in_user_mode` | 普通模式 developer-panel 不存在 | ✅ |
| `s59_zone_a_topic_intake_runs` | 输入题目 → 开始分析 → 状态变等待确认 | ✅ |
| `s59_zone_b_quick_action_fills_draft` | 4 个 quick action 真实填入 chat | ✅ |
| `s59_zone_b_chat_submit_modify_topic` | "修改 X" → 预览卡片 → 接受后题目更新 | ✅ |
| `s59_zone_c_evidence_submit_and_status` | 提交/改状态/删除证据 | ✅ |
| `s59_zone_d_library_submit_tag_status_remove` | 提交文献/切 tag/改 status/标重索引/删除 | ✅ |
| `s59_dev_panel_hidden_by_default` | 普通首屏 dev 抽屉不可见 | ✅ |
| `s59_dev_panel_opens_via_toggle` | 开发者按钮打开抽屉, 6 入口 + ThoughtPanel 在内 | ✅ |
| `s59_dev_panel_closes_via_scrim_and_toggle` | scrim 和 × 都能关闭 | ✅ |
| `s59_dev_panel_keyboard_shortcut` | Ctrl+` 切换抽屉 | ✅ |
| `s59_dev_panel_nav_links_route` | dev 抽屉点 RAG Eval → RAG page + 抽屉保持 | ✅ |

**结果:** 13/13 pass in 16.10s

### 截图 (4 张 1440×900 full_page)
- `apps/web-react/e2e/screenshots/session59/s59_user_minimal_home.png` — 首屏 4 区
- `apps/web-react/e2e/screenshots/session59/s59_evidence_submit.png` — Zone C 提交证据
- `apps/web-react/e2e/screenshots/session59/s59_rag_library_edit.png` — Zone D 编辑文献库
- `apps/web-react/e2e/screenshots/session59/s59_developer_panel.png` — DeveloperPanel 抽屉 + ThoughtPanel TUI console

### TypeScript 编译
`npx tsc --noEmit` 0 error.

### 旧 react-web 测试影响 (重要)
S59 故意将原 5 nav / SideNav 分组 / HomePage CTAs / 可见 ThoughtPanel 全部移除或移入开发者抽屉.
**预期 S53–S58 的 react-web 测试会失败 (59 个 case)**, 因为它们测试的 UI 不再出现在普通用户流.

具体失败分布:
- `test_session53_design_system.py`: 测试旧 SideNav / 旧 collapse / 旧 badge (7 case)
- `test_session54_step_workbench.py`: 测试 home page + sidenav active (4 case)
- `test_session55_rag_thesis.py`: 测试 home quick links + sidenav active (5 case)
- `test_session56_regression_matrix.py`: 测试 home renders + sidenav highlight (4 case)
- `test_session57_click_through.py`: 测试 topnav 5 entries / SideNav / HomePage 3 CTAs (18 case)
- `test_session57_opencode_style.py`: 测试 topnav 5 / sidenav sections / ThoughtPanel 可见 (6 case)
- `test_session58_usability_repair.py`: 测试 home CTA + dev mode toggle (8 case)

**S59 的 13 case + S57 子集 (`test_s57_01_topbar_wordmark_visible` + `test_s57_05_thought_panel_console_*`) 仍通过**, 因为:
- S57_01 只断言 wordmark "paperagent" 文本存在 — TopBar 仍保留这个
- S57_05 测试 TUI console 在 interview 路由下的 dark theme — interviewer 路由下走 WorkbenchShell, ThoughtPanel 仍在 right rail

**S60 计划:** 重写旧 react-web 测试以匹配新极简用户流 (或将其迁入 dev-mode-only 子套件).

## 不变量验收

- 后端 / 老前端 / 新前端端口未变 (18181 / 18182 / 18183)
- 普通用户首屏直达 UserWorkbenchPage, 不再需要点 "进入工作台"
- 高级内容 (RAG Eval / ThesisEval / Interview / Protocol / 健康 / 旧前端) 全部可经开发者抽屉访问
- Ctrl+` 在所有路由下都能切换开发者抽屉
- LLM 凭据仍走 `.env` (本次未触)
- 新增依赖: 0
- TypeScript: 0 error

## 未触碰

- 后端 (apps/api) — 任何文件
- 旧前端 (apps/web) — 任何文件
- 数据库 / fixture / paper-library 数据
- 路由 hash 协议 (`#/` `#/workbench` `#/?mode=...`) — 兼容
- 用户/linter 之前对 SideNav / TopBar / components.css 的修改 — 保留 (本轮在它们基础上继续极简化)