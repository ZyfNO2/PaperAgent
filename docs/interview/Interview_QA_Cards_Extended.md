# PaperAgent 面试 QA 卡片（60+ 题）- 补充篇 (Session 38)

> 本文件是 S33 创建的 30 题卡片的补充。
> 原始 30 题在 `Interview_QA_Cards.md`。
> 本文件追加 32 题，分类如下：
>   - 项目总览扩展 5 题（Q31-Q35）
>   - RAG Deep Dive 5 题（Q36-Q40）
>   - Agent Deep Dive 5 题（Q41-Q45）
>   - Memory Deep Dive 5 题（Q46-Q50）
>   - MCP Deep Dive 5 题（Q51-Q55）
>   - Testing / Eval 5 题（Q56-Q60）
>   - Safety / Failure 2 题（Q61-Q62）

每张卡包含：`question` / `short_answer` / `project_evidence` / `files_to_show` / `follow_up` / `weakness_or_boundary`。

---

## Q31. 你的项目技术栈是什么？用了哪些 LLM？

**问题：** 完整技术栈？
**短答：** FastAPI + Pydantic v2 + Vue 3 + Vite + Playwright，LLM 用 Claude（Anthropic SDK）+ heuristic fallback。
**项目证据：** `apps/api/pyproject.toml` 列出依赖；`apps/web/package.json` 列出前端依赖。
**可展示文件：** `apps/api/app/main.py`、`apps/web/package.json`。
**追问：** 为什么不用 Django / Flask？
**边界：** LLM API key 在 `.env`，不 commit。

---

## Q32. 你的后端怎么分层？

**问题：** 后端架构？
**短答：** `app/api/v1/` 路由 + `app/services/` 业务 + `app/schemas_*.py` 数据契约 + `app/main.py` 入口。
**项目证据：** `apps/api/app/` 目录结构。
**可展示文件：** `apps/api/app/main.py`、`apps/api/app/api/v1/one_topic.py` 入口路由。
**追问：** 怎么保证 schema 和 service 一致？
**边界：** 没引入 ORM（如 SQLAlchemy），因为 MVP 用文件持久化。

---

## Q33. 你怎么处理 LLM 调用失败？

**问题：** LLM 不可用怎么办？
**短答：** 双层降级 — LLM JSON 模式失败 → heuristic 规则；API 报错 → 默认候选列表。
**项目证据：** `apps/api/app/services/llm.py` 的 `llm_call()` 统一入口。
**可展示文件：** `apps/api/app/services/llm.py`。
**追问：** heuristic 怎么生成关键词？
**边界：** 当前 heuristic 是 mock 关键词，未来可接 sentence-transformers。

---

## Q34. 你的 LLM 怎么和 prompt 配合？

**问题：** Prompt 怎么管理？
**短答：** Prompt 模板在 `apps/api/app/services/llm_content.py`，JSON 模式输出，结构化解析。
**项目证据：** `apps/api/app/services/llm_content.py` 模板。
**可展示文件：** `apps/api/app/services/llm_content.py`。
**追问：** Prompt 怎么版本管理？
**边界：** Prompt 模板未做版本化（每次 LLM 调用现场构造）。

---

## Q35. 你的后端有多少端点？

**问题：** 你的 API surface 有多大？
**短答：** ~40+ 端点，覆盖 intake / keyword / retrieval / evidence / feasibility / proposal / readiness / MCP / Memory。
**项目证据：** `apps/api/app/api/v1/one_topic.py` 主要路由（35+ 端点）。
**可展示文件：** `curl http://127.0.0.1:18181/openapi.json`。
**追问：** 怎么保证向后兼容？
**边界：** v0.x 阶段，路径不保证稳定。

---

## Q36. RAG 怎么防幻觉？

**问题：** RAG 系统怎么避免 LLM 编造？
**短答：** 三层防护：RAG 候选约束 + URL verified + Gate 校验。
**项目证据：** `apps/api/app/services/verification.py` URL 验证。
**可展示文件：** `apps/api/app/services/verification.py`、`apps/api/app/services/rag_evaluator.py`。
**追问：** URL 验证失败怎么处理？
**边界：** 当前是 HEAD 请求 mock，未真正访问网络。

---

## Q37. 你的 Rerank 怎么做的？

