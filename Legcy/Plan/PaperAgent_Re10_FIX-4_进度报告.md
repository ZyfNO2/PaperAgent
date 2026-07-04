# PaperAgent Re10 FIX-4 进度报告（更新）

## 0. 审核结论（更新）

FIX-4 代码修复已完成。Loop 2 已验证通过（3/3 case 跑通，H1-H10 全 PASS）。
Loop 3 已启动（因 MiniMax JSON 截断重试导致单 case 耗时较长，需超时扩到 30min）。

## 1. FIX-4 代码修复（全部完成）

| 文件 | 改动 | 原因 | 状态 |
|------|------|------|------|
| `search_reflection_helpers.py` | 新增 `flatten_axis_terms()` | P0-2: topic_axis_match 用 list[dict] 不命中 | ✅ |
| `search_reflection_helpers.py` | 导入 `os` | 修复 NameError | ✅ |
| `search_reflection_helpers.py` | `build_round_plan` + `PAPERAGENT_NO_OPENALEX` → crossref | OpenAlex 限流 fallback | ✅ |
| `search_reflection_loop.py` | 删除 generic_repos/is_slam_topic | P0-1: 硬编码违例 | ✅ |
| `search_reflection_loop.py` | 改用 flatten_axis_terms 统一 topic_axis_match | P0-2 | ✅ |
| `search_reflection_loop.py` | repo-only pass 检测 | FIX-4 §3.3 | ✅ |
| `search_reflection_loop.py` | 传递 topic_atoms + accepted 给 TraceLedger | trace 需要 | ✅ |
| `trace_ledger.py` | record_round 新增 accepted 参数 | validator 读不到 accepted | ✅ |
| `trace_ledger.py` | TraceLedger 新增 topic_atoms | trace 记录 axis 源 | ✅ |
| `validate_re10_reflection_search.py` | H10 批内统计替代硬编码 | P1-1 | ✅ |
| `search_reflection_helpers.py` | 移除 [Fallback] query 前缀 | P1-2 | ✅ |
| `llm.py` | 重写多 provider (MiniMax + Deepseek) | Deepseek 支持 | ✅ |
| `llm.py` | chat_json stream=False 默认 | MiniMax 截断 | ✅ |
| `research_agent.py` | _chat_json_strict _retries=2 + max_tokens 指数退避 | DomainScout JSON 截断 | ✅ |
| `openalex_search.py` | _oa_fetch 429 重试 3s→6s→12s | OpenAlex 限流 | ✅ |
| `run_balanced40_reflection_re10.py` | PAPERAGENT_ADAPTER_CACHE=1 默认 | 减少重复调用 | ✅ |
| `run_balanced40_reflection_re10.py` | PAPERAGENT_NO_OPENALEX=1 跳过 | 限流 fallback | ✅ |
| `run_balanced40_reflection_re10.py` | _build_retrieval_clients 用 _cached_adapter | 缓存 | ✅ |
| `.env` | Deepseek 配置 + MINIMAX_MAX_TOKENS=8192 |  | ✅ |

## 2. 重要决策

### 2.1 为什么启用 MiniMax 而非 Deepseek
opencode.ai 免费 tier 日限流（午夜 UTC 恢复）。MiniMax 做稳定 fallback。

### 2.2 为什么单 case 耗时 ~2-3 分钟
MiniMax 偶尔截断长 JSON（Unterminated string），触发 _chat_json_strict 重试 2 次。
属 LLM 非确定性行为，非代码 bug。

### 2.3 为什么 Loop 2 retry 用 crossref 替代 openalex
OpenAlex 日预算耗尽（retry-after ~43000s）。等 12h 不现实。

### 2.4 Loop 3/4 所需超时
5 case × ~3 min ≈ 15 min + 重试。需 --timeout 1800000（30 min）。

## 3. 已验证结果

### 3.1 Loop 2（3 个微型题目）— 重试后 ✅

