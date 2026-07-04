# PaperAgent Re10 Multi-Loop Reflection 搜索收口 SOP

## 0. 背景判断

Re09 已经证明 fresh online 检索可以跑起来，但它没有完成“可用搜索系统”的目标。

Re09 的主要问题不是“没有搜索”，而是搜索范式还停留在单轮/半单轮：

- 它从 0 重建候选池，导致 Re08 已经有效的 baseline / parallel / dataset 候选丢失。
- 它执行了 repair query，但没有把错误结果反馈给下一轮 planner。
- 它有 52 个含 `X` 的失败 query，说明 query 修复没有闭环。
- 它有大量 OpenAlex 空 URL 结果，但空 URL 不应该直接等价为 fail，应该触发 URL repair。
- 它没有让专门的“宽泛领域关键词搜索 Agent”先调研领域搜索词，再交给后续 Agent 审查和搜索。
- 它没有强 Trace 约束，报告能说明“跑过”，但不足以复盘每轮为什么搜偏、怎么修正。

因此 Re10 是搜索功能的收口阶段。目标不是再新增一堆松散功能，而是把检索改成：

```text
宽泛领域调研 → 多源搜索 → 结果观察 → 错误反思 → 查询修复 → 再搜索 → 证据核验 → 增量合并 → 最终候选包
```

## 1. Re10 总目标

Re10 必须完成“多轮反思检索闭环”，并把搜索能力在本阶段收口。

完成后，系统应能做到：

1. 输入一个工科毕业题目。
2. 先由领域关键词 Agent 宽泛查找该领域应该搜什么词、常见 baseline、常见 dataset、常见 repo。
3. 后续检索 Agent 按关键词矩阵执行多源检索。
4. 如果第一轮搜到噪声、空 URL、无数据集、无 baseline、占位符 query，则进入 Reflection Loop。
5. Reflection Agent 根据错误结果生成下一轮 action。
6. 至多 3 轮后停止，输出可解释的候选资源包。
7. 最终报告必须能追踪每条候选来自哪一轮、哪条 query、哪个工具、为什么保留、为什么降级。

## 2. 非目标

本阶段不做：

- 不做 UI 大改。
- 不做完整知识图谱。
- 不做 HumanGate。
- 不做论文写作。
- 不做工作包推荐大改。
- 不做 100 题全量最终评估。

本阶段只解决搜索闭环、证据 Trace、候选合并和结果可信度。

## 3. 核心架构

### 3.1 新范式：Reflection Search Loop

Re10 采用轻量 ReAct + Reflection 混合范式。

```text
Topic
  ↓
DomainScoutAgent
  ↓
SearchPlannerAgent
  ↓
SearchExecutor
  ↓
ObservationBuilder
  ↓
ReflectionCriticAgent
  ↓
QueryRepairAgent / URLRepairAgent / CitationExpandAgent
  ↓
CandidateVerifier
  ↓
EvidenceMerger
  ↓
StopController
```

每一轮必须产出 Trace。Trace 是 Re10 的一等产物，不是附属日志。

### 3.2 Agent 职责

#### DomainScoutAgent

用途：

宽泛网络搜索该领域“应该搜什么”。

输入：

```json
{
  "topic": "...",
  "topic_atoms": {},
  "previous_noise": [],
  "previous_success": []
}
```

输出：

```json
{
  "domain_keywords": {
    "zh": [],
    "en": [],
    "method": [],
    "object": [],
    "task": [],
    "scenario": [],
    "dataset_terms": [],
    "baseline_terms": [],
    "repo_terms": []
  },
  "must_search": [],
  "avoid_search": [],
  "known_baseline_families": [],
  "known_dataset_families": [],
  "search_notes": ""
}
```

要求：

- 可以使用宽泛 web / OpenAlex / GitHub 搜索。
- 必须记录它参考了哪些页面、哪些 query、哪些结果。
- 必须允许从错误候选中学习 `avoid_search`。
- 必须允许从正确论文中学习扩展词。

该 Agent 不应该：

- 直接给最终结论。
- 直接判定题目可不可做。
- 直接生成工作包。
- 把一个领域强行映射到 CV 检测。

#### SearchPlannerAgent

用途：

根据 DomainScout 输出和当前缺口生成本轮检索计划。

输出：