**问题：** 5 因子 Rerank 是什么？
**短答：** 关键词覆盖 + 年份新鲜度 + 引用数 + 类型权重 + 来源权重，加权得分。
**项目证据：** `apps/api/app/services/rag_pipeline.py` Rerank 函数。
**可展示文件：** `apps/api/app/services/rag_pipeline.py`。
**追问：** 权重怎么定？
**边界：** 启发式权重（method=0.4, year=0.2, cite=0.2, type=0.1, source=0.1），未做 A/B。

---

## Q38. 你的 RAG 评估指标哪个最重要？

**问题：** 8 指标里挑一个？
**短答：** `nDCG@10` — 排序质量，前 10 名最关键。
**项目证据：** `apps/api/app/services/rag_evaluator.py` 的 `compute_ndcg()`。
**可展示文件：** `apps/api/app/services/rag_evaluator.py`。
**追问：** 为什么不只看 Recall？
**边界：** nDCG 在小候选集（< 10）上不稳定。

---

## Q39. 检索为空怎么 fallback？

**问题：** `empty_retrieval` 怎么检测？
**短答：** `rag_evaluator.detect_empty_retrieval()` 检查 items.length == 0。
**项目证据：** `apps/api/app/services/rag_evaluator.py`。
**可展示文件：** `apps/api/app/services/rag_evaluator.py`。
**追问：** 触发后怎么处理？
**边界：** 当前仅标记，未自动扩展查询。

---

## Q40. 你的 RAG 怎么测试？

**问题：** RAG pipeline 怎么保证正确性？
**短答：** 25 个后端测试 + 8 个 Playwright，覆盖 pipeline 6 步 + 8 指标 + 5 检测器。
**项目证据：** `apps/api/tests/test_session34_rag_pipeline_eval.py`。
**可展示文件：** `apps/api/tests/test_session34_rag_pipeline_eval.py`。
**追问：** 评估集从哪来？
**边界：** Mock 评估集，未用真实 BEIR 数据。

---

## Q41. 你的 Agent 状态机有几步？

**问题：** Step Deck 几步？
**短答：** 8 步 — intake / keyword / query_plan / retrieval / candidate_scoring / feasibility / evidence_promotion / proposal_draft。
**项目证据：** `apps/web/src/components/StepDeck.vue`。
**可展示文件：** `apps/web/src/components/StepDeck.vue`。
**追问：** 哪步最容易出错？
**边界：** retrieval 步骤依赖外部 mock 数据源。

---

## Q42. 你的 Agent 怎么和前端通信？

**问题：** Step Deck 状态怎么同步？
**短答：** SSE 流式（每个 step 推送 `event_type`）+ REST 状态查询。
**项目证据：** `apps/api/app/api/v1/one_topic.py` 的 `/runs/{run_id}/stream` 路由。
**可展示文件：** `apps/api/app/api/v1/one_topic.py`。
**追问：** 断流怎么恢复？
**边界：** S35 已实现 Replay 端点。

---

## Q43. 你的 Agent 怎么避免重复调 LLM？

**问题：** 怎么去重？
**短答：** snapshot 缓存 + 关键词 + 候选 + LLM 输出 hash 组合。
**项目证据：** `apps/api/app/services/project_memory.py`。
**可展示文件：** `apps/api/app/services/project_memory.py`。
**追问：** 缓存多久过期？
**边界：** 当前不过期，由用户主动清除。

---

## Q44. 你的 Agent 怎么支持 undo？

**问题：** 用户改主意了怎么办？
**短答：** user_patch 事件 + snapshot 重建 + 不覆盖用户决策。
**项目证据：** `apps/api/app/services/run_event.py` 的 `append_user_patch()`。
**可展示文件：** `apps/api/app/services/run_event.py`。
**追问：** 多次 patch 怎么合并？
**边界：** 当前线性追加，未来支持合并。

---

## Q45. 你的 Agent 失败怎么重试？

**问题：** Step 失败怎么重试？
**短答：** 失败 → 写 trace → 失败原因 → 暴露给用户决策（不自动重试）。
**项目证据：** `apps/api/app/services/one_topic.py`。
**可展示文件：** `apps/api/app/services/one_topic.py`。
**追问：** 自动重试为什么不做？
**边界：** 不自动重试是 design choice — 怕浪费 LLM 预算。

