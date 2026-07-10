# PaperAgent Re6.0 — 基线风险清单

> 冻结日期：2026-07-11 | 基线 commit：398b8f61

| ID | 风险 | 影响 | 受影响组件 | 建议处理阶段 | 严重度 |
|---|---|---|---|---|---|
| R-001 | Registry 切换不影响生产 `call_json`；新 provider 注册后不被 `llm_router.call_json` 使用 | 模型切换完全无效；用户配置的 provider 被静默忽略 | `llm_router.py`, `llm_provider_registry.py` | R6.2 | **高** |
| R-002 | `call_json` 的 `profile` 参数是字符串而非 registry 引用 | 无法做 contract-level provider 校验；拼写错误被静默 fallback 到默认 provider | `llm_router.py`, `llm.py` | R6.2 | **高** |
| R-003 | Formatter 写死 verifier 专有字段（`verdict`, `hit_keywords` 等）；其他节点调用时产出错误 schema | topic_parser / dataset_repo / work_package 的 schema 校验可能静默失败 | `llm_router.py`, `json_repair.py` | R6.2 | **高** |
| R-004 | `json_repair.py` 无 fenced block（```json）二次提取 | 某些模型在代码块中包裹 JSON 时无法解析 | `json_repair.py` | R6.2 | 中 |
| R-005 | 无 YAML-in-JSON 解析（如 `search_plan_yaml`） | search_planner 特定输出格式兼容性差 | `json_repair.py` | R6.2 | 中 |
| R-006 | `source_policy.py` `_expand_one_seed` 内懒 import `get_source_policy` | S2 API 在 policy.is_enabled 检查后可能被静默跳过；mock 测试失效 | `citation_expander.py`, `source_policy.py` | R6.1/R6.2 | 中 |
| R-007 | verify_node 空 expansion 回退 paper_candidates | 已 accept 论文被重验证清空 | `verify.py` | ✅ Re6.1 Fix B 已修 | — |
| R-008 | targeted_repair 空计划跳回 paper_retriever | 浪费 79s LLM + 无意义检索 | `targeted_repair.py` | ✅ Re6.1 Fix A 已修 | — |
| R-009 | `quality_gate` 的 `zero_accept_repair` 在 0 accept + 3+ weak 时阻断提升 | 有可用的 weak papers 但触发无效 repair 循环 | `quality_gate.py` | R6.1 性能修复 | 中 |
| R-010 | `dataset_repo_extractor` ThreadPoolExecutor 无 budget 控制 | 7 次 LLM 全失败耗时 90s 且不返回 partial | `dataset_repo_extractor.py` | R6.1 性能修复 | 中 |
| R-011 | LangGraph fan-out 声明为并行但实际串行 | 分析阶段耗时 ≈ 各节点之和 | `research_graph.py`, 各分析节点 | R6.1 性能修复 | 中 |
| R-012 | 无 `verify_scope` 显式区分 search/expanded/repair 三种调用路径 | verify_node 用 `citation_done` 猜测，逻辑易出错 | `verify.py` | ✅ Re6.1 Fix B 已修 | — |
| R-013 | 模型白名单硬编码在总纲 SOP 但代码中无强制校验 | 可能意外接入第三个模型 | `llm_router.py`, provider 注册逻辑 | R6.1/R6.2 | **高** |
| R-014 | Provider API v1 仍直接返回配置中的 raw key（若未 redact） | 安全风险：前端/API 响应泄露 API key | `api/v1/providers.py` | R6.1 | **高** |
| R-015 | 无 SSRF 防护：provider url 无 loopback/private/metadata 校验 | 用户输入的 provider URL 可能访问内网 | 无对应模块 | R6.1 | **高** |
| R-016 | 无 SecretStore：API key 明文存储 | key 泄露风险 | `.env`, 配置系统 | R6.1 | **高** |
| R-017 | 无 model discovery/probe：无法验证用户配置的 provider 是否可用 | 用户配置了不可用的 provider 后静默失败 | 无对应模块 | R6.1 | 中 |
| R-018 | 无 provider ledger：无法审计 provider 配置变更历史 | 安全审计盲区 | 无对应模块 | R6.1 | 低 |
| R-019 | `_expand_one_seed` 在 `citation_expander_node` 内创建新 event loop | 可能存在 event loop 嵌套问题 | `citation_expander.py` | R6.2 | 低 |