```json
{
  "round": 1,
  "queries": [
    {
      "query": "...",
      "tool": "arxiv | openalex | crossref | github | semantic_scholar | web",
      "target_role": "core_paper | baseline | parallel_paper | dataset | repo | survey",
      "why": "...",
      "expected_signal": "title | abstract | citation | dataset_name | repo_readme"
    }
  ]
}
```

要求：

- 每轮 query 必须覆盖 paper / dataset / repo / baseline 至少三类。
- 第二轮以后必须引用上一轮观察结果。
- 不允许输出 `X`、`{object}`、`{scenario}`、空 query。
- 如果缺词，必须返回 `needs_query_repair`，而不是生成假 query。

#### SearchExecutor

用途：

只负责执行 query 和记录工具结果，不做最终判断。

要求：

- 每条 query 必须记录 `tool`、`query`、`started_at`、`ended_at`、`status`、`result_count`、`error`。
- 空结果不是 fail，只是 `no_results` observation。
- adapter 错误必须记录，不得静默吞掉。

#### ObservationBuilder

用途：

把搜索结果整理成可反思的观察。

输出：

```json
{
  "round": 1,
  "observations": {
    "good_candidates": [],
    "noise_candidates": [],
    "empty_url_candidates": [],
    "empty_query_results": [],
    "dataset_gap": true,
    "baseline_gap": true,
    "repo_gap": true,
    "query_placeholder_leaks": [],
    "useful_terms_discovered": []
  }
}
```

#### ReflectionCriticAgent

用途：

分析上一轮为什么搜偏，以及下一轮该怎么改。

输出：

```json
{
  "round": 1,
  "diagnosis": [
    {
      "problem": "noise | empty_url | dataset_gap | baseline_gap | repo_gap | query_placeholder | source_bias",
      "evidence": [],
      "root_cause": "",
      "next_action": "repair_query | repair_url | expand_citation | switch_source | stop"
    }
  ],
  "next_round_focus": []
}
```

该 Agent 不应该：

- 把空 URL 直接判为错误论文。
- 把 no_results 直接判为不可做。
- 不看上一轮成功候选就重新泛搜。

#### QueryRepairAgent

用途：

修复坏 query，包括 `X` 占位符、过泛 query、工具不匹配 query。

输入：

```json
{
  "bad_query": "X dynamic scene dataset",
  "topic_atoms": {},
  "domain_keywords": {},
  "noise_reason": "placeholder_leak"
}
```

输出：

```json
{
  "status": "repaired | needs_clarification | drop",
  "repaired_queries": [],
  "reason": ""
}
```

规则：

- 能补就补。
- 补不了就 drop，不扣大分。
- 不能把 `X` 直接发给检索工具。

#### URLRepairAgent

用途：

修复真实论文的空 URL。

空 URL 状态机：

```text
candidate_url_empty
  → verify_title_exists
  → find_url_by_arxiv_or_doi_or_openalex_or_web
  → url_repaired | url_unavailable_but_verified | candidate_unverified
```

规则：

- 如果论文真实但 URL 空，不得直接 fail。
- 先用标题、作者、年份、DOI、OpenAlex ID 查找。
- 找到 DOI 但没有网页 URL，也可标 `url_unavailable_but_verified`。
- 只有论文真实性无法确认时才进入 `candidate_unverified`。

#### CitationExpandAgent

用途：

从已确认正确的论文向外扩展：

- referenced works
- cited by
- official code
- dataset mentioned
- benchmark mentioned

要求：

- 只对 verified / metadata_repaired / likely_relevant 的论文做扩展。
- 每篇种子论文最多扩展 5 条，避免爆炸。
- 扩展结果必须保留 `source_candidate_id`。

#### EvidenceMerger

用途：

增量合并，不丢旧证据。

Re10 必须修复 Re09 的核心问题：不能从 0 重建 candidate_pool。

合并策略：

```text
base_pool = Re08 有效候选 + Re09 fresh 候选 + Re10 loop 新候选
```

冲突策略：

- 同 DOI / arXiv ID / normalized title 视为同一候选。
- URL 空的候选可以被 URL 完整候选修复。
- low-confidence 不覆盖 high-confidence。
- off_topic 不删除原候选，只进入 noise / rejected bucket。

## 4. 必须新增/修改的模块

### 4.1 新增 `search_reflection_loop.py`

路径：

`apps/api/app/services/agents/search_reflection_loop.py`

职责：

- 管理最多 3 轮搜索。
- 保存每轮 Trace。
- 调用 DomainScout / Planner / Executor / Observer / Critic / Repair / Verify / Merge。

