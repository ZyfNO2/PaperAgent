# PaperAgent · 项目深挖索引（Session 43）

> 面试时如果被追问“能不能马上打开代码、测试、文档”，优先从这里进入。

## 模块总表

| 模块 | 当前状态 | 代码 | 测试 | 文档 | 面试追问 |
|---|---|---|---|---|---|
| Workflow / Step Workbench | implemented | `apps/web/step_workbench.js` | `apps/web/e2e/test_one_topic_session41_step_workbench.py` | `docs/interview/Project_OnePager.md` | 为什么不是一次性生成？ |
| LLM / WorkspaceCommand | implemented | `apps/web/step_workbench.js` | `apps/web/e2e/test_one_topic_session42_workbench_chat_edit.py` | `docs/interview/Demo_Script_3min.md` | 为什么先预览再确认？ |
| RAG Pipeline | lightweight | `apps/api/app/services/rag_pipeline.py` | `apps/web/e2e/test_one_topic_session34_rag_eval.py` | `docs/interview/RAG_Design_Explainer.md` | 为什么现在不默认接向量库？ |
| Evidence Governance | implemented | `apps/api/app/services/evidence.py` | `apps/api/tests/test_session17_demo_baseline.py` | `docs/interview/Known_Limitations_For_Interview.md` | Candidate 和 Evidence 的边界？ |
| Memory / Trace / Replay | lightweight | `apps/api/app/services/project_memory.py` | `apps/web/e2e/test_one_topic_session35_memory_replay.py` | `docs/interview/Agent_Memory_Explainer.md` | 什么能压缩，什么不能丢？ |
| MCP / Tool Boundary | design-only | `apps/api/app/mcp/server.py` | `apps/web/e2e/test_one_topic_session36_mcp.py` | `docs/interview/MCP_FunctionCalling_Explainer.md` | 为什么默认不开放写工具？ |
| Agent / LangGraph Mapping | design-only | `apps/api/app/services/agent_router.py` | `apps/web/e2e/test_one_topic_session43_interview_mode.py` | `docs/interview/Deep_Dive_QA_Agent.md` | 为什么现在不用 LangGraph runtime？ |
| Protocols / MCP / A2A / ACP | design-only | `Plan/design/ACP_Interop_And_Agent_Communication.md` | `apps/web/e2e/test_one_topic_session44_protocols_acp.py` | `docs/interview/Deep_Dive_QA_MCP.md` | MCP / A2A / ACP 有什么区别？ |
| Failure / Tests | implemented | `apps/web/app.js` | `apps/web/e2e/test_one_topic_session43_interview_mode.py` | `docs/interview/Known_Limitations_For_Interview.md` | 后端挂了怎么表现？ |

## 推荐打开顺序

### 3 分钟演示

1. `Workflow / Step Workbench`
2. `LLM / WorkspaceCommand`
3. `Failure / Tests`

### 10 分钟深挖

1. `Workflow / Step Workbench`
2. `RAG Pipeline`
3. `Memory / Trace / Replay`
4. `Agent / LangGraph Mapping`
5. `Protocols / MCP / A2A / ACP`
6. `Failure / Tests`

## 当前真实口径

- `implemented`：当前 UI 或主链路里已经可见、可点、可演示
- `lightweight`：已有轻量实现或稳定讲解入口，但不是重型生产版
- `design-only`：只作为架构预留和面试解释，不参与当前默认执行

## Session 43 新增的前端深挖入口

这些入口都集中在 `Interview Mode`：

- `3min Demo`
- `10min Demo`
- `Deep Dive 模块卡片`
- `Interview Tech Switches`
- `关键热点按钮`

这样做的目的不是增加炫技层，而是把“代码证据、测试证据、文档证据”从散落状态收进一个现场可点开的壳里。

##模块速查（按面试深挖顺序逐模块展开）

## 模块 1：Workflow / Step Workbench

- 代码：`apps/web/step_workbench.js`
- 测试：`apps/web/e2e/test_one_topic_session41_step_workbench.py`
- 文档：`docs/interview/Project_OnePager.md`

## 模块 2：LLM / WorkspaceCommand

- 代码：`apps/web/step_workbench.js`
- 测试：`apps/web/e2e/test_one_topic_session42_workbench_chat_edit.py`
- 文档：`docs/interview/Demo_Script_3min.md`

## 模块 3：RAG Pipeline

- 代码：`apps/api/app/services/rag_pipeline.py`
- 测试：`apps/web/e2e/test_one_topic_session34_rag_eval.py`
- 文档：`docs/interview/RAG_Design_Explainer.md`

## 模块 4：Evidence Governance

- 代码：`apps/api/app/services/evidence.py`
- 测试：`apps/api/tests/test_session17_demo_baseline.py`
- 文档：`docs/interview/Known_Limitations_For_Interview.md`

## 模块 5：Memory / Trace / Replay

- 代码：`apps/api/app/services/project_memory.py`
- 测试：`apps/web/e2e/test_one_topic_session35_memory_replay.py`
- 文档：`docs/interview/Agent_Memory_Explainer.md`

## 模块 6：MCP / Tool Boundary

- 代码：`apps/api/app/mcp/server.py`
- 测试：`apps/web/e2e/test_one_topic_session36_mcp.py`
- 文档：`docs/interview/MCP_FunctionCalling_Explainer.md`

## 模块 7：Agent / LangGraph Mapping

- 代码：`apps/api/app/services/agent_router.py`
- 测试：`apps/web/e2e/test_one_topic_session43_interview_mode.py`
- 文档：`docs/interview/Deep_Dive_QA_Agent.md`

## 模块 8：Failure / Tests / Readiness

- 代码：`apps/web/app.js`
- 测试：`apps/api/tests/test_session32_readiness.py`
- 文档：`docs/interview/Known_Limitations_For_Interview.md`

## 模块 9：Project Intake

- 代码：`apps/api/app/services/intake.py`
- 测试：`apps/api/tests/test_session1_project_intake.py`
- 文档：`docs/interview/Architecture_Diagram.md`

## 模块 10：Topic Decomposition

- 代码：`apps/api/app/services/topic_spec.py`
- 测试：`apps/api/tests/test_session2_topic_decomposition.py`
- 文档：`docs/interview/Architecture_Diagram.md`

## 模块 11：Search Query Plan

- 代码：`apps/api/app/services/query_plan.py`
- 测试：`apps/api/tests/test_session3_search_query_plan.py`
- 文档：`docs/interview/RAG_Design_Explainer.md`

## 模块 12：Evidence Ledger / Promotion

- 代码：`apps/api/app/services/evidence_ledger.py`
- 测试：`apps/api/tests/test_session4_evidence_ledger.py`
- 文档：`docs/interview/Deep_Dive_QA_RAG.md`

## 模块 13：Protocols / MCP / A2A / ACP

- 代码：`Plan/design/ACP_Interop_And_Agent_Communication.md`
- 测试：`apps/web/e2e/test_one_topic_session44_protocols_acp.py`
- 文档：`docs/interview/Deep_Dive_QA_MCP.md`