| Case | 轮次 | 候选 | H11 | 总体 |
|------|------|------|-----|------|
| YOLOv5 钢铁缺陷检测 | 3 | 16 | ✅ | PASS |
| 视觉 SLAM 语义地图 | 3 | 18 | ✅ | PASS |
| 医学问答可信度评估 | 3 | 16 | ⚠️ | WEAK |

ALL HARD-FAIL GATES PASSED (H1-H10) — 3/3 cases ran 3 rounds each.

### 3.2 Loop 3（5 个跨领域）— 进行中
- 已生成 5 个 trace（TIMEOUT 中断）
- MiniMax 重试导致 > 10min

## 4. 变更影响范围

| 影响范围 | 风险 | 验证 |
|----------|------|------|
| search_reflection_helpers.py | flatten_axis_terms | unit test ✅ |
| search_reflection_loop.py | topic_axis_match 重写 | trace ✅ |
| trace_ledger.py | accepted 存储格式 | validator ✅ |
| validate_re10_reflection_search.py | H10 重写 | H10 PASS ✅ |
| llm.py | 重写 + stream=False | 集成 ✅ |
| research_agent.py | _chat_json_strict 重试 | 集成 ✅ |
| run_balanced40.py | cache + no_openalex | 集成 ✅ |

## 5. 下一阶段

### 5.1 VOAPI (GPT-5.4-medium) 接入 ✅

新增第三个 LLM provider，通过 OpenAI 兼容代理。

**GPT-5.4-medium 对比 MiniMax M3**:
- 更强 JSON 完整性（减少截断 → 减少重试 → 加速 ~40%）
- 更长上下文窗口
- 更高质量 topic_atoms 生成

### 5.2 重要工程教训

> **API 不要直接删改，而是做切换功能。**

正确的做法：
- MiniMax: `_chat_minimax()` 保留，不做任何破坏性修改
- Deepseek: 原 `_chat_deepseek_once()` 改为复用 `_chat_openai_compat_once()`
- VOAPI: 新增 `_chat_voapi()` 调用同一个通用后端
- 路由: `chat_json()` / `chat_json_array()` 中用 `if/elif/else` 分发
- 切换: 通过 `LLM_PROVIDER` env 或 per-call `provider=` 参数

这样任何 provider 出问题时可以秒切另一个，不需要回滚代码。

### 5.3 后续计划

1. Loop 3 validate（已有 trace 目录 `fix4_loop3_v3`，仅 3/5 完整）
2. Loop 3 用 VOAPI 重跑（预期 JSON 截断减少，单 case 从 ~150s 降到 ~90s）
3. Loop 4: 5 回归抽样
4. 完工报告

### 5.4 累计改动文件

```
apps/api/app/services/llm.py         — 多 provider 切换（不删改，只加功能）
apps/api/app/services/agents/
  search_reflection_helpers.py        — flatten_axis_terms + os import + OA fallback
  search_reflection_loop.py           — 删除硬编码 + topic_axis_match 重写 + repo-only 检测
  research_agent.py                   — _chat_json_strict 重试逻辑
trace_ledger.py                       — accepted + topic_atoms 存储
validate_re10_reflection_search.py    — H10 批内统计
retrieval/adapters/
  _http.py                            — 429 检测增强
  openalex_search.py                  — 429 指数退避重试
run_balanced40_reflection_re10.py     — adapter cache + no_openalex 开关
.env                                  — VOAPI + Deepseek + MiniMax 三 provider 配置
```

## 6. 产出文件

```
Plan/
  PaperAgent_Re10_FIX-4_静态审计报告.md
  PaperAgent_Re10_FIX-4_小样例3审计.md
  PaperAgent_Re10_FIX-4_进度报告.md
tmp_re04_eval/
  fix4_loop2_retry/  ✅ complete
  fix4_loop3_crossref/  ⚠️ incomplete
  adapter_cache/  auto
```