核心接口：

```python
async def run_search_reflection_loop(
    topic: str,
    *,
    seed_candidates: dict,
    max_rounds: int = 3,
    llm_client,
    retrieval_clients: dict,
) -> dict:
    ...
```

返回：

```json
{
  "topic": "...",
  "final_candidate_pool": {},
  "rounds": [],
  "trace_path": "...",
  "stop_reason": "sufficient_evidence | max_rounds | no_new_signal | blocked",
  "summary": {}
}
```

### 4.2 新增 `domain_scout_agent.py`

路径：

`apps/api/app/services/agents/domain_scout_agent.py`

职责：

- 宽泛搜索领域关键词。
- 接收上一轮错误结果反馈。
- 形成 `must_search` / `avoid_search`。

该模块不应该：

- 直接 eval 题目。
- 直接写入最终候选池。
- 靠硬编码领域词表替代搜索。

### 4.3 新增 `reflection_critic_agent.py`

路径：

`apps/api/app/services/agents/reflection_critic_agent.py`

职责：

- 分析搜索失败原因。
- 输出下一轮 action。

必须识别以下问题类型：

- `noise_candidate`
- `empty_url`
- `query_placeholder`
- `dataset_gap`
- `repo_gap`
- `baseline_gap`
- `source_bias`
- `too_broad_query`
- `too_method_only_query`
- `topic_atom_missing`

### 4.4 新增 `query_repair_agent.py`

路径：

`apps/api/app/services/agents/query_repair_agent.py`

职责：

- 修复 `X` / `{}` / 过泛 / 工具不匹配 query。
- 输出修复后的 query 或 drop。

硬规则：

- 不允许任何包含 bare `X` 的 query 进入 adapter。
- 不允许任何包含 `{` 或 `}` 的 query 进入 adapter。
- 被修复的 query 必须记录原始 query。

### 4.5 新增 `url_repair_agent.py`

路径：

`apps/api/app/services/agents/url_repair_agent.py`

职责：

- 对空 URL 候选做真实性核验和 URL 补全。

接口：

```python
async def repair_candidate_url(candidate: dict, *, retrieval_clients: dict) -> dict:
    ...
```

输出状态：

- `url_repaired`
- `url_unavailable_but_verified`
- `candidate_unverified`
- `not_enough_metadata`

### 4.6 修改 `run_balanced40_fresh_re09.py`

不要继续在 Re10 里直接用它作为主入口。

可以保留作为历史 runner，但 Re10 新建：

`apps/api/scripts/run_balanced40_reflection_re10.py`

要求：

- 读取 Re08 / Re09 有效候选作为 seed。
- 对 fail / weak / regression case 执行 reflection loop。
- 对 pass case 至少保留原有证据，不允许因为没跑搜索变 fail。

## 5. Trace 设计

Re10 必须强制输出 Trace。

每个 case 输出：

```text
tmp_re04_eval/balanced40_re10_reflection/traces/<case_id>.json
```

Trace Schema：

```json
{
  "case_id": "...",
  "topic": "...",
  "seed_sources": {
    "re08_candidates_n": 0,
    "re09_candidates_n": 0
  },
  "rounds": [
    {
      "round": 1,
      "agent": "DomainScoutAgent | SearchPlannerAgent | SearchExecutor | ObservationBuilder | ReflectionCriticAgent",
      "input_summary": {},
      "actions": [
        {
          "type": "search | verify | repair_query | repair_url | expand_citation",
          "tool": "openalex",
          "query": "...",
          "status": "success | no_results | error | skipped",
          "result_count": 0,
          "candidate_ids": [],
          "error": ""
        }
      ],
      "observations": {},
      "reflection": {},
      "new_candidates_n": 0,
      "accepted_candidates_n": 0,
      "rejected_candidates_n": 0,
      "url_repair_n": 0,
      "query_repair_n": 0
    }
  ],
  "final": {
    "stop_reason": "",
    "paper_n": 0,
    "baseline_n": 0,
    "parallel_n": 0,
    "dataset_n": 0,
    "repo_n": 0,
    "remaining_gaps": []
  }
}
```

Trace 验收要求：

- 每个 fail / weak / regression case 必须有至少 2 轮 Trace。
- 每轮必须有 action 和 observation。
- 如果有失败 query，下一轮必须出现对应 reflection。
- 如果有空 URL，必须出现 URL repair action 或说明为什么跳过。
- 如果有 `X` query，必须出现 query repair action，且不得进入 adapter。

