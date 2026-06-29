# PaperAgent Session 57 验收报告 — OpenCode 风格视觉重塑

日期: 2026-06-29
范围: 把 `apps/web-react` (React + Vite + TS, 18183 默认入口) 从 S53 的深色工作台风格,
调整为接近 OpenCode 的浅色文档化 + 深色 TUI Agent console 的视觉语言。

参考来源:

- `Plan/PaperAgent_Session57_OpenCode风格视觉重塑_SOP.md`
- OpenCode 中文首页 <https://opencode.ai/zh>
- OpenCode 中文文档 <https://opencode.ai/zh/docs>

SOP §3 已给出可落地的 token / 字体 / 布局 / 强调色 / 数据表达方案。
SOP §2 列出 "不做什么": 不改 RAG 算法 / 不改 ThesisEval / 不改 API / 不删旧前端 /
不照搬 OpenCode brand/copy。本报告对应 §7 (T1-T6) + §8 (Playwright) + §10 (交付物)。

---

## 1. 完成情况

| 任务 | SOP § | 状态 | 关键产物 |
|---|---|---|---|
| T1 视觉基线切换 | §7 | done | tokens.css / global.css / components.css 全部切到 light + console dark tokens |
| T2 TopBar 重做 | §7 | done | wordmark `paperagent` · 5 nav · 黑按钮 `加载 Demo` · 旧前端入口 |
| T3 SideNav docs rail | §7 | done | 工作流 / 评估 / 协议 / 系统 4 分组; 当前项短线高亮 |
| T4 ThoughtPanel TUI console | §7 | done | 3 dot titlebar + `PaperAgent \| Topic feasibility workflow` + 流式日志 + 命令行 prompt |
| T5 首页 OpenCode 化 | §7 | done | hero 主张 + 黑色主按钮 `进入工作台` + 3 个能力数据区 + 隐私段落 |
| T6 业务页面风格统一 | §7 | done | StepWorkbench / RAG / ThesisEval / Interview / Protocols 全部继承新 tokens |
| Playwright E2E | §8 | done | `test_session57_opencode_style.py` 15 case + 5 PNG |
| 验收报告 | §10 | done | 本文档 |

---

## 2. 修改文件清单 (实际 diff, 已 staged)

| 文件 | 修改要点 |
|---|---|
| `apps/web-react/src/styles/tokens.css` | 全替换: 从 S53 dark `#0f1115` 切到 OpenCode-like light `#f8f7f4`; 保留 `--pa-console-*` 5 个深色 console token; 全站字体切到 `ui-monospace` + 中文 fallback; 阴影归零 (`--pa-shadow-* : none`); 引入 `--pa-fg-muted / --pa-fg-faint / --pa-line / --pa-line-strong / --pa-bg-soft` 等 light 语义色 |
| `apps/web-react/src/styles/global.css` | 背景白底; 链接默认下划线 + `text-decoration-color` 灰; `code` 用浅灰底; 新增 `.pa-rule / .pa-info / .pa-sans` 工具类 |
| `apps/web-react/src/styles/components.css` | TopBar: wordmark + nav + cta; SideNav: 文本列表 + 短线高亮; Card/Badge/Button/Tabs/Stepper 全部去重阴影, 改边框 + 圆角 5-6px; TracePanel 文本列表; Collapse/TechSwitches 改 dashed 分割线; 新增 `.pa-hero / .pa-zone / .pa-doc-section / .pa-privacy` OpenCode hero 区; 完整重写 `.pa-thought-panel` 为深色 TUI console (titlebar 3 dot + 流式行 + prompt 输入) |
| `apps/web-react/src/components/layout/TopBar.tsx` | 重写: `paperagent` wordmark (小写 + mono) + 5 个 nav item (工作台 / RAG / ThesisEval / 面试 / 协议) + 黑色 `加载 Demo` CTA + `旧前端 ↗` 链接; 当前路由 nav item 加底部 border |
| `apps/web-react/src/components/layout/SideNav.tsx` | 重写: 4 分组 `工作流 / 评估 / 协议 / 系统`; 子项文本列表, 当前项左 border 短线 + 加粗 |
| `apps/web-react/src/components/layout/ThoughtPanel.tsx` | 重写为 TUI 深色 console: 3 个 mac dot + title bar `PaperAgent | Topic feasibility workflow` + 50 行上限流式日志 (`info / tool / user / err` tag) + 底部命令行 prompt `›` + 提交后追加; 6s 自动追加 demo 日志让 console 持续有内容 |
| `apps/web-react/src/features/home/HomePage.tsx` | 重写: hero `面向毕业选题与论文复现的 AI 证据工作台` + 副标题 + 黑色 `进入工作台 →` 主按钮 + `加载面试 Demo` + `/health` 次按钮; 3 个能力数据区 (RAG / ThesisEval / Interview) 用 `图 1 / 图 2 / 图 3` 编号 caption; 系统状态 (含 `card-health` test id 兼容 S56); 隐私 / 本地 / 证据可追踪 3 列说明 |