---

## Q46. 你的 Memory 4 层各存什么？

**问题：** 每层存什么？
**短答：** ShortContext=step deck 状态；Transcript=RunEvent JSONL；ProjectMemory=项目级摘要；EvidenceMemory=不可变证据。
**项目证据：** `apps/api/app/services/project_memory.py`、`apps/api/app/schemas_memory.py`。
**可展示文件：** `apps/api/app/schemas_memory.py`。
**追问：** 为什么 Evidence 单独一层？
**边界：** 学术引用必须稳定。

---

## Q47. 压缩时什么事件永不被丢？

**问题：** 6 类 critical 事件？
**短答：** user_patch / gate / evidence_promotion / url_verified / readiness_check / llm_call。
**项目证据：** `apps/api/app/services/project_memory.py` 的 `DEFAULT_CRITICAL_TYPES`。
**可展示文件：** `apps/api/app/services/project_memory.py`。
**追问：** 为什么 llm_call 是 critical？
**边界：** debug 关键 + 成本审计。

---

## Q48. 怎么 replay 恢复 step 状态？

**问题：** Replay 怎么工作？
**短答：** `replay_project()` 加载 snapshot + events → 合并 step_states。
**项目证据：** `apps/api/app/services/project_memory.py`。
**可展示文件：** `apps/api/app/services/project_memory.py`。
**追问：** Replay 失败怎么办？
**边界：** 失败时显示「项目需重新开始」。

---

## Q49. `replay_source` 字段有什么用？

**问题：** 这个字段是干嘛的？
**短答：** 告诉前端数据来自 snapshot / transcript / both，便于调试。
**项目证据：** `apps/api/app/services/project_memory.py`。
**可展示文件：** `apps/api/app/services/project_memory.py`。
**追问：** 怎么判断"both"？
**边界：** snapshot + events 都非空时。

---

## Q50. EvidenceMemory 怎么确保不可变？

**问题：** 怎么保证不可变？
**短答：** 1) 永不被压缩；2) 没有 update API；3) 只能 add。
**项目证据：** `apps/api/app/services/project_memory.py` 的 `add_evidence_memory()`。
**可展示文件：** `apps/api/app/services/project_memory.py`。
**追问：** 错填了怎么办？
**边界：** 添加新 EvidenceRef 标记旧的不准确，不删除。

---

## Q51. MCP 暴露了几个 tool？为什么？

**问题：** 4 个 tool 是怎么定的？
**短答：** SOP 明确 — 只暴露读/检查，不暴露写/破坏。读 = 4 类（search/candidate/trace/readiness）。
**项目证据：** `apps/api/app/mcp/tools.py`。
**可展示文件：** `apps/api/app/mcp/tools.py`。
**追问：** 为什么不暴露 promote？
**边界：** 晋升是状态变更，需要用户确认。

---

## Q52. 工具调用失败怎么回客户端？

**问题：** 失败如何表达？
**短答：** HTTP 200 + `success: false` + `error.code`，业务/transport 分开。
**项目证据：** `apps/api/app/schemas_mcp.py` 的 `MCPToolCallError`。
**可展示文件：** `apps/api/app/schemas_mcp.py`。
**追问：** 为什么不抛 4xx/5xx？
**边界：** 业务失败 ≠ transport 错误。

---

## Q53. Forbidden 工具调用也写 Trace 吗？

**问题：** 拒绝的调用有审计吗？
**短答：** 是，**所有调用都写 Trace**，包括 forbidden 尝试。
**项目证据：** `apps/api/app/mcp/server.py` 的 `_write_mcp_trace()`。
**可展示文件：** `apps/api/app/mcp/server.py`。
**追问：** 怎么检测滥用？
**边界：** 当前不检测，Trace 已记录可后查。

---

## Q54. Trace 数据怎么脱敏？

**问题：** 敏感信息怎么办？
**短答：** `sanitize_trace_data()` 递归替换绝对路径为 `<redacted-path>`。
**项目证据：** `apps/api/app/mcp/permissions.py`。
**可展示文件：** `apps/api/app/mcp/permissions.py`。
**追问：** API key 也脱敏吗？
**边界：** 当前只脱敏路径，key 走 .env 不进 trace。

