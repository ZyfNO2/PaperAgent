# PaperAgent — React / Reflection 反思提示词总览

> 本文档汇总 PaperAgent 项目中与 ReAct 循环、反思（Reflection）、修复（Repair）相关的提示词。
>
> 这些提示词分布在三个位置：
> 1. **Re3.0 ReACT 搜索 agent** — 节点内联 prompt，think→call→observe 循环
> 2. **Re10 SearchReflectionLoop** — 反思循环编排器（已归档但被引用）
> 3. **Re1.2 / Re08 修复 prompt** — 定向修复规划器
>
> 生成时间：2026-07-11

---

## 目录

- [1. 反思循环架构总览](#1-反思循环架构总览)
- [2. Re3.0 ReACT 搜索 Agent（生产主路径）](#2-re30-react-搜索-agent生产主路径)
  - [2.1 _SYSTEM_PROMPT（学术搜索策略师）](#21-_system_prompt学术搜索策略师)
  - [2.2 _build_decision_prompt（决策 user prompt 构造器）](#22-_build_decision_prompt决策-user-prompt-构造器)
  - [2.3 _generate_reflection_query（反思策略生成器）](#23-_generate_reflection_query反思策略生成器)
- [3. Re10 ReflectionCriticAgent（反思评审员）](#3-re10-reflectioncriticagent反思评审员)
  - [3.1 _SYSTEM（搜索结果反思 Agent）](#31-_system搜索结果反思-agent)
  - [3.2 规则层 _rule_layer（LLM 失败时的反思兜底）](#32-规则层-_rule_layerllm-失败时的反思兜底)
  - [3.3 _PROBLEM_TO_ACTION 映射表](#33-_problem_to_action-映射表)
- [4. Re10 DomainScoutAgent（领域侦察）](#4-re10-domainscoutagent领域侦察)
  - [4.1 _SYSTEM（领域检索侦察 Agent）](#41-_system领域检索侦察-agent)
  - [4.2 _build_user_prompt（领域侦察 user prompt）](#42-_build_user_prompt领域侦察-user-prompt)
- [5. Re1.2 定向修复规划器（targeted_repair）](#5-re12-定向修复规划器targeted_repair)
  - [5.1 SYSTEM（修复策略规划器）](#51-system修复策略规划器)
  - [5.2 build() user prompt 模板](#52-build-user-prompt-模板)
- [6. Re08 Gap Repair Planner（缺口修复规划器）](#6-re08-gap-repair-planner缺口修复规划器)
- [7. 修复循环触发条件](#7-修复循环触发条件)
- [8. 重要提示：归档状态告警](#8-重要提示归档状态告警)

---

## 1. 反思循环架构总览

PaperAgent 项目中有**两套**反思/ReAct 系统：

### 1.1 Re3.0 ReACT 搜索 Agent（生产主路径）

- **文件**：`apps/api/app/services/agents/graph/nodes/search_agent.py`
- **位置**：LangGraph 的 `search_agent` 节点，替代了固定 adapter 的 `retrieve_node`
- **循环**：`think → call → observe → decide`，最多 8 步
- **触发**：每次 `search_agent_node` 被调用时执行
- **状态**：生产环境主路径

```
search_agent_node 入口
  ↓
循环 step 0..7 (_MAX_STEPS=8):
  1. Think:  _llm_decide() → LLM 返回 {action, tool, query, reason}
  2. 域工具注入检查 (pubmed for medical)
  3. 反思触发检查 (Re3.9.4):
     - 若 LLM 决定 stop 但论文相关度 < 30%
     - 调用 _generate_reflection_query() 生成新查询
     - 拒绝 stop，继续搜索
  4. 若 action == "stop" → break
  5. Call: _run_tool_sync(tool, query)
  6. Observe: _classify_results() → papers + repos
  7. 记录 step，避免重复 tool+query 组合
  8. 全工具失败 → 提前 break
  ↓
去重 + 返回 raw_results + paper_candidates + repo_candidates + search_steps
```

### 1.2 Re10 SearchReflectionLoop（已归档但被引用）

- **文件**：`apps/api/app/services/agents/search_reflection_loop.py`
- **编排**：多轮反思循环（最多 3 轮）

```
DomainScout → Plan queries → SearchExecutor → ObservationBuilder
  → ReflectionCritic → URLRepair / QueryRepair / drop
  → CandidateVerifier → EvidenceMerger → StopController
```

> ⚠️ **告警**：`search_reflection_loop.py` 导入了 `domain_scout_agent` 和 `reflection_critic_agent`，但这两个文件**只在归档目录** `apps/api/tests/_archived_legacy_sessions/` 中存在。详见 [第 8 节](#8-重要提示归档状态告警)。

---

## 2. Re3.0 ReACT 搜索 Agent（生产主路径）

### 2.1 _SYSTEM_PROMPT（学术搜索策略师）

- **文件**：[apps/api/app/services/agents/graph/nodes/search_agent.py](file:///g:/PaperAgent/apps/api/app/services/agents/graph/nodes/search_agent.py)
- **变量**：`_SYSTEM_PROMPT`（行 75–106）
- **用途**：ReACT 循环的 system prompt，告诉 LLM 如何决策下一步搜索什么工具/查询，何时停止。
- **关键参数**：`_MAX_STEPS=8`、`_MIN_PAPERS=5`、`_MIN_REPOS=1`

```text
你是学术搜索策略师。根据题目、已有结果和搜索历史，决定下一步搜索什么。

可用工具:
- arxiv: 搜预印本论文
- openalex: 搜学术期刊论文
- crossref: 搜DOI注册论文
- github: 搜代码仓库
- semantic_scholar: 搜高被引论文
- huggingface: 搜模型和数据集
- core: 搜开放获取论文
- datacite: 搜注册数据集
- pubmed: 搜医学/生物论文（仅医学领域可用，查看 available_extra_tools 确认是否可用）

判断标准:
- 如果还没有论文 → 搜 method+object 组合
- 如果论文太少 (<5) → 扩大范围或换关键词
- 如果论文够多 (≥5) 但没 repo → 搜 github
- 如果论文够多 + 有 repo → 停止
- 如果某个工具在 failed_tools_do_not_retry 列表中 → 不要再用它，换其他工具

输出 JSON:
{"action": "search" | "stop", "tool": "arxiv|openalex|crossref|github|semantic_scholar|huggingface|core|datacite|pubmed", "query": "...", "reason": "..."}

如果搜索结果已经足够，输出:
{"action": "stop", "reason": "已有 N 篇论文 + M 个 repo，足够开始分析"}

如果所有工具都失败了，输出:
{"action": "stop", "reason": "all tools failed"}

重要: 不要重复已经用过的 tool+query 组合。查看 prior_steps 列表，如果某个查询已经执行过，必须换关键词或换工具。

[OUTPUT CONTRACT] 你必须输出且仅输出一个合法 JSON 对象，不要输出其他内容。
```

### 2.2 _build_decision_prompt（决策 user prompt 构造器）

- **文件**：同上
- **函数**：`_build_decision_prompt(...)`（行 109–158）
- **用途**：把当前 state 构造为 JSON 形式的 user prompt，给 LLM 决策下一步。

构造出的 user prompt 是一个 JSON 对象，字段包括：

```json
{
  "topic": "<截断到 200 字的题目>",
  "method_keywords": ["前 5 个 method 关键词"],
  "object_keywords": ["前 5 个 object 关键词"],
  "task_keywords": ["前 3 个 task 关键词"],
  "domain": "<题目领域>",
  "available_extra_tools": ["pubmed（仅医学领域）"],
  "current_paper_count": 0,
  "current_repo_count": 0,
  "prior_steps": [
    "arxiv: \"some query\" -> 12 results",
    "openalex: \"another query\" -> FAILED"
  ],
  "available_plan_queries": [
    "arxiv: \"planned query 1\"",
    "github: \"planned query 2\""
  ],
  "failed_tools_do_not_retry": ["crossref"],
  "step_number": 3,
  "max_steps": 8
}
```

**关键字段说明**：

- `prior_steps`：最近 8 步的 tool+query+结果数（或 FAILED 标记），防止 LLM 重复查询
- `available_plan_queries`：search_planner 阶段生成的候选查询，给 LLM 参考
- `failed_tools_do_not_retry`：本轮调用中失败的工具集合，禁止 LLM 再用
- `available_extra_tools`：领域专属工具（如医学领域的 pubmed）

### 2.3 _generate_reflection_query（反思策略生成器）

- **文件**：同上
- **函数**：`_generate_reflection_query(atoms, steps, papers)`（行 222–249）
- **用途**：Re3.9.4 新增的反思机制。当 LLM 想停止但论文相关度 < 30% 时，按三种策略生成新的查询，拒绝停止。
- **触发条件**：在 `search_agent_node` 中（行 488–515），当：
  - `step_idx < _MAX_STEPS - 2`
  - `all_papers` 非空
  - 相关论文比例 `_rel_count / _total < 0.3`
  - `_total < 15`

三种反思策略（**非 LLM 调用，纯规则**）：

```python
def _generate_reflection_query(atoms, steps, papers):
    """Re3.9.4: Generate a new search query using reflection strategies."""
    used_queries = {(s.get("tool"), s.get("query")) for s in steps if s.get("type") == "tool_call"}
    method = atoms.get("method") or []
    obj = atoms.get("object") or []
    domain = atoms.get("domain") or []

    # 策略 1: simplify — 只用 object 词简化查询
    if obj:
        q = " ".join(obj[:2])
        if ("arxiv", q) not in used_queries:
            return {"tool": "arxiv", "query": q, "strategy": "simplify:object_only"}

    # 策略 2: broaden — method + domain 扩大范围
    if domain and method:
        q = f"{method[0]} {domain[0]}"
        if ("crossref", q) not in used_queries:
            return {"tool": "crossref", "query": q, "strategy": "broaden:method+domain"}

    # 策略 3: synonym — method + application 同义词扩展
    if method:
        q = f"{method[0]} application"
        if ("openalex", q) not in used_queries:
            return {"tool": "openalex", "query": q, "strategy": "synonym:method+application"}

    return None  # 无可用反思策略
```

**反思步骤记录**（在 `search_steps` 中）：

```json
{
  "step": 5,
  "type": "reflection",
  "reason": "relevance 28%, simplify:object_only"
}
```

---

## 3. Re10 ReflectionCriticAgent（反思评审员）

> ⚠️ 该文件位于归档目录 `apps/api/tests/_archived_legacy_sessions/reflection_critic_agent.py`，但 `search_reflection_loop.py` 仍导入它。详见 [第 8 节](#8-重要提示归档状态告警)。

### 3.1 _SYSTEM（搜索结果反思 Agent）

- **文件**：[apps/api/tests/_archived_legacy_sessions/reflection_critic_agent.py](file:///g:/PaperAgent/apps/api/tests/_archived_legacy_sessions/reflection_critic_agent.py)
- **变量**：`_SYSTEM`（行 29–64）
- **用途**：根据上一轮搜索的真实结果，判断为什么没搜到好证据，下一轮应该怎么改。识别 9 类问题，输出 5 种 next_action。

```text
你是搜索结果反思 Agent。

你要根据上一轮搜索的真实结果，判断为什么没有搜到好证据，下一轮应该怎么改。

输入：
- topic
- topic_atoms
- executed_queries
- accepted_candidates
- noise_candidates
- empty_url_candidates
- failed_queries
- remaining_gaps

你必须识别：
- 查询过泛
- 查询缺对象词
- 查询只含方法词
- source 用错
- URL 缺失但论文可能真实
- 数据集缺口
- baseline 缺口
- repo 缺口
- 占位符 query

你必须输出 next_action：
- repair_query
- repair_url
- expand_from_good_paper
- switch_source
- stop_with_gap

不得把空 URL 直接判为假论文。
不得把 no_results 直接判为题目不可做。

只输出 JSON。
```

### 3.2 规则层 _rule_layer（LLM 失败时的反思兜底）

- **文件**：同上
- **函数**：`_rule_layer(obs)`（行 128–194）
- **用途**：当 LLM 不可用或返回错误时，基于 observations 字典生成确定性的反思诊断。该层只读 observations，不调用网络，不会幻觉领域。

规则层识别以下问题并生成对应的 `diagnosis` 项：

| 触发条件 | problem | next_action | root_cause |
|---|---|---|---|
| `obs.dataset_gap == True` | `dataset_gap` | `repair_query` | no dataset/citation surfaced from round 1 search |
| `obs.baseline_gap == True` | `baseline_gap` | `repair_query` | no baseline/citation surfaced from round 1 search |
| `obs.repo_gap == True` | `repo_gap` | `repair_query` | no github/repo surfaced from round 1 search |
| `obs.query_placeholder_leaks` 非空 | `query_placeholder` | `repair_query` | planner emitted unsubstituted placeholder; atom missing |
| `obs.noise_candidates` 非空 | `noise_candidate` | `switch_source` | off-topic hits; query too broad or source biased |
| `obs.empty_url_candidates` 非空 | `empty_url` | `repair_url` | OpenAlex returned no landing page; URL repairable |
| `obs.failed_queries` 非空 | `source_bias` | `switch_source` | adapter returned empty; try a different source |

**关键规则**（SOP §6.1）：空 URL 不等于假论文，必须走 `repair_url` 而不是判为噪声。

### 3.3 _PROBLEM_TO_ACTION 映射表

- **文件**：同上
- **变量**：`_PROBLEM_TO_ACTION`（行 114–125）

```python
_PROBLEM_TO_ACTION = {
    "dataset_gap": "repair_query",
    "baseline_gap": "repair_query",
    "repo_gap": "repair_query",
    "noise_candidate": "switch_source",
    "empty_url": "repair_url",
    "query_placeholder": "repair_query",
    "source_bias": "switch_source",
    "too_broad_query": "repair_query",
    "too_method_only_query": "repair_query",
    "topic_atom_missing": "stop_with_gap",
}
```

---

## 4. Re10 DomainScoutAgent（领域侦察）

> ⚠️ 该文件位于归档目录 `apps/api/tests/_archived_legacy_sessions/domain_scout_agent.py`，但 `search_reflection_loop.py` 仍导入它。

### 4.1 _SYSTEM（领域检索侦察 Agent）

- **文件**：[apps/api/tests/_archived_legacy_sessions/domain_scout_agent.py](file:///g:/PaperAgent/apps/api/tests/_archived_legacy_sessions/domain_scout_agent.py)
- **变量**：`_SYSTEM`（行 122–148）
- **用途**：LLM-only（无网络调用）侦察 agent，产出领域关键词矩阵 + `must_search` / `avoid_search` 列表给 SearchPlanner 使用。不评判题目、不生成工作包、不收敛到单一领域。

```text
你是工科学位论文选题系统中的领域检索侦察 Agent。

你的任务不是给最终结论，而是找出这个题目所在领域应该搜索哪些关键词、baseline、数据集、repo、综述词和避免词。

输入：
- 题目
- 已解析 topic_atoms
- 上一轮正确候选
- 上一轮错误候选
- 上一轮失败 query

你必须：
1. 给出中文和英文关键词。
2. 给出 method/object/task/scenario 四类词。
3. 给出 baseline 搜索词。
4. 给出 dataset 搜索词。
5. 给出 repo 搜索词。
6. 从错误候选中总结 avoid_search。
7. 从正确候选中总结 expansion_terms。

你不得：
1. 直接判定题目可不可做。
2. 直接生成工作包。
3. 只给 YOLO/UNet 这种方法词。
4. 用单一领域规则把题目打到 CV 检测路线。

只输出 JSON。
```

### 4.2 _build_user_prompt（领域侦察 user prompt）

- **文件**：同上
- **函数**：`_build_user_prompt(topic, topic_atoms, history)`（行 151–158）
- **用途**：构造 user prompt，包含 topic / topic_atoms / 上一轮成功/失败历史。

```json
{
  "topic": "<题目>",
  "topic_atoms": { /* 结构化 atoms */ },
  "previous_success": ["上一轮正确候选"],
  "previous_noise": ["上一轮错误候选"],
  "previous_failed_queries": ["上一轮失败 query"]
}
```

**离线兜底**：当 LLM 失败或 atoms 为空时，`_offline_must_search(topic_atoms)` 会从 topic_atoms 的 task / object 轴自动生成 `<atom> benchmark` 形式的 must_search 查询。

---

## 5. Re1.2 定向修复规划器（targeted_repair）

### 5.1 SYSTEM（修复策略规划器）

- **文件**：[apps/api/app/services/agents/prompts/re12_repair.py](file:///g:/PaperAgent/apps/api/app/services/agents/prompts/re12_repair.py)
- **变量**：`SYSTEM`（行 22–55）
- **用途**：当 evidence 不足时，针对单一失败切片生成修复轮搜索计划。输出 schema 与 search_planner 一致，可直接覆盖 `state["search_plan"]`。Re3.0 引入 strategy switching。

```text
You are a targeted research-gap repair planner. The last broad/focused
search round came back short on one evidence slice. Re-plan ONLY that slice.

Available tools:
- arxiv:    academic papers (use for paper_gap and baseline_gap)
- openalex: academic papers / reviews; good for dataset / baseline gaps
- crossref: DOI / journal papers; use for target paper you have DOI/title for
- web:      dataset pages / project pages / benchmarks (url_repair +
            metadata_mismatch_repair)
- github:   official repos (repo_gap_repair); ONLY when you can name a paper or
           method to disambiguate

Re3.0 Strategy switching (choose one):
- "synonym": Replace keywords with synonyms or related terms
    (e.g. "YOLO crop" → "object detection agriculture" → "plant disease detection")
- "broaden": Remove qualifiers and search more broadly
    (e.g. "YOLO crop recognition" → "YOLO" or "crop detection")
- "switch_tool": If a specific adapter returned 0 results, try a different tool
    for the same query (e.g. OpenAlex 429 → use Crossref or arxiv)

Hard rules:
1. Output a SINGLE JSON object with EXACTLY these top-level keys:
     "queries", "rounds", "negative_feedback", "strategy".
2. "rounds" MUST be ["repair"] (this is a repair round, not a broad sweep).
3. "strategy" MUST be one of: "synonym", "broaden", "switch_tool".
4. Every query MUST include: tool, query, why, expected_evidence, stop_condition.
5. `why` MUST explicitly name the prior failed query it replaces and the
   gap-closing strategy.
6. `stop_condition` MUST be stricter than the failing query's condition so
   we fail fast if the gap truly does not exist.
7. NEVER repeat any query from `prior_queries` (case-insensitive match). The
   LLM must rotate tools, keywords, or language.
8. NO prose outside the JSON object.
```

### 5.2 build() user prompt 模板

- **函数**：`build(topic, gaps, rejected_titles, prior_queries)`（行 58–82）
- **用途**：组装修复 user prompt，传入 quantitative gaps、rejected titles、prior queries。

```text
Topic: {topic}

Quantitative gaps in current evidence:
{gaps_json}

Titles / candidates that were REJECTED in the last round
(unrelated / weak / off-topic):
{rejected_titles_json}

Queries that were ALREADY TRIED in earlier rounds — DO NOT
repeat any of these (case-insensitive):
{prior_queries_json}

Return a JSON object:
  {"queries": [ {tool, query, why, expected_evidence, stop_condition}, ... ],
   "rounds": ["repair"],
   "negative_feedback": "<why the prior round failed + how this closes the gap>",
   "strategy": "synonym|broaden|switch_tool"}
```

**调用方**：[apps/api/app/services/agents/graph/nodes/targeted_repair.py](file:///g:/PaperAgent/apps/api/app/services/agents/graph/nodes/targeted_repair.py) 第 209 行 `P.build(topic, gaps, rejected_titles, prior_queries)`。

**策略推断**（`_infer_strategy`，行 83–95）：
- Round 0 → `"synonym"`（换同义词）
- Round 1+ 且无失败 adapter → `"broaden"`（扩大范围）
- 任意 round 且有失败 adapter → `"switch_tool"`（换工具）

---

## 6. Re08 Gap Repair Planner（缺口修复规划器）

> 该 prompt 与 Re1.2 的修复规划器类似，但针对 Re08 的命名 gap_reasons。

- **文件**：[apps/api/app/services/agents/prompts/gap_repair_planner.py](file:///g:/PaperAgent/apps/api/app/services/agents/prompts/gap_repair_planner.py)
- **变量**：`GAP_REPAIR_PLANNER_SYSTEM`（行 20–75）

```text
You are the gap-repair planner for an autonomous
literature-survey agent.  Your job is to look at the **named gap reasons**
of a single case and generate 1-3 targeted queries that *plausibly close the
gap* — not generic re-searches.

===================== NON-NEGOTIABLE RULES =====================
1. [OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences.
2. For EACH gap reason, output AT MOST 3 queries.  If a gap has 5+ plausible
   queries, **rank them** by expected yield and emit only the top 3.
3. Every query MUST mix BOTH a Chinese keyword and an English keyword
   when the topic is bilingual (zh topic atoms present).  Otherwise English
   only is acceptable.
4. NEVER emit a query like "deep learning" or "YOLO" alone — every query
   must carry at least one object-word AND one task-word (or scenario-word).
5. For dataset gaps, the query MUST include the object word from the topic
   (NOT a hardcoded example) AND a data-source word
   (dataset / benchmark / corpus / repository / collection).
6. For baseline gaps, the query MUST include the method word AND the object
   word, AND at least one of {benchmark, SOTA, comparison, proposed}.
7. For attack-defense axis gaps, the query MUST include at least one of
   {attack, defense, adversarial, robustness, mitigation, patch, evasion}.
8. For scenario axis gaps, the query MUST include a sensor / environment /
   operation-mode word (UAV, satellite, night, fog, indoor, outdoor,
   industrial, edge device, mobile).
9. Queries targeting GitHub / HuggingFace MUST include the resource type
   word (implementation / repo / weights / dataset).
10. If the topic has NO clear repair route (e.g. a Chinese-only thesis on
    an obscure industrial process), output `repair_plan: []` and explain
    why in `unrepairable_reason`.

===================== INPUT =====================
TOPIC: {topic}

TOPIC_ATOMS: {topic_atoms_json}

CURRENT_STATUS: {current_status}

GAP_REASONS: {gap_reasons_json}

EXISTING_CANDIDATE_SUMMARY (one-line per candidate):
{candidate_summary}

===================== OUTPUT (strict JSON) =====================
{{
  "repair_plan": [
    {{
      "gap": "<verbatim gap reason from GAP_REASONS>",
      "target_role": "dataset | repo | baseline | parallel_paper | core_paper",
      "queries": [
        {{"query": "<search string>", "tool": "arxiv | openalex | crossref | github | huggingface | semantic_scholar | web", "why": "<one sentence: which atom this targets>"}}
      ]
    }}
  ],
  "unrepairable_reason": "<if repair_plan is empty, explain in one sentence>"
}}
```

**与 Re1.2 的区别**：
- Re08 版本接受命名 gap_reasons 列表，针对每条 gap 生成查询
- Re1.2 版本接受 quantitative gaps dict（数字 + failed adapters），输出 strategy
- Re08 强调中英文混合查询，Re1.2 强调 strategy switching

---

## 7. 修复循环触发条件

修复循环在 `research_graph.py` 的多个路由函数中触发：

### 7.1 quality_gate 路由（`_route_after_quality_gate`，行 140–182）

| 条件 | 路由 | 说明 |
|---|---|---|
| 论文数 < 3 且修复未耗尽 | `targeted_repair` → `paper_retriever` | 修复回路（最多 `MAX_REPAIR_ROUNDS=2` 次） |
| 第一轮但不够 | `citation_expander` → `verify` → `quality_gate` | 引用扩展回路（1 次） |
| 论文数 >= 3 或修复耗尽 | `dataset_repo_extractor` | 继续下一阶段 |
| 严重阻塞 | `final_recommendation` | 直接结束 |

### 7.2 low_bar_review 路由（`_route_after_review`，行 185–213）

| 条件 | 路由 | 说明 |
|---|---|---|
| verdict != pass 且证据不足 | `targeted_repair` → `paper_retriever` | 低门槛修复回路 |
| verdict == ready | `optimization_advisor` | 继续 |
| blocked | `final_recommendation` | 结束 |

### 7.3 devils_advocate 路由（`_route_after_devils`，行 232–264）

| 条件 | 路由 | 说明 |
|---|---|---|
| ACCEPT | `human_gate` | 通过 |
| MINOR_REVISION 且 revisions < `MAX_NARRATIVE_REVISIONS=2` | `narrative_builder` | 叙事修订回路 |
| MINOR_REVISION 且 revisions >= MAX | `human_gate` | 强制通过 |
| BLOCK 且 block_count <= `MAX_BLOCK_RETRIES=1` 且 feasibility 允许 | `optimization_advisor` | 优化回路 |
| BLOCK 其他情况 | `human_gate` | 强制人工 |

### 7.4 ReACT 循环内部反思触发（search_agent.py 行 488–515）

```python
# Re3.9.4: Relevance-aware stop — if papers have low relevance, try reflection
if thought.get("action") == "stop":
    if _atoms_for_rel and all_papers and step_idx < _MAX_STEPS - 2:
        _rel_count = _count_relevant_papers(all_papers, _atoms_for_rel)
        _total = len(all_papers)
        _ratio = _rel_count / _total if _total > 0 else 1.0
        if _ratio < 0.3 and _total < 15:
            _reflection = _generate_reflection_query(_atoms_for_rel, steps, all_papers)
            if _reflection:
                # 拒绝 stop，继续搜索
                steps.append({
                    "step": step_idx,
                    "type": "reflection",
                    "reason": f"relevance {_ratio:.0%}, {_reflection.get('strategy','')}",
                })
                thought = {
                    "action": "search",
                    "tool": _reflection.get("tool", "arxiv"),
                    "query": _reflection.get("query", ""),
                    "reason": f"reflection: low relevance ({_ratio:.0%})",
                }
```

---

## 8. 重要提示：归档状态告警

### 8.1 导入断裂风险

`apps/api/app/services/agents/search_reflection_loop.py` 第 36、38 行：

```python
from .domain_scout_agent import run_domain_scout       # 行 36
from .reflection_critic_agent import run_reflection_critic  # 行 38
```

这两个文件**不在** `apps/api/app/services/agents/` 目录中，仅在 `apps/api/tests/_archived_legacy_sessions/` 下存档：

| 导入名 | 实际位置 |
|---|---|
| `domain_scout_agent` | `apps/api/tests/_archived_legacy_sessions/domain_scout_agent.py` |
| `reflection_critic_agent` | `apps/api/tests/_archived_legacy_sessions/reflection_critic_agent.py` |

### 8.2 影响

- 如果 `search_reflection_loop.py` 被生产路径加载，会触发 `ModuleNotFoundError`
- **当前生产主路径是 Re3.0 ReACT 搜索 agent**（`search_agent.py`），不依赖 `search_reflection_loop.py`
- `search_reflection_loop.py` 的反思 prompt（第 3、4 节）目前**仅作参考**，实际运行时不会触发

### 8.3 建议

1. 确认 `search_reflection_loop.py` 是否仍被生产路径调用
2. 若是，需要把归档的 `reflection_critic_agent.py` 和 `domain_scout_agent.py` 恢复到 active agents 目录
3. 若否，建议删除 `search_reflection_loop.py` 以避免误导

---

## 文档说明

- 本文档聚焦 **React 循环 + Reflection 反思 + Repair 修复** 三类提示词
- 各 Agent 阶段的主线提示词见 [Prompts_AgentStages.md](file:///g:/PaperAgent/docs/Prompts_AgentStages.md)
- 节点编排与状态流转见 [docs/agent_architecture.md](file:///g:/PaperAgent/docs/agent_architecture.md)
- 反思循环的 SOP 定义见 `Plan/Arch/PaperAgent_Re3.x_收官报告.md` 和 Re10 相关 SOP
