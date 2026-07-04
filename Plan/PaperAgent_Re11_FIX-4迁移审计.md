# PaperAgent Re1.1 FIX-4 迁移审计

> SOP §3 要求：在动主链路之前阅读 Re10/FIX-4 完工报告，并把遗留问题对齐到 Re1.1。

## 1. 从 FIX-4 继承的资产

| 方向 | FIX-4 状态 | Re1.1 处理 |
| --- | --- | --- |
| 删除具体 repo 黑名单 | ✅ 完成 | 保留方向；本 graph 无仓库白名单硬编码（`test_re11_no_secret_leak.py::test_no_secrets_in_re11_code` 通过） |
| `topic_axis_match` 写 trace | ✅ 完成 | Graph 的 verify 节点写入 `hit_keywords / unrelated_keywords`，满足 |
| `dataset/repo` 抽取 | ⚠️ 弱（主要 0） | 新建 `dataset_repo_node`：从 verified papers 的 metadata/abstract/URL 优先抽取，失败打 `not_found_in_paper`，禁止伪造 |
| `VOAPI` 复核 | ✅ 完成 | 复用（premium_review）但默认不启用；小样例 0 调用 |
| `test_fix4_loop2.py` 可追溯 | ❌ 未完成 | 本轮补齐 `test_llm_router_re11.py` + `test_re11_research_graph_smoke.py` + `test_re11_no_secret_leak.py` + `test_re11_dataset_repo_from_papers.py` |

## 2. FIX-4 遗留问题 → Re1.1 映射

| FIX-4 问题 | 是否已解决 | 位置 |
| --- | --- | --- |
| dataset/repo = 0 | ✅ 部分 | dataset_repo_node 新实现；loop3 实测抽取状态 |
| VOAPI 被当常规模型（每 case 150-282s） | ✅ | 新增独立 premium_review profile；loop3 loop4 禁用 |
| LLM_PROVIDER 单入口 | ✅ | 新建 `llm_router.py` provider profile；旧入口保留 |
| StepFun adapter 不存在 | ✅ | `_chat_stepfun()` 已加 |
| 小样例 (`has_single_strong`) 过宽 | 保留 | verifier 现在是 hit_keywords-based，非单一轴 |
| `.env` 已写入 DeepSeek/StepFun/VOAPI | ✅ 部分 | DeepSeek key 过期，StepFun/VOAPI OK |
| `test_fix4_loop2.py` 未找到 | ✅ | 本轮 4 个目标测试全到位 |

## 3. 迁移红线（SOP §2.2）

- 禁止绕过 LangGraph 直接跑旧 runner：✅ graph.run + retrieve adapter 仅作 fallback
- 禁止候选标题硬编码黑名单：✅ 以 topic_atoms 为主的证据驱动
- 禁止领域白名单硬塞 dataset/repo：✅ topic 关键词反查 + 论文内抽取优先
- 禁止无 Trace 的 LLM 调用：✅ 所有 prompt node 写 `trace_events`
- 禁止 MiniMax 隐式 fallback：✅ 缺 key 或 disabled 显式 raise

## 4. 未解决（进入 Re1.1 loop3 验收）

- DeepSeek key 过期 → fast_json 默认走 `FAST_JSON_PRIMARY=stepfun`（显式路由项）；最终用户需补 DEEPSEEK key
- `_search_reflection_helpers.build_axis_bound_queries` 导入缺失 → legacy adapter 已隔离在 try/except，可被 fallback 替代
