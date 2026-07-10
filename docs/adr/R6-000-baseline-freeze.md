# ADR R6-000：Re6.X 基线冻结

> **状态**：已接受  
> **日期**：2026-07-11  
> **作者**：ZyfNO2 + Claude Opus 4.8  
> **基线 commit**：398b8f61

---

## 上下文

PaperAgent 进入 Re6.X "多模型与学术裁缝鲁棒性" 阶段。在引入 Provider Core（R6.1）、Router Unification（R6.2）、学术裁缝 2.0（R6.4）等结构性变更之前，需要冻结当前 provider/router/prompt/测试基线，形成可复现的对照锚点。后续所有 Re6.X 改动均与此基线对比，任一回归可追溯到具体 commit。

---

## 决议

### 冻结范围

| 层级 | 冻结对象 | 方式 |
|---|---|---|
| Provider | 当前默认 provider（OpenCode proxy）、model 列表 `[deepseek-v4-flash, big-pickle]` | `provider_router_snapshot.json` |
| Router | `llm_router.call_json` 入口逻辑、`FAST_JSON_PRIMARY` 配置 | git commit hash |
| JSON 解析 | `json_repair.py` 3-phase 解析链 | git commit hash |
| Re5 检索 | SearchController、SourceCatalog、query_ledger、search_agent | git commit hash |
| Prompt 模板 | `agents/prompts/` 下全部 28 个 .py/.md 文件 | 逐文件 SHA-256 hash |
| 测试 Fixture | `apps/api/tests/fixtures/` 下全部文件 | 逐文件 SHA-256 hash |
| 测试结果 | 当前 512 pass / 37 fail / 17 skip | `test_results.json` |
| Graph 核心 | `research_graph.py`、`state.py`、`nodes/` 路由逻辑 | git commit hash（包含 Re6.1 Fix A+B） |

### 模型白名单

**只允许使用以下两个模型（均通过 OpenCode proxy 接入）：**

| model_id | 用途 |
|---|---|
| `deepseek-v4-flash` | structured_extract / search_control / formatter / rag_answer / fast_json |
| `big-pickle` | evidence_critic / novelty_draft / narrative_write / premium_review |

**禁止引入第三个 model_id。** ProviderProfile 注册、ModelPolicy 白名单校验、前端 dropdown 均限定为这两个模型。

### 例外

- `Plan/PaperAgent_Re6.1_性能修复快速SOP.md` 中的 Fix A + Fix B（targeted_repair 空收敛 + citation_expander 空扩展跳 verify）**已包含在基线内**（commit d601ea67）。
- 该 SOP 的剩余部分（Section 1 观测埋点、Section 4 10-case 实验、Section 5 分析链并行）**不在基线范围内**，作为后续工作。
- Re6.1 Fix A 中 `quality_gate` 的 weak promotion feature flag（`PAPERAGENT_ZERO_ACCEPT_WEAK_POLICY`）已加入代码但默认值为 `repair`（保持现有行为），未改变生产路径。

---

## 后果

### 正面

- 所有 Re6.X 变更都有可对比的锚点；
- prompt hash 不可变 → 任何 prompt 修改都能被检测到；
- 模型白名单在代码和文档双写，防止静默引入第三个模型。

### 负面

- 在 R6.2 完成前不可修改 `llm_router.py`，即使发现 bug 也只能记录到风险清单；
- 测试通过率仅 91.4%，部分失败是 mock 路径问题（R-006），需在后续阶段修复。

### 风险

- 若 R6.2 Router Unification 延迟，双轨问题（R-001/R-002）会持续影响 provider 切换功能；
- 模型白名单目前仅在总纲 SOP 和快照文档中记录，代码层面（R6.1/R6.2）未强制校验。

---

## 后续阶段的修改条件

任一后续阶段如需修改冻结项：

1. 更新本 ADR 记录变更；
2. 在对应 Re6.X 的 `baseline_report.md` 中追加 diff；
3. 重新计算受影响文件的 SHA-256 hash 并更新 `prompt_hashes.json` 或 `fixture_hashes.json`；
4. 跑全量测试确认无回归。

### 基线测试集与 hidden 测试集的隔离规则

- **基线测试集**（`apps/api/tests/`）：可运行、可查看、可修复。用于验证 Re6.X 变更无回归。
- **hidden 测试集**（R6.5 创建于 `apps/api/tests/test_re6/hidden/`）：冻结后不可查看内容、不可调 prompt。仅用于盲测报告。违反此规则触发 No-go #7。