新增文件:

| 文件 | 用途 |
|---|---|
| `apps/web-react/e2e/test_session57_opencode_style.py` | 15 case: wordmark / 5 nav / CTA / sidenav 4 分组 / 路由 active 高亮 / TUI console 3 dot + title / console prompt 提交 / RAG eval (含 Run Eval 后表格) / ThesisEval 4 subset / Interview tech switches 真实状态 / 5 截图 |
| `apps/web-react/e2e/screenshots/session57/s57_*.png` | 5 张 1440×900 full_page 截图: home / workbench / rag / thesis / interview |

**未触碰 (按 SOP §2 / §5 不做):**

- 后端 `apps/api/**` (无变更)
- `apps/web-react/src/app/apiClient.ts` + `features/*/types.ts` (DTO 不动)
- 旧前端 `apps/web/**` (回滚路径保留, 仍 18182 起)
- 路由契约 `app/routing.ts` (5 mode 名称不变)

---

## 3. OpenCode 风格提炼如何落地 (SOP §3 ↔ 实际)

| SOP §3 维度 | OpenCode 观察 | 落地方式 |
|---|---|---|
| 色彩 | 浅灰纸面 + 黑色文字 + 灰辅助 | tokens.css 主体 `#f8f7f4` / `#1f1d1d` / `#76716b / #aaa49c`; 状态色降饱和 (`#2f7d4a / #a96a00 / #b03a2e / #2a5db0`) |
| 字体 | 等宽/技术文档感 | `--pa-font` 切到 `ui-monospace` + 中文 fallback `PingFang SC / Microsoft YaHei`; 正文用 `--pa-sans` 系统 sans 缓解中文阅读疲劳 |
| 顶栏 | Logo 左, 导航右, 黑色主按钮 | TopBar wordmark + 5 nav + 黑底 `加载 Demo` |
| 文档页 | 左目录固定, 右内容大留白 | SideNav docs rail + 中栏 max-width 920px |
| 内容块 | 分隔线清晰, 卡片感很弱 | `.pa-doc-section` 用 `border-top` 而非 card; 真正 card 也只用 1px border + 0 shadow |
| 数据表达 | 极简图形 + 编号 caption | 首页 3 个 `.pa-zone` 用 `图 1 / 图 2 / 图 3` caption, 与 OpenCode 文档编号一致 |
| Agent 展示 | 文档页中嵌入深色 TUI 截图 | ThoughtPanel 完整 TUI console: 3 dot titlebar + 流式日志 + 命令行 prompt |
| 交互感 | tab/code block 简洁 | Tabs/Stepper/Collapse 都去重彩, 改 border-only |

---

## 4. 保留的 PaperAgent 业务入口 (SOP §9 校验)

