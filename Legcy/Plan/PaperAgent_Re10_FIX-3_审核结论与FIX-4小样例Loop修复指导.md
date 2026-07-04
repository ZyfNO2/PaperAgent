# PaperAgent Re10 FIX-3 审核结论与 FIX-4 小样例 Loop 修复指导

## 0. 审核结论

Re10 FIX-3 暂不建议验收，也不建议进入全量重跑。

原因不是“结果完全没改善”，而是当前实现和报告仍然存在三个关键问题：

1. 仍有具体 repo 名称硬编码过滤，违反“不要固化硬编码”的主要求。
2. 典型样例报告承认关键字段和 validator 未完整验证，却在结论中写“已解决”。
3. 执行者又尝试全量和并行验证，和当前应采用的“小量 Loop 自查”方向相反。

下一阶段只允许每轮跑 3-5 个 case。小样例未通过前，不允许 Balanced40 全量验证。

## 1. 主要发现

### P0-1：仍然存在具体 repo 名称硬编码

位置：

- `G:\PaperAgent\apps\api\app\services\agents\search_reflection_loop.py:335`
- `G:\PaperAgent\apps\api\app\services\agents\search_reflection_loop.py:336`
- `G:\PaperAgent\apps\api\app\services\agents\search_reflection_loop.py:344`
- `G:\PaperAgent\apps\api\scripts\validate_re10_reflection_search.py:340`
- `G:\PaperAgent\apps\api\scripts\validate_re10_reflection_search.py:341`
- `G:\PaperAgent\apps\api\scripts\validate_re10_reflection_search.py:362`

问题：

代码中出现了：

```python
generic_repos = {"ORB_SLAM3", "open_vins", "awesome-visual-slam"}
```

以及：

```python
generic_repo_in_non_slam_topic
```

这仍然是“把某个坏样例写死”的修法。它能挡住当前截图里的污染，但挡不住下一个热门通用 repo，也会让审计逻辑继续偏向 SLAM 特例。

修复要求：

- 删除具体 repo 名称集合。
- 删除 `non-SLAM` 特判。
- 改为通用批内污染检测：
  - 同一候选在同一批次 3 个以上不同题目中进入主证据。
  - 这些题目的 object/task/scenario 不同。
  - 该候选没有命中当前 case 的 object/task 轴。
  - 则标记 `repeated_generic_candidate_pollution`。

候选是否污染只能由“重复模式 + 主题轴不匹配”决定，不由标题名称决定。

### P0-2：topic_axis_match 的实现可能失效

位置：

- `G:\PaperAgent\apps\api\app\services\agents\search_reflection_loop.py:313`
- `G:\PaperAgent\apps\api\app\services\agents\search_reflection_loop.py:324`

问题：

当前写法类似：

```python
method_hit = [k for k in verdict.matched_keywords if k in (topic_atoms.get("method") or [])]
```

但 `topic_atoms.get("method")` 往往是 list[dict]，例如：

```json
{"en": "YOLOv5", "zh": "YOLOv5"}
```

`k in list[dict]` 基本不会命中，所以 `method_hit/object_hit/task_hit` 可能全空。典型样例报告也承认 trace 中未验证 `topic_axis_match` 字段。

修复要求：

- 抽出统一函数 `flatten_axis_terms(topic_atoms, axis)`。
- 同时展开 `en / zh / aliases`。
- hit 计算必须在 `candidate_verifier` 和 `topic_axis_match` 共用同一套 axis 展开逻辑。
- `axis_verdict=accept` 不能只靠字段存在，必须能在 trace 中看到具体命中词。

### P0-3：报告结论越过证据

位置：

- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_典型样例审计.md:36`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_典型样例审计.md:45`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_典型样例审计.md:60`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_典型样例审计.md:76`

问题：

报告先写：

- trace 未包含 `topic_axis_match`。
- 缺少 `summary.json`。
- validator 无法完整验证。

后面又写：

- 每个候选都有主题轴匹配信息。
- 建议进入 Loop B。

这不成立。没有 trace 字段和 validator 输出，就不能判定通过。