---

## Q55. MCP 怎么和 Gate 协作？

**问题：** search_topic_evidence 怎么判断 keyword gate？
**短答：** `permissions.check_permission()` 检查 `project_memory.get_latest_snapshot` 是否有 verdict。
**项目证据：** `apps/api/app/mcp/permissions.py`。
**可展示文件：** `apps/api/app/mcp/permissions.py`。
**追问：** Gate 状态实时吗？
**边界：** 是，每次调用实时检查。

---

## Q56. 你的测试怎么分层？

**问题：** 测试金字塔？
**短答：** 单元测试（~400+）→ 集成测试（TestClient）→ E2E（Playwright）。
**项目证据：** `apps/api/tests/` 单元 + 集成；`apps/web/e2e/` Playwright。
**可展示文件：** `apps/api/tests/` 目录。
**追问：** 怎么保证覆盖率？
**边界：** 当前未做严格覆盖率统计，靠测试数量增长。

---

## Q57. 你的 E2E 怎么写？

**问题：** Playwright 套路？
**短答：** 走 HTTP 真实 API，不 mock 后端，端到端验证。
**项目证据：** `apps/web/e2e/test_one_topic_session*.py` 多个 session 测试。
**可展示文件：** `apps/web/e2e/test_one_topic_session31_full_chain_baseline.py`。
**追问：** 启动太慢怎么办？
**边界：** 每个 session 测试独立文件，按需跑。

---

## Q58. 你的失败案例怎么测？

**问题：** 怎么测失败路径？
**短答：** Failure Cases 文档 + 专门的 session 测试（session4_pivot / session32_readiness）。
**项目证据：** `docs/interview/Failure_Cases.md`、`apps/web/e2e/test_one_topic_session4_pivot.py`。
**可展示文件：** `docs/interview/Failure_Cases.md`。
**追问：** 多少失败案例？
**边界：** 当前 ~10 个典型失败（无数据集、URL 失效、readiness 不足等）。

---

## Q59. 你的 readiness 怎么工作的？

**问题：** 8 维 readiness 是什么？
**短答：** section_completeness / evidence_binding / reference_integrity / template_fit / risk_disclosure / workload_clarity / innovation_safety / format_basic。
**项目证据：** `apps/api/app/services/readiness.py`。
**可展示文件：** `apps/api/app/services/readiness.py`。
**追问：** 哪一维最重要？
**边界：** evidence_binding 是硬约束，其余 warn。

---

## Q60. 你的回归测试覆盖什么？

**问题：** 怎么防回退？
**短答：** 每个 session commit 前必跑完整 pytest + Playwright；S31 baseline 专门测。
**项目证据：** `apps/api/tests/test_session31_full_chain_baseline.py`。
**可展示文件：** `apps/api/tests/test_session31_full_chain_baseline.py`。
**追问：** 怎么发现没测到的？
**边界：** 当前无 mutation testing。

---

## Q61. 你的项目最可能失败在哪？

**问题：** 最大风险？
**短答：** 三个：1) 外部 API 失效（mock 数据）2) LLM 成本失控 3) 用户决策被覆盖。
**项目证据：** `docs/interview/Failure_Cases.md`。
**可展示文件：** `docs/interview/Failure_Cases.md`。
**追问：** 怎么缓解？
**边界：** heuristic fallback 缓解第 1 条，cost budget 缓解第 2 条，user_patch 机制缓解第 3 条。

---

## Q62. 你的项目离生产还差什么？

**问题：** 距离上线最大缺口？
**短答：** 真实 embedding / 真实 LLM / 持久化数据库 / 鉴权 / 限流。
**项目证据：** `docs/interview/MultiAgent_Expansion_Design.md` §未来扩展。
**可展示文件：** `docs/interview/MultiAgent_Expansion_Design.md`。
**追问：** 优先级？
**边界：** 真实 embedding + 持久化 = 必须；鉴权 = 必须；限流 = 上线后补。

---

> **本附录为 S33 的 30 题补充至 62 题，分布在 7 个主题下。**
> **所有答案都基于真实项目代码，不虚构能力。**
> **每张卡都标注了项目证据 + 可展示文件 + 追问 + 边界。**
