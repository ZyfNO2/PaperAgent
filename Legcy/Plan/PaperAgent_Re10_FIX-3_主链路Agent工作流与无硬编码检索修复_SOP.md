# PaperAgent Re10 FIX-3：主链路 Agent 工作流与无硬编码检索修复 SOP

## 0. 本轮定位

当前问题不是某一个候选标题的问题，而是主链路存在“泛化检索 + 宽松接收 + 审计误判”的系统性污染。

症状是：不同领域题目会共享同一批热门工程、通用论文或固定 fallback，导致 case-level audit 看似通过，但候选与题目轴并不匹配。

本轮目标不是写黑名单，而是重建主链路规则：

```text
题目解析
  -> 检索计划
  -> 多源召回
  -> 候选验真与主题轴匹配
  -> 证据分层
  -> 审计与报告
```

只有这条主链路合格，才允许进入下一阶段。

## 1. 禁止事项

执行者必须遵守以下禁止事项。违反任意一条，本轮不允许验收。

### 1.1 禁止硬编码候选过滤

不允许：

- 用具体论文名、repo 名、数据集名写黑名单。
- 用 `if title == xxx: reject` 处理噪声。
- 用 `STRONG_NOISE_TOKENS` 这类静态噪声词表作为主过滤逻辑。
- 在 validator 中写某几个固定标题的特判。

允许：

- 使用“批内重复污染检测”。
- 使用“主题轴匹配不足”。
- 使用“source role 不匹配”。
- 使用“候选元数据不一致”。
- 使用“候选只命中通用方法词但未命中对象/任务”的通用规则。

### 1.2 禁止固定领域路线

不允许：

- `if "检测" in topic -> CV 检测路线`
- `if "深度学习" in topic -> YOLO/U-Net`
- `if "三维" in topic -> SLAM/点云`
- `if "问答" in topic -> LLM`

允许：

- 让 TopicParseAgent 输出多个候选领域路线。
- 每条路线必须有 method / object / task / scenario 轴。
- 如果轴缺失，标记 `needs_axis_clarification`，不要自动补固定路线。

### 1.3 禁止固定 fallback

不允许：

- 固定 repo fallback。
- 固定 baseline fallback。
- 固定 dataset fallback。
- LLM 失败后直接套用某个模板候选。

允许：

- LLM 失败后保留空结果并进入 query repair。
- 使用 topic atoms 生成轴绑定查询。
- 保留 fallback 的 trace，但 fallback 不能让 case 直接通过。

## 2. 主链路 Agent 设计

### 2.1 TopicParseAgent

职责：

- 把题目拆成结构化 topic atoms。
- 输出多条可能路线，不做最终判断。

输入：

```json
{
  "topic": "用户输入题目"
}
```

输出：

```json
{
  "method_terms": [],
  "object_terms": [],
  "task_terms": [],
  "scenario_terms": [],
  "metric_terms": [],
  "candidate_domain_routes": [
    {
      "route_id": "r1",
      "method": [],
      "object": [],
      "task": [],
      "scenario": [],
      "why_possible": "",
      "missing_axis": []
    }
  ],
  "needs_axis_clarification": false
}
```

硬性要求：

- 不允许只返回整句题目作为 object。
- 不允许只返回“深度学习”“检测”这类泛词。
- 至少输出 `object_terms + task_terms`。
- 如果题目确实无法解析，必须显式返回 `needs_axis_clarification=true`。

### 2.2 SearchPlannerAgent

职责：

- 基于 topic atoms 生成多源检索计划。
- 不直接调用网络。
- 不直接生成候选。

必须输出 query matrix：

```json
{
  "paper_queries": [],
  "dataset_queries": [],
  "repo_queries": [],
  "baseline_queries": [],
  "parallel_work_queries": [],
  "negative_queries": [],
  "why": []
}
```

查询生成规则：

- 每条 query 必须绑定至少两个主题轴。
- repo query 必须包含 object/task/scenario 中至少一个。
- dataset query 必须包含 object 或 scenario。
- baseline query 必须包含 method 或 task，同时包含 object/scenario 中至少一个。
- 不允许出现只有单个泛词的 query。

推荐组合：