修复要求：

- 报告结论必须改为“未通过 / 待补验证”。
- 若缺 `summary.json`，该轮 Loop 不能过。
- 若 trace 中没有 `topic_axis_match`，该轮 Loop 不能过。
- 若 validator 未完整跑通，该轮 Loop 不能过。

### P1-1：Validator 的 H10 仍是硬编码污染检测

位置：

- `G:\PaperAgent\apps\api\scripts\validate_re10_reflection_search.py:340`
- `G:\PaperAgent\apps\api\scripts\validate_re10_reflection_search.py:341`

问题：

H10 当前只检查三个固定 repo 名称，不是真正的“通用 repo 污染检测”。

修复要求：

H10 改为批内统计：

```text
repeated_main_candidate_title_n
repeated_main_candidate_case_n
repeated_candidate_axis_miss_n
```

失败条件：

```text
同一 candidate title 在 >=3 个不同 case 中作为主证据出现
and 这些 case 的 object/task/scenario 不同
and 该 candidate 对其中任意 case 缺少 object/task 命中
```

### P1-2：Fallback 标记口径混乱

位置：

- `G:\PaperAgent\apps\api\app\services\agents\domain_scout_agent.py:257`
- `G:\PaperAgent\apps\api\app\services\agents\search_reflection_helpers.py:77`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_完工报告.md:79`

问题：

报告声称 `Fallback误标 40/40 零 [Fallback]`，但代码中仍会写 `[Fallback] LLM offline` 和 `[Fallback] ... dataset benchmark`。如果报告只检查 query，没有检查 search_notes，就会误报。

修复要求：

- 区分 `fallback_mode` 和 `query_text`。
- 不要把 `[Fallback]` 放入 query。
- trace 中用结构化字段记录：

```json
{
  "fallback_mode": true,
  "fallback_reason": "llm_parse_failed",
  "query": "steel surface defect detection dataset benchmark"
}
```

报告必须分别统计：

- fallback 发生次数。
- fallback query 是否污染。
- fallback 是否导致候选通过。

### P1-3：并行验证不应继续进入主流程

位置：

- `G:\PaperAgent\apps\api\scripts\run_balanced40_reflection_re10.py:376`
- `G:\PaperAgent\apps\api\scripts\run_balanced40_reflection_re10.py:493`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_完工报告.md:141`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_完工报告.md:143`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_完工报告.md:150`

问题：

报告已经证明 `--parallel 3` 会导致 OpenAlex 429，但脚本仍保留 `--parallel` 参数。保留参数可以，但修复阶段不允许使用它做验收。

修复要求：

- 小样例 Loop 固定 `--parallel 1`。
- 报告必须写明实际运行参数。
- 任何并行跑出的失败不能作为主结论。

## 2. FIX-4 修复范围

本轮只修主链路最小闭环，不新增 Agent，不跑全量。

允许修改：

- `search_reflection_loop.py`
- `search_reflection_helpers.py`
- `candidate_verifier.py`
- `validate_re10_reflection_search.py`
- `re10_fix2_to_csv.py` 或新建 FIX-4 CSV 审计脚本
- 必要的单元测试 / 小样例测试脚本

不建议修改：

- 前端。
- 报告生成 UI。
- RAG。
- 工作包生成。
- 大规模 orchestration。

## 3. FIX-4 必须完成的代码规则

### 3.1 删除具体标题/项目名硬编码

必须删除：

```python
generic_repos = {...}
is_slam_topic = ...
generic_repo_in_non_slam_topic
```

替换为：

```text
batch-level repeated candidate detector
topic-axis mismatch detector
repo-only pass detector
```

### 3.2 统一 axis 展开

新增或复用一个函数：

```python
flatten_axis_terms(topic_atoms, axis) -> list[str]
```

要求：

- 支持 list[str]。
- 支持 list[dict]。
- 展开 `en / zh / aliases`。
- 去重。
- 不调用网络。
- 不调用 LLM。

### 3.3 主证据接收标准

accepted candidate 必须满足：