## 6. 状态机与评分逻辑

### 6.1 空 URL 不直接 fail

候选状态：

```text
url_empty
  → url_repair_pending
  → url_repaired
  → url_unavailable_but_verified
  → candidate_unverified
```

判定：

- `url_repaired`：可作为正常证据。
- `url_unavailable_but_verified`：可作为候选证据，但 UI 标“URL 待补”。
- `candidate_unverified`：不能进入核心证据，只进候选池。

### 6.2 占位符 query 不直接扣大分

query 状态：

```text
placeholder_detected
  → query_repair_pending
  → query_repaired
  → query_dropped
```

判定：

- `query_repaired`：进入下一轮搜索。
- `query_dropped`：不扣题目分，只计入 planner 质量问题。
- 如果同一 case 出现 3 次以上 placeholder，判定 planner 失败，需要修 topic atoms。

### 6.3 错误论文用于反思，不只是过滤

错误候选状态：

```text
noise_candidate
  → noise_reason
  → avoid_terms / source_bias / query_too_broad
  → next_round_query_update
```

示例：

- 搜到医学 COVID 论文：说明 query 过泛或对象词缺失。
- 搜到 Survey Motivation 论文：说明 survey 关键词被误用，必须加对象词限定。
- 搜到纯材料统计论文：可能是相关背景，不一定删除；应转成 `background_proxy`。

## 7. StopController

最多 3 轮。

停止条件：

- `sufficient_evidence`
  - 至少 4 篇相关论文。
  - 至少 1 个 baseline 或 baseline family。
  - 至少 1 条 dataset route 或明确 proxy dataset route。
  - 至少 1 个 repo 或明确“无官方 repo 但可复现路线”。

- `no_new_signal`
  - 连续 2 轮新增 accepted candidates < 2。

- `max_rounds`
  - 已到 3 轮。

- `blocked`
  - 所有 adapter 错误或 LLM 不可用。

不得因为第一轮没有 dataset / URL / repo 直接 fail。

## 8. Re10 测试集

Re10 不跑 100 题。跑 Balanced40，但重点看 regression 修复。

必测：

### 8.1 Re09 Regression Cases

从 Re09 中挑 10 个 Re08 pass → Re09 fail 的 case。

验收：

- Re10 不得从 0 开始。
- 必须保留 Re08 有效候选。
- 状态不得低于 Re08，除非 Re08 候选被证明为错误且报告逐条说明。

### 8.2 Re09 Fail Cases

必测：

- `ENG-THESIS-043`
- `ENG-THESIS-048`
- `ENG-THESIS-075`

验收：

- 每个 case 至少 2 轮 Trace。
- 每个 case 至少一次 ReflectionCritic 输出。
- 每个 case 必须执行 URL repair 或 query repair 中至少一类。

### 8.3 占位符 Query Case

构造或复用含 `X dynamic scene dataset` 的记录。

验收：

- 不得进入 adapter。
- 必须被 QueryRepairAgent 修复或 drop。
- Trace 中必须记录修复原因。

### 8.4 空 URL Case

使用 OpenAlex 返回空 URL 的候选。

验收：

- 不得直接 fail。
- 必须进入 URLRepairAgent。
- 至少尝试 arXiv / DOI / OpenAlex landing page / web title search 中两种。

### 8.5 错误论文反馈 Case

构造噪声论文：

- survey motivation / German open-ended survey
- COVID transmission
- unrelated astronomy

验收：

- 不得进入核心证据。
- 必须进入 noise bucket。
- 下一轮 query 必须加入 avoid_terms 或更强对象词限定。

## 9. 验收标准

Re10 通过必须同时满足：

### 9.1 搜索收口指标

- Balanced40 `pass + weak >= Re08 pass + weak`，即不得低于 92.5%。
- Re09 的 24 个 pass regression case 不得继续全 fail。
- Re09 的 3 个 fail 至少 2 个提升到 weak，或报告中给出真实不可补证 Trace。

### 9.2 Trace 指标

- fail / weak / regression case Trace 覆盖率 100%。
- 每个 Trace 至少 2 轮。
- 每个 Trace 至少包含 search、observe、reflect、repair/next_action。
- Trace 中不得出现未解释的 adapter error。

### 9.3 Query 质量指标