```text
object + task + paper
object + task + dataset benchmark
method + object + baseline method
method + task + implementation
object + scenario + survey
```

### 2.3 MultiSourceFetchAgent

职责：

- 按 SearchPlannerAgent 的 query matrix 调用工具。
- 记录每一次 tool call。
- 不做最终保留判断。

工具策略：

- arXiv / OpenAlex / Crossref：论文和综述。
- GitHub：工程复现、baseline 实现、代码仓库。
- HuggingFace：数据集、模型、demo。
- WebSearch：补充公开数据集、项目主页、论文主页。

硬性要求：

- 每个 topic 至少跑 paper / dataset / repo 三类检索，除非 SearchPlanner 明确说明某类无法构造有效 query。
- 每次调用必须写入 trace：

```json
{
  "agent": "MultiSourceFetchAgent",
  "tool": "",
  "query": "",
  "source_type": "paper|dataset|repo|web",
  "result_count": 0,
  "error": "",
  "fallback_used": false
}
```

### 2.4 CandidateVerifierAgent

职责：

- 判断候选是否真实。
- 判断候选与题目轴的关系。
- 判断候选角色：baseline / parallel_work / dataset / repo / survey / unrelated。

禁止：

- 用具体标题黑名单。
- 用热门 repo 名称直接 reject。
- 只靠分数决定去留。

必须输出：

```json
{
  "candidate_id": "",
  "title": "",
  "source_type": "",
  "verified_status": "verified|partial|unverified|metadata_mismatch",
  "axis_match": {
    "method_hit": [],
    "object_hit": [],
    "task_hit": [],
    "scenario_hit": [],
    "missing_axis": []
  },
  "role": "baseline|parallel_work|dataset|repo|survey|supporting|reject",
  "relation": "direct|proxy|foundation|infrastructure|off_topic",
  "accept_as_main_evidence": false,
  "reject_reason": ""
}
```

主证据接收标准：

- `direct`：至少命中 object + task，或 method + object/task。
- `proxy`：命中 task 或 object，但应用场景略有偏移，可进入候选，不可直接作为 baseline。
- `foundation`：基础方法或框架，只能作为辅助候选，不能单独让 case 通过。
- `infrastructure`：工具库、通用工程，只能作为辅助候选，不能单独让 case 通过。
- `off_topic`：剔除。

### 2.5 EvidenceLayerAgent

职责：

- 把候选分层，而不是只给一个混杂列表。

输出分层：

```text
核心论文：直接研究同对象/同任务。
平行论文：同任务或同对象，可学习实验设计/模块组合。
Baseline：可复现主干或论文中明确使用的基础方法。
数据集：公开、可下载、与对象/任务匹配。
工程：repo、demo、模型实现。
辅助资料：综述、博客、项目页。
剔除资料：说明剔除原因。
```

硬性要求：

- Baseline 可以从候选论文中选择，也可以来自论文引用的基础方法。
- 如果系统无法判断 baseline，必须让候选留在“待人工选择 baseline”，不能编造。
- 不允许把 repo-only 结果作为题目可行的主要证据。

### 2.6 ReflectionLoopAgent

职责：

- 根据失败原因生成下一轮检索计划。
- 只修 query、source、axis，不改最终结论。

触发条件：

- paper 不足。
- dataset 不足。
- baseline 不足。
- repo 不足。
- 批内重复污染。
- 主题轴命中不足。
- 元数据不一致。

Reflection 输出：

```json
{
  "failure_type": "",
  "bad_pattern": "",
  "next_queries": [],
  "avoid_query_patterns": [],
  "why_next_queries_should_work": ""
}
```

禁止：

- 直接给固定候选。
- 直接写具体黑名单。
- 只把同一个泛 query 换个后缀重试。

## 3. 批内污染检测

本轮必须新增通用污染检测，不允许写具体项目名。

### 3.1 重复候选污染

规则：

- 同一候选标题在同一批次中出现在 3 个及以上不同 case 的主证据列表中。
- 且这些 case 的 object/task/scenario 明显不同。
- 且该候选没有命中每个 case 的 object/task 轴。

则标记：

