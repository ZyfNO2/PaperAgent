# PaperAgent Re6.0 — 基线冻结报告

> **冻结日期**：2026-07-11  
> **基线 commit**：398b8f61（fix(re3.9.4): R39-GAS修复）  
> **后继阶段**：R6.1 Provider Core

---

## 1. Provider 配置摘要（不含 key）

| 项目 | 值 |
|---|---|
| Provider 类型 | OpenCode proxy（兼容 OpenAI Chat Completions API） |
| Provider 入口 | `llm_router.py` — `FAST_JSON_PRIMARY` 环境变量控制 |
| 主模型 | `deepseek-v4-flash`（fast_json / structured_extract / search_control / formatter / rag_answer） |
| 次模型 | `big-pickle`（evidence_critic / novelty_draft / narrative_write / premium_review） |
| 模型白名单 | **仅** `deepseek-v4-flash` + `big-pickle`；禁止第三个 model_id |
| 接入方式 | 统一通过 OpenCode proxy |
| Fallback 链 | `_chat_openai_compat_once` + `_chat_once_json_via_fallback`（3 次 retry / 1-2-4s 退避） |
| JSON 解析 | `json_repair.py` — 3-phase: direct → reasoning scan → fallback formatter |
| API key | `.env` 中存储；API 层使用 `api_key_set` 布尔标志，不暴露 raw key |

---

## 2. Provider Registry 与生产 llm_router 的关系

**现状：双轨并行。**

- `llm_provider_registry.py`：Pydantic ProviderProfile 注册表，定义了 schema 但代码中多数调用仍使用 `llm_router.call_json` + `profile` 字符串直接。
- `llm_router.py`：`FAST_JSON_PRIMARY` 环境变量指向单一 provider；`call_json` 硬编码 profile→provider 映射。
- `llm.py`：`call_json_with_validation` 入口，内部调用 `llm_router.call_json`。

**双轨影响**：
- Registry 的 ProviderProfile 未被 `call_json` 消费；
- 添加新 provider 时需要在 registry 和 router 两处同步；
- Task Role 模型（在 R6.0 总纲中定义）尚未被 router 消费；
- `call_json` 的 `profile` 参数是字符串，不是 registry 引用。

**本期约束**：provider/router 逻辑在未经 R6.2 Router Unification 之前不得变动。

---

## 3. 已知双轨问题清单

| ID | 问题 | 影响 | 建议阶段 |
|---|---|---|---|
| R-001 | Registry 切换不影响生产 `call_json` | 模型切换无效，新 provider 注册后不被使用 | R6.2 |
| R-002 | `call_json` profile 是字符串而非 registry 引用 | 无法做 contract-level 校验 | R6.2 |
| R-003 | Formatter 在 `_chat_once_json_via_fallback` 中写死字段 | verifier/topic_parser 等多节点共用同一 formatter，可能产出错误字段 | R6.2 |
| R-004 | `json_repair.py` 3-phase 解析中无 fenced block 二次提取 | 某些模型输出 ```json``` 包裹的 JSON 可能无法解析 | R6.2 |
| R-005 | 无 YAML-in-JSON 解析 | search_plan_yaml 兼容性问题 | R6.2 |
| R-006 | `source_policy.py` 引入后 `_expand_one_seed` 使用懒 import | 测试 mock 失效；S2 API 可能因 source_policy 被静默跳过 | R6.1/R6.2 |
| R-007 | verify_node 无 `verify_scope`（Re6.1 Fix B 已修） | 空 expansion 回退 paper_candidates 导致已 accept 被清空 | ✅已修 |
| R-008 | targeted_repair 空计划仍回 paper_retriever（Re6.1 Fix A 已修） | 浪费 79s LLM 调用 + 无意义检索 | ✅已修 |
| R-009 | `quality_gate` 弱提升时 zero_accept_repair 阻断 | 0 accept + 3+ weak 场景不提升 weak 而触发无效 repair | R6.1 Fix A（需 env 开关） |
| R-010 | `dataset_repo_extractor` 使用 ThreadPoolExecutor 但无 budget 控制 | 7 次 LLM 全失败耗时 90s | R6.1 性能修复 §5 |
| R-011 | work_package + sota_matcher 并行声明为 LangGraph edge 但未实际并发 | 分析阶段耗时 ≈ 各节点之和 | R6.1 性能修复 §5 |

---

## 4. Re5 检索链路状态

| 组件 | 状态 | 备注 |
|---|---|---|
| SearchController | 运行中 | `apps/api/app/services/search_controller.py`；Re5 LLM-as-router |
| SourceCatalog | 运行中 | `apps/api/app/services/search_catalog.py`；9 adapter |
| query_ledger | 运行中 | `apps/api/app/services/agents/graph/validators/query_ledger.py` |
| search_agent | 运行中 | `search_agent.py` — React agent，替代旧 `paper_retriever` |
| arXiv adapter | ✅ | |
| OpenAlex adapter | ✅ | |
| Crossref adapter | ✅ | |
| Semantic Scholar adapter | ✅ | 受 `source_policy` 懒 import 影响 |
| GitHub adapter | ✅ | |
| PubMed adapter | ✅ | Re3.9.1 强制注入修复 |

当前检索 arm：LLM 路由 + React agent search，template 模式（experiment_a/b/c 为 Re5 实验 template）

---

## 5. 测试通过率

| 指标 | 值 |
|---|---|
| 总测试数 | ~560 |
| 通过 | 512 |
| 失败 | 37（均为既有问题：mock 路径不匹配、旧模块名不存在、需要运行中 server） |
| 跳过 | 17 |
| 通过率 | 91.4% |

**已知跳过/失败项**：
- `test_one_topic_api.py` — 需要运行中 server（API 集成测试）
- `test_re1_1_research_graph_smoke.py::test_graph_nodes_registered` — 期望旧名 `retrieve`（REGISTRY 已改为 `paper_retriever`/`search_agent`）
- `test_re1_1_research_graph_smoke.py::test_graph_compiles_and_runs_offline` — 导入不存在模块 `retrieve`
- `test_re1_3_loop3_sse_stream.py` — SSE server 未启动
- 部分 mock path 不匹配测试（`semantic_scholar_search` 懒 import 绕过 patch）

---

## 6. 本期不可改动的文件列表

| 文件 | 原因 |
|---|---|
| `llm_router.py` | R6.0 基线冻结；R6.2 统一路由前不可改 |
| `llm.py` | 同上 |
| `json_repair.py` | 同上 |
| `llm_provider_registry.py` | 同上 |
| `search_catalog.py` | Re5 检索基线 |
| `search_controller.py` | Re5 检索基线 |
| `agents/prompts/` 下所有 `.py` 文件 | 提示词基线冻结 |
| `graph/validators/binding_validator.py` | Re4.3 合同基线 |
| `graph/validators/coverage_gate.py` | Re5.X 合同基线 |

---

## 7. 基线可复现验证

- [ ] Prompt hash 清单已生成（`prompt_hashes.json`）
- [ ] Fixture hash 清单已生成（`fixture_hashes.json`）
- [ ] Provider/Router 快照已生成（`provider_router_snapshot.json`）
- [ ] 测试结果快照已生成（`test_results.json`）
- [ ] `git checkout 398b8f61` 可重现当前基线状态