```text
verified_status in verified/metadata_repaired/weak_metadata
and relation in direct/proxy
and axis_match 至少命中 object/task 之一
and repo-only 不得让 case pass
```

foundation / infrastructure：

- 可以保留为辅助候选。
- 不能进入主证据。
- 不能计入 `topic_axis_pass_n`。
- 不能让 case 通过。

### 3.4 Validator 必须先验证字段存在

Validator 的第一层 gate：

```text
summary.json exists
trace exists for every case
accepted candidates contain topic_axis_match
topic_axis_match contains concrete hit terms
validator itself exits 0 only when all gates pass
```

如果字段不存在，直接 fail，不允许“根据代码应该有”。

## 4. 强制小样例 Loop

从现在开始，任何一轮 Loop 只允许 3-5 个 case。

### Loop 1：静态审计，不跑网络

目标：

- 查硬编码。
- 查固定 fallback。
- 查 validator 是否仍用具体标题。
- 查报告是否可能在 validator 未跑通时写通过。

命令建议：

```powershell
rg -n "generic_repos|non-SLAM|ORB_SLAM|open_vins|awesome-visual-slam|STRONG_NOISE|title ==|new_candidates_n >= 1|\\[Fallback\\]" apps/api/app/services/agents apps/api/scripts
```

通过条件：

- 主链路代码无具体候选标题黑名单。
- validator 无具体候选标题黑名单。
- query 中不出现 `[Fallback]`。
- 报告生成逻辑不能在缺 summary/trace 时通过。

### Loop 2：3 个微型题目

只跑 3 个：

1. `基于YOLOv5的钢铁表面缺陷检测研究`
2. `基于深度学习的视觉SLAM语义地图构建研究`
3. `基于大语言模型的医学问答答案可信度评估`

通过条件：

- 每个 case 都有 `summary.json`。
- 每个 case 都有 trace。
- accepted 主证据中必须有 `topic_axis_match`。
- 每条主证据必须显示命中词。
- 没有任何具体 repo 黑名单触发记录。
- validator 完整跑通。

### Loop 3：5 个跨领域题目

只跑 5 个，覆盖：

- 2D 工业缺陷。
- 3D/SLAM/点云。
- NLP/LLM。
- 遥感/农业。
- 电力/设备识别。

通过条件：

- 5/5 无批内重复主证据污染。
- 5/5 无 repo-only pass。
- 5/5 无 fixed fallback pass。
- 至少 4/5 有 paper 主证据。
- 失败 case 必须给出明确 failure_type，不允许写“已解决”。

### Loop 4：抽样 5 回归

从之前出问题的样例中抽 5 个，不要跑 10 个，更不要跑 40 个。

通过条件：

- `PASS + WEAK >= 4/5`
- `FAIL` 必须是合理失败，不是污染、字段缺失或 validator 缺失。
- 不允许出现“报告说通过但 validator 未跑”的情况。

## 5. 禁止扩大测试的条件

出现以下任意情况，不允许进入下一轮更大测试：

- trace 缺 `topic_axis_match`。
- validator 无法完整运行。
- 报告存在“无法验证但建议通过”。
- 仍有具体 repo / 论文 / 数据集名称硬编码过滤。
- 任一 case 由 repo-only 通过。
- OpenAlex 429 导致结果不完整。
- 使用 `--parallel > 1`。

## 6. 下一份报告必须包含

文件建议：

- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-4_静态审计报告.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-4_小样例3审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-4_小样例3审计.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-4_跨领域5审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-4_完工报告.md`

完工报告必须回答：

1. 是否删除了具体候选标题硬编码？
2. 是否删除了 non-SLAM 特判？
3. topic_axis_match 是否真实出现在 trace？
4. validator 是否在缺字段时 fail？
5. 是否只跑了 3-5 个 case？
6. 是否使用 `--parallel 1`？
7. 哪些 case 仍失败，失败原因是什么？

## 7. 当前是否可进入下一阶段

不可以。

只能进入 FIX-4 小样例修复 Loop。小样例全部通过前，不允许继续做 Balanced40 全量，也不允许转去新功能。