```json
{
  "pollution_type": "repeated_generic_candidate",
  "candidate_title": "",
  "case_count": 0,
  "affected_cases": [],
  "action": "remove_from_main_evidence_keep_as_auxiliary_or_reject"
}
```

### 3.2 泛查询污染

规则：

- query 只包含 method 或泛词。
- query 不包含 object/task/scenario。
- 该 query 产生的候选在多个不同 case 中重复出现。

则标记：

```json
{
  "pollution_type": "generic_query",
  "query": "",
  "reason": "missing object/task/scenario axis"
}
```

## 4. Validator 重写规则

不允许再用：

```text
new_candidates_n >= 1 -> pass
```

新的 case 通过条件：

```text
PASS:
  direct_or_proxy_main_evidence_n >= 2
  and paper_main_evidence_n >= 1
  and topic_axis_match_n >= 2
  and repeated_generic_candidate_n == 0
  and repo_only_pass == false
  and fixed_fallback_seen == false

WEAK:
  paper_main_evidence_n >= 1
  and repeated_generic_candidate_n == 0
  and 有明确待补项

FAIL:
  repeated_generic_candidate_n > 0
  or repo_only_pass == true
  or topic_axis_match_n == 0
  or fixed_fallback_seen == true
  or metadata_mismatch_main_evidence_n > 0
```

报告必须显示：

- 候选标题。
- 来源。
- 命中的 method/object/task/scenario。
- 角色。
- 为什么保留。
- 为什么剔除。
- 是否主证据。

## 5. 强制 Loop

执行者必须按小循环修，不能直接跑全量然后交报告。

### Loop A：代码静态审计

检查范围：

- `apps/api/app/services/agents`
- `apps/api/scripts`
- `apps/api/tests`

必须确认：

- 无运行时标题黑名单。
- 无固定 baseline fallback。
- 无固定 repo fallback。
- 无 `new_candidates_n >= 1` 直接 pass。
- 无 `first_en + open source`。
- 无 `first atom + github repository`。
- 无 `foundation` 直接作为 pass 主证据。

输出：

- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_静态审计报告.md`

### Loop B：3 个微型样例

使用 3 个不同领域题目：

1. 工业缺陷检测题。
2. 三维视觉/重建/SLAM 题。
3. NLP/大语言模型/文本评估题。

要求：

- 三个题目的 top 主证据不能共享同一批通用候选。
- 每个题目必须显示 query matrix。
- 每个主证据必须有 axis_match。
- repo-only 不得通过。

输出：

- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_微型样例审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_微型样例审计.csv`

### Loop C：抽样 10

要求：

- `PASS + WEAK >= 9/10`
- `repeated_generic_candidate_n = 0`
- `repo_only_pass = 0`
- `fixed_fallback_seen = 0`
- 每个 WEAK 必须写清楚缺什么。

输出：

- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_抽样10审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_抽样10审计.csv`

### Loop D：Balanced40

要求：

- `PASS + WEAK >= 95%`
- 不允许批内重复污染。
- 不允许固定 fallback。
- 不允许靠 repo-only 通过。
- 不允许隐藏失败 case。

输出：

- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_Balanced40_逐论文审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_Balanced40_逐论文审计.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_Balanced40_致命问题自查.md`

## 6. 撞墙处理

执行者撞墙时，先看参考工程，不允许继续猜。

参考路径：

- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills`

重点参考：

- 多轮 query rewrite。
- 文献 source verification。
- 候选角色分类。
- source quality hierarchy。
- research planning prompt。
- trace 记录方式。

只有以下情况可以停：

- 外部 API 不可用，并已有日志证明。
- 参考工程路径不可读。
- 需要用户确认题目语义，否则会强行编造。
- 需要改 Agent 总架构，超出本轮局部修复范围。

不能因为样例失败就停。样例失败必须进入 Loop 修复。

## 7. 完工报告要求

最终必须提交：

- 修改了哪些模块。
- 删除了哪些硬编码。
- 新增了哪些通用规则。
- 每个 Loop 的结果。
- 失败 case 的真实原因。
- 是否仍存在主链路风险。
- 是否允许进入下一阶段。

如果实现与文档不一致，必须写：

```text
实现偏离点：
偏离原因：
影响范围：
后续修复建议：
```

