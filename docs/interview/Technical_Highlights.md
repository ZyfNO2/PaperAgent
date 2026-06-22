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
- design-only：LangGraph runtime、SubAgent Router、MCP 深挖

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
