# Demo Script 10 分钟

> 场景：`Interview Mode`
> 题目：`基于YOLO的钢材表面缺陷检测`

## 0. 打开入口（20 秒）

- 打开 `http://127.0.0.1:18182/?mode=interview`
- 说明这是“普通工作台 + 面试增强层”

## 1. 加载稳定 Demo Case（30 秒）

- 点击“面试演示模式（加载 Demo Case）”
- 指出顶部提示：这是固定演示数据，不是假装成实时检索

## 2. Workflow / Gate（70 秒）

围绕中栏讲解：

1. 为什么把流程拆成 5 步
2. 为什么每一步都要 Gate
3. 为什么导出要放到 Step 6

建议强调：

> 这里不是聊天框，而是带确认点的 Agent Workflow。

## 3. WorkspaceCommand（60 秒）

围绕左栏讲解：

- `仅讨论`：只回答，不改状态
- `生成修改建议`：先产出预览卡
- `确认修改`：真正落地并把后续步骤标记为 `stale`

建议强调：

> 我没有让 LLM 直接写工作区数据，而是通过可确认的命令预览中转。

## 4. Trace / Memory（60 秒）

围绕右栏讲解：

- 为什么要保留用户确认
- 为什么 reject / restore 也要留痕
- 为什么证据链和普通对话不能被同样压缩

建议强调：

> Trace 在这里不是普通日志，而是面向审计和 replay 的记忆层。

## 5. Deep Dive：RAG（80 秒）

打开 `RAG` 模块卡片。

需要讲清：

1. Query 拆解
2. 候选召回
3. Hybrid / Rerank
4. Candidate -> Evidence
5. 为什么当前不默认接真实向量库

## 6. Deep Dive：Memory / Agent（80 秒）

先开 `Memory`，再开 `Agent`。

要点：

- 哪些状态是 Working / Conversation / Trace / Evidence / Snapshot
- 为什么当前是 LangGraph friendly，但不是硬接 runtime
- 为什么 SubAgent / Multi-Agent 仍是 design-only

## 7. Tech Switches（45 秒）

展示：

- `on`
- `off`
- `design-only`

建议强调：

> 我会明确区分已落地、轻量实现和设计预留，不把架构草图当成功能交付。

## 8. Failure / Tests（55 秒）

打开 `Failure` 和 `Tests`。

要点：

- 后端离线时前端如何提示
- 哪些浏览器测试已经覆盖
- 哪些仍然是边界或 blocked，需要诚实说明

## 9. Step 6 导出收尾（20 秒）

回到导出区：

- 看 readiness 提示
- 看 backend 状态

收尾句：

> 这套系统最重要的不是“会生成”，而是“知道什么时候该停、该确认、该提示边界”。


## 10.讲解对应的文件与边界速查

被追问“能不能现在打开代码”时，按模块映射到真实文件：

- Workflow / Step Workbench：`apps/web/step_workbench.js`、`apps/web/e2e/test_one_topic_session41_step_workbench.py`
- LLM / WorkspaceCommand：`apps/web/e2e/test_one_topic_session42_workbench_chat_edit.py`
- Interview Mode：`apps/web/e2e/test_one_topic_session43_interview_mode.py`
- RAG Pipeline：`apps/api/app/services/rag_pipeline.py`、`apps/web/e2e/test_one_topic_session34_rag_eval.py`
- Evidence Governance：`apps/api/app/services/evidence.py`、`apps/api/tests/test_session17_demo_baseline.py`
- Memory / Trace：`apps/api/app/services/project_memory.py`、`apps/web/e2e/test_one_topic_session35_memory_replay.py`
- MCP / Tool Boundary：`apps/api/app/mcp/server.py`、`apps/web/e2e/test_one_topic_session36_mcp.py`
- Tests / Failure：`apps/web/app.js`、`docs/interview/Known_Limitations_For_Interview.md`

讲解口径提醒：implemented 能现场点开，lightweight 有稳定入口但不是生产版本，design-only 只做架构解释。Step 6 导出依赖后端 `18181`，离线时前端明确提示，不伪装成功。