- 进入 adapter 的 query 中 `X` / `{}` 占位符数量 = 0。
- 被修复或 drop 的 placeholder query 必须有 Trace。
- 第二轮 query 必须引用第一轮观察结果。

### 9.4 URL 修复指标

- 空 URL 候选不得直接 fail。
- 空 URL 候选必须有 `url_status`。
- `url_empty` 候选中至少 70% 经过 URLRepairAgent。

### 9.5 候选合并指标

- Re08 有效候选不得被无理由丢弃。
- Re10 final pool 必须记录候选来源：
  - `source_run = re08 | re09 | re10_round_1 | re10_round_2 | re10_round_3`
- 同名 / 同 DOI / 同 arXiv 候选必须 dedup。

### 9.6 报告诚实指标

完工报告必须包含：

- Re08 → Re09 → Re10 状态对比。
- 每类问题的修复统计。
- Trace 覆盖率。
- URL repair 统计。
- Query repair 统计。
- 仍未解决的 case 和明确原因。

## 10. Prompt 规范

### 10.1 DomainScoutAgent Prompt

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

### 10.2 ReflectionCriticAgent Prompt

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
```

### 10.3 QueryRepairAgent Prompt

```text
你是 query 修复 Agent。

输入一个坏 query，以及题目的 topic_atoms 和领域关键词。
你的任务是把坏 query 修成可执行、可搜索、含对象词/任务词/资源词的 query。

规则：
- 如果 query 含 X 或 {object}/{scenario}，必须替换或 drop。
- 如果无法替换，返回 needs_clarification 或 drop。
- 数据集 query 必须含 dataset/benchmark/challenge/corpus/数据集 中至少一个。
- repo query 必须含 github/code/implementation/repo 中至少一个。
- paper query 必须含对象词 + 任务词，不能只含方法词。

只输出 JSON。
```

### 10.4 URLRepairAgent Prompt

```text
你是候选论文 URL 修复 Agent。

输入一个候选资源，它可能有标题、作者、年份、摘要、DOI、OpenAlex ID，但 URL 为空。

你的任务：
1. 先判断论文是否真实存在。
2. 如果真实，尝试找到 arXiv / DOI / OpenAlex landing page / publisher page / GitHub 引用页。
3. 如果找不到 URL，但论文可由 DOI/OpenAlex 确认，输出 url_unavailable_but_verified。
4. 只有真实性无法确认时，才输出 candidate_unverified。

不得因为 URL 为空直接判 fail。
```

## 11. 报告产物

必须产出：

- `G:\PaperAgent\Plan\PaperAgent_Re10_完工报告.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_Balanced40_逐论文审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_Balanced40_逐论文审计.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re10_Balanced40_候选论文.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re10_SearchTrace_索引.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_ReflectionLoop_统计.json`

Trace 原始文件：

- `G:\PaperAgent\tmp_re04_eval\balanced40_re10_reflection\traces\*.json`

## 12. 执行顺序

1. 修复 Re09 runner 的候选池从 0 重建问题，改为增量合并。
2. 新增 TraceLedger。
3. 新增 DomainScoutAgent。
4. 新增 ReflectionCriticAgent。
5. 新增 QueryRepairAgent。
6. 新增 URLRepairAgent。
7. 新增 SearchReflectionLoop。
8. 接入 Balanced40 Re10 runner。
9. 对 3 fail + 13 weak + 10 regression case 跑多轮。
10. 生成报告和 Trace 索引。
11. 跑 validator。

## 13. Validator 要求

新增：

`apps/api/scripts/validate_re10_reflection_search.py`

必须校验：

- Trace 文件数量。
- 每个重点 case 是否至少 2 轮。
- 是否存在进入 adapter 的 `X` / `{}` query。
- 是否存在空 URL 候选未进入 URL repair。
- Re08 有效候选是否被无理由丢弃。
- Re10 pass+weak 是否不低于 Re08。
- Re09 regression 是否恢复。
- 完工报告是否包含 Trace 覆盖率和状态对比。

任何一项失败，Re10 不得验收。

## 14. 最终边界

Re10 是搜索阶段收口。

如果 Re10 仍无法达到验收标准，不再继续“微调搜索规则”。下一步应改为：

- 明确列出无法自动补齐的领域。
- 进入人工证据提交 / 手动 URL 补充 / 文献库维护。
- 或把数据集 / repo 检索交给专用外部数据源。

也就是说，Re10 之后搜索阶段应该结束，系统进入“基于候选资源做毕业方向推荐”的阶段。
