# PaperAgent · 技术亮点（对齐 Session 43）

## 亮点 1：Step Workbench 把 Workflow 前置到 UI

- 不是一次性全出结果
- 5 步主工作流 + Step 6 导出区
- 用户确认和重跑都在界面里可见

对应文件：

- `apps/web/step_workbench.js`
- `apps/web/e2e/test_one_topic_session41_step_workbench.py`

## 亮点 2：对话入口不直接改状态

- `仅讨论` 不改数据
- `生成修改建议` 只出预览
- `确认修改` 后才落地，并触发 `stale`

对应文件：

- `apps/web/step_workbench.js`
- `apps/web/e2e/test_one_topic_session42_workbench_chat_edit.py`

## 亮点 3：Interview Mode 把讲解入口和真实 UI 对齐

- `?mode=interview`
- 稳定 `Demo Case`
- 3 分钟 / 10 分钟脚本
- Deep Dive 模块索引

对应文件：

- `apps/web/index.html`
- `apps/web/styles.css`
- `apps/web/e2e/test_one_topic_session43_interview_mode.py`

## 亮点 4：implemented / lightweight / design-only 显式区分

这样做是为了避免两个常见问题：

1. 把设计预留说成已落地
2. 为了演示引入长期难维护的重依赖

当前口径：

- implemented：Workflow、WorkspaceCommand、Failure、Tests
- lightweight：RAG、Memory
- design-only：LangGraph runtime、SubAgent Router、MCP 深挖、ACP、A2A

对应文件：

- `apps/api/tests/test_session40_resume_packaging.py`（本亮点的三档结构由该测试校验）
- `docs/interview/AutoResearchClaw_对标与小型化移植.md`（design-only 对标参考）

## 亮点 5：失败路径和测试入口一起展示

- 后端离线时明确提示
- 导出前 readiness 状态可见
- 浏览器验收脚本可直接对应到面试讲解点

对应文件：

- `apps/web/app.js`
- `docs/interview/Known_Limitations_For_Interview.md`
- `apps/web/e2e/test_one_topic_session43_interview_mode.py`

## 亮点 6：Protocol Map — MCP / A2A / ACP 三层协议边界显式区分

这样做是为了避免面试官问"协议区别"时散点回答：

- **MCP**：Agent-to-Tool，当前已最小暴露（S36）
- **A2A**：Agent-to-Agent 任务委派 + 能力发现，design-only
- **ACP**：Agent-to-Agent Messaging + 异步流 + 多模态交换，design-only

当前口径：

- implemented：MCP 最小工具（4 个只读 tool）
- design-only：A2A 任务委派、ACP 消息总线、ACP-Control
- protocol_map 默认展示，acp_* 开关默认关闭

对应文件：

- `Plan/design/ACP_Interop_And_Agent_Communication.md`
- `apps/web-react/src/features/protocols/ProtocolMapPanel.tsx` (S54 迁移)

## 亮点 7：React + Vite 前端迁移 (Session 52-56)

旧前端 `apps/web/` (~1626 行 step_workbench.js + ~118 KB app.js) 迁移到 `apps/web-react/`:

- **设计系统**: 8 个 base 组件 (Button/Card/Badge/Tabs/Stepper/Collapse/Spinner/ErrorState) + tokens
- **状态机**: `useReducer + Context` 替代模块级 var + DOM; 切 step 不重置 trace/llm/chat 是关键不变式
- **路由**: 手写 hash router (60 行), 不引 react-router (省 ~50kB gz)
- **RAG Eval Dashboard**: 11 指标 (3 类) + baseline diff + regression alert, 阈值与后端 `eval_baseline.REGRESSION_THRESHOLDS` 1:1 对齐
- **ThesisEval Page**: 4 subset + 9 tag + 4 difficulty + verified/partial/failed 三态降级
- **测试**: 30 vitest + 49 Playwright e2e + 8 截图

S56 切换策略: 双前端并行, React 默认入口 18183, 旧前端保留 18182 备用 (回滚路径不删除).

对应文件：

- `apps/web-react/src/features/step-workbench/` (S54)
- `apps/web-react/src/features/rag-eval/RagEvalDashboard.tsx` (S55)
- `apps/web-react/src/features/thesis-eval/ThesisEvalPage.tsx` (S55)
- `apps/web-react/e2e/test_session56_regression_matrix.py` (S56, 30 case)
- `docs/frontend/ReactVite_Migration_Matrix.md` (S52-S56 进度)

## 亮点 8：评估口径单一事实源 (Session 50 + S55)

- 后端 `eval_baseline.REGRESSION_THRESHOLDS` 是单一来源
- 客户端 RagEvalDashboard 用同一份阈值表, vitest 单测验证方向判定
- 11 指标 3 类 (Retrieval/Answer/System), 方向标注 up/down, 下降阈值 0.05 (latency_p50 50ms, latency_p95 100ms)
- baseline 缺失不报错, 空态引导 "跑一次 Eval 后再保存"

对应文件：

- `apps/api/app/services/paper_library/eval_baseline.py` (后端单一来源)
- `apps/web-react/src/features/rag-eval/ragMetricLogic.test.ts` (客户端单测)
- `apps/web-react/src/features/rag-eval/RagEvalDashboard.tsx` (前端展示)