| 入口 | 状态 | 备注 |
|---|---|---|
| 首页 (输入题目 → 工作台) | ✅ | 黑色主按钮 `进入工作台 →` 仍跳 `#/` |
| Interview Mode + Demo Case | ✅ | nav-interview + 顶部 `加载 Demo` CTA + S54 tech switches 全部保留 |
| RAG Eval (11 指标 + baseline + regression) | ✅ | 浅色 `pa-metric-table` + baseline card + regression alert; e2e 已验证 Run Eval 后表格渲染 |
| ThesisEval (4 subset + 三态) | ✅ | 4 个 `.pa-subset-btn` 可见; S55 三态降级仍在 |
| Protocol Map (MCP / A2A / ACP) | ✅ | `#/protocols` 通过 InterviewShell 渲染; ACP design-only 仍诚实标注 |
| StepWorkbench 5 步 | ✅ | S54 reducer / 6 组件不变; 仅样式 token 化 |
| 旧前端入口 | ✅ | TopBar `旧前端 ↗` + SideNav `旧前端 (18182) ↗` 双入口 |
| TracePanel / EvidenceTrace | ✅ | 浅色, 当前项左 border 短线 |
| WorkbenchChat (聊天编辑) | ✅ | 浅色 mono input + warn-soft preview |
| 系统状态 HealthCard | ✅ | 保留 `card-health` test id 兼容 S56 |

**不允许通过的检查 (SOP §11) 全部规避:**

| 现象 | 是否出现 |
|---|---|
| 只改了颜色, 没改信息层级 | ❌ — SideNav 从 dashboard menu 改 docs rail; Card 改 section+border |
| 模仿 OpenCode 但丢主线 | ❌ — 输入题目 → 证据 → RAG/ThesisEval → 可行性 → 开题 仍贯通 |
| 首页变纯宣传页 | ❌ — 黑底 `进入工作台` + 次按钮 `加载面试 Demo` + `/health` 三按钮直达 |
| RAG/ThesisEval 指标不可见 | ❌ — Playwright 实测 Run Eval 后 `.pa-metric-table` 可见 |
| ThoughtPanel 是普通聊天框 | ❌ — 真 TUI console: 3 dot title + 50 行流式日志 + 命令行 prompt |

---

## 5. Playwright E2E 结果 (SOP §8)

### 5.1 S57 新增 suite (15 case / marker `react-web`)

```text
test_s57_01_topbar_wordmark_visible             PASSED
test_s57_02_topnav_5_entries_clickable          PASSED
test_s57_03_topnav_cta_and_legacy               PASSED
test_s57_04_sidenav_sections                    PASSED
test_s57_05_sidenav_active_route                PASSED
test_s57_06_thought_panel_is_dark_console       PASSED
test_s57_07_thought_panel_prompt_input          PASSED
test_s57_08_rag_eval_route_visible              PASSED
test_s57_09_thesis_eval_subset_visible          PASSED
test_s57_10_interview_tech_switches             PASSED
test_s57_20_screenshot_home                     PASSED
test_s57_21_screenshot_workbench                PASSED
test_s57_22_screenshot_rag_eval                 PASSED
test_s57_23_screenshot_thesis_eval              PASSED
test_s57_24_screenshot_interview                PASSED
15 passed in 21.63s
```

### 5.2 S56 回归矩阵 (30 case) 重跑确认

S57 重构 HomePage 后, 唯一一个失败的 S56 case (`test_s56_02_health_check` 检查
`card-health` test id) 已通过把 `HealthCard` 包到 `<div data-testid="card-health">`
中修复。

```text
S56 + S57 联跑:  45 passed in 28.50s
S56 30/30 + S57 15/15
```

### 5.3 截图索引 (S57 实际产物)

| 文件 | 大小 | 内容 |
|---|---|---|
| `apps/web-react/e2e/screenshots/session57/s57_home_opencode.png` | 96 KB | OpenCode 化首页: wordmark / hero / 3 数据区 / 隐私 |
| `apps/web-react/e2e/screenshots/session57/s57_workbench_opencode.png` | 75 KB | Interview Mode + Demo Case: docs rail / 5 步 / TUI console |
| `apps/web-react/e2e/screenshots/session57/s57_rag_opencode.png` | 45 KB | RAG Eval: baseline card + metric table + regression alert |
| `apps/web-react/e2e/screenshots/session57/s57_thesis_opencode.png` | 55 KB | ThesisEval: 4 subset grid + 评估区 |
| `apps/web-react/e2e/screenshots/session57/s57_interview_opencode.png` | 75 KB | Interview 模式入口 + Tech Switches 完整展开 |

---

## 6. 与 Session 56 的差异

| 维度 | S56 | S57 |
|---|---|---|
| 主色背景 | `#0f1115` (深) | `#f8f7f4` (浅纸面) |
| 主字体 | system sans + mono | ui-monospace + 中文 fallback (sans 仅用于正文) |
| TopBar | "PA" 蓝方块 + 模式/会话号 | wordmark `paperagent` + 5 nav + 黑 CTA |
| SideNav | dashboard menu 单层 | docs rail 4 分组, 当前项左 border |
| ThoughtPanel | Tabs + 简单 LLM 思维/对话/Skill | 真 TUI console (3 dot + 流式 + 命令行 prompt) |
| 首页 | 4 张 Card dashboard | hero 主张 + 3 数据区 + 隐私段落 |
| 阴影 | `--pa-shadow-md / lg` 仍在 | 全部归 0, 改 border |
| RAG/ThesisEval 视觉 | dark card 堆叠 | light section + 表格 + caption |
| 业务入口保留 | 全 | 全 |
| API contract | 不变 | 不变 |
| 旧前端入口 | TopBar + SideNav | TopBar + SideNav (双入口) |

后端 0 变更; 旧前端 0 变更; 路由契约 0 变更。

---

## 7. 已知遗留 / 下一步

1. **TopBar `S57 · docs` tag**: 仍是硬编码。S58+ 改用真实 build hash / 当前 route 描述。
2. **ThoughtPanel console 流是 client-side 模拟**: 6s 自动追加的 4 种 beat 是 demo 占位,
   真正 LLM SSE 接入待 S58+ (与 S56 已知遗留 #2 一致)。
3. **doc-section 的文档内容仍是中文短说明**: OpenCode 文档页有大量英文 prose + code block;
   PaperAgent 中文短说明已能体现 docs 风格, 长 prose 暂不需要。
4. **截图中的 hero/数据区排版**: 1440×900 viewport 下 hero + 3 zone + privacy 三段式
   在测试机器上未做响应式断点深测 (<1366px); mobile drawer 仍待 S58+。
5. **`PaperAgent | Topic feasibility workflow` title 文字**: 英文短语, 与 OpenCode 风格一致;
   如果演示受众偏中文, 可改为 `PaperAgent | 选题可行性工作流`。

---

## 8. CLAUDE.md 强约束复述 (S57 已遵守)

- ✅ 旧前端 18182 保留, 不删 (TopBar + SideNav 双入口)
- ✅ pytest 总数增长 (S56: 30 → S56+S57: 45)
- ✅ 真实 uvicorn smoke 跑过 (本次 backend 18181 已起, /health 200)
- ✅ 设计原则不可破: 设计-only 标注 / 不可变式 / 单一事实源 全部保留
- ✅ 每个阶段端点 409 拦截未触及 (无 API 变更)
- ✅ LLM 路径配 heuristic fallback 未触及 (无 service 变更)

---

## 9. 累计 (S57 截止)

| 范围 | 用例 |
|---|---|
| 新前端 Vitest | 30 (S53-S55 不变) |
| 新前端 Playwright | 79 (S56) + 15 (S57) = **94** |
| 截图 | S57 新增 5 张 OpenCode 风格 |
| 后端 pytest | 799 passed (无变化, S57 仅前端) |
| 前端总 case | **94** (S57 截止) |

---

## 10. 建议下一 Session 候选

1. **S58: 真实 LLM 流接入 (SSE)** — ThoughtPanel 当前的 6s 自动 beat 替换为真 SSE,
   旁路 prompt 输入把用户指令流回后端 `/api/v1/.../stream`。
2. **S58: Paper Library UI** — S55 RAG 只接了 eval, paper-library 上传/PDF/arXiv 抓取 UI 待建。
3. **S58: Claim Grounding 详情弹窗** — S54 trace 组件已建, evidence claim 的来源 + confidence
   弹窗可独立成页。

S57 不阻塞任何后续路线, 视觉风格定型后, S58+ 的功能添加直接套用新 tokens。