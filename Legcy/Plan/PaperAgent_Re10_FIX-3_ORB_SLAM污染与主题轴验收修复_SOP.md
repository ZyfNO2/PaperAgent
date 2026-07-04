# PaperAgent Re10 FIX-3：ORB_SLAM 污染与主题轴验收修复 SOP

## 0. 本轮结论

Re10 FIX-2 不能进入下一阶段。当前问题不是“某一个题目搜不到”，而是检索链路存在跨题目污染：`ORB_SLAM3 / open_vins / awesome-visual-slam` 这类通用视觉工程被多个无关题目接收，并且被 case-level audit 判为通过。

本轮只修检索与验收，不新增 Agent 架构，不新增 HumanGate，不做论文数据网。

## 1. 已定位的污染原因

### 1.1 Repo 查询过泛

重点检查：

- `apps/api/app/services/agents/search_reflection_helpers.py`
- `apps/api/app/services/agents/search_reflection_loop.py`

当前链路中存在类似：

```python
probe = f"{first_en} open source"
```

以及后续多轮检索中使用：

```python
atom = en_atom_pool[0]
must_search.append(f"{atom} github repository")
must_search.append(f"{atom} dataset benchmark")
must_search.append(f"{atom} baseline method")
```

这会导致第一个英文关键词一旦过泛，例如 `deep learning`、`3D reconstruction`、`computer vision`，后续 repo / dataset / baseline 查询都会偏向通用热门工程。ORB_SLAM3 正是这类通用热门工程污染。

### 1.2 接收标准只看“有没有候选”，没有看“是否命中题目轴”

重点检查：

- `apps/api/scripts/re10_fix2_to_csv.py`
- `apps/api/scripts/validate_re10_reflection_search.py`
- `apps/api/app/services/agents/search_reflection_loop.py`

当前 audit 里 `accepted_n >= 1` 就容易被判为通过，但没有强制要求候选命中：

- 方法轴：YOLO / U-Net / Transformer / LLM / SLAM / PointNet 等
- 对象轴：钢材裂缝 / 农作物 / 医学问答 / 绝缘子 / 混凝土 等
- 任务轴：检测 / 分割 / 识别 / 问答 / 评估 / 重建 等
- 场景轴：表面缺陷 / 遥感 / 医学 / 工业质检 / 农业 等

所以“YOLO 钢材缺陷检测”里出现 ORB_SLAM3，不应该因为它是 GitHub repo 就被接收。

### 1.3 `final_candidate_pool` 保留了污染 seed

重点检查：

- `apps/api/app/services/agents/search_reflection_loop.py`

如果污染 repo 被加入 `seed_pool`，最后：

```python
"final_candidate_pool": list(seed_pool.values())
```

会把它原样带到最终结果。后续 CSV 抽取只读 pool，不知道它为什么被接收，于是污染会扩散到审计报告。

### 1.4 Validator 没有拦截“通用 repo 横跨多个无关 case”

FIX-2 的 case-level audit 没有硬性失败以下情况：

- 同一个 repo 标题在多个不相关 case 的 top accepted titles 中反复出现。
- `domain_route` 为空。
- `fixed_unet_fallback_seen=True`。
- repo-only candidate 导致 case 通过。
- 非 SLAM / 非 3D mapping 题目中出现 ORB_SLAM3、open_vins、awesome-visual-slam。

## 2. 本轮目标

把检索验收从“有结果就算好”改为“结果必须贴合题目轴”。

最小合格状态：

- YOLO / U-Net / 钢材 / 混凝土 / 农业 / 医学 / NLP 等不同题目不再共用 ORB_SLAM3 这类通用 repo。
- SLAM 相关题目允许出现 ORB_SLAM3，但不能只靠 ORB_SLAM3 通过。
- 每个 accepted candidate 必须显示主题轴命中情况。
- 每个 case 的 pass / weak / fail 必须有可解释理由。

## 3. 禁止事项

本轮禁止：

- 禁止只写 `if title == "ORB_SLAM3": reject` 这种单点黑名单修复。
- 禁止通过隐藏 accepted_titles、删除报告列、降低审计输出密度来“看起来通过”。
- 禁止继续使用 `first_en + " open source"` 作为 repo 查询。
- 禁止只用第一个英文 atom 生成 dataset / repo / baseline 查询。
- 禁止 repo-only candidate 让 case 通过。
- 禁止把所有检测题都打到 CV 检测路线。
- 禁止把无法解析的整句题目当作唯一 object term。
- 禁止用 `accepted_n >= 1` 作为通过条件。

可以有少量通用污染词表用于诊断，但不能作为唯一修复手段。真正修复必须来自查询生成、候选验收、validator 三层。

## 4. 代码修改范围

优先只改这些模块：

- `apps/api/app/services/agents/search_reflection_helpers.py`
- `apps/api/app/services/agents/search_reflection_loop.py`
- `apps/api/scripts/re10_fix2_to_csv.py`
- `apps/api/scripts/validate_re10_reflection_search.py`
- 现有候选清洗 / relevance / verifier 模块，如果已有则复用，不新增重复模块。

不允许大规模重构前端、RAG、Agent 编排框架。

## 5. 必须实现的修复

### 5.1 查询生成：从 first atom 改成主题轴组合

新增或改造一个 query builder，输入必须是结构化 topic parse：

```json
{
  "method_terms": ["YOLOv5", "YOLO"],
  "object_terms": ["steel surface defect", "steel crack"],
  "task_terms": ["defect detection", "crack detection"],
  "scenario_terms": ["industrial inspection"],
  "negative_terms": []
}
```

repo 查询规则：

- 必须包含 object 或 scenario。
- 必须包含 task 或 method。
- 不允许只有 `deep learning github repository`。
- 不允许只有 `3D reconstruction open source`。
- 如果 object/task 缺失，repo 查询直接标记 `repo_query_blocked_missing_axis`，不要强行搜。

示例：

```text
steel surface defect detection YOLO GitHub
steel crack segmentation U-Net GitHub
crop early recognition remote sensing GitHub
medical question answering factuality benchmark GitHub
```

dataset 查询规则：

```text
steel surface defect detection dataset
steel crack segmentation dataset benchmark
crop early recognition remote sensing dataset
medical QA factuality dataset
```

paper 查询规则：

```text
steel surface defect detection YOLO paper
steel crack segmentation U-Net paper
crop early recognition remote sensing deep learning paper
medical question answering factuality evaluation paper
```

### 5.2 候选接收：每条候选必须有 topic_axis_match

每条 candidate 必须补充：

```json
{
  "method_hit": ["YOLO"],
  "object_hit": ["steel surface"],
  "task_hit": ["defect detection"],
  "scenario_hit": ["industrial inspection"],
  "missing_axis": [],
  "axis_verdict": "accept|weak|reject",
  "reject_reason": ""
}
```

最低接收标准：

- Paper：至少命中 `object + task`，或命中 `method + object/task`。
- Dataset：必须命中 `object/task/scenario` 中至少两个。
- Repo：必须命中 `object/task/scenario` 至少一个，并命中 `method/task` 至少一个。
- 通用 repo 只能作为 `supporting_candidate`，不能成为 case pass 的主证据。

### 5.3 通用 repo 污染检测

Validator 必须检测同一批次中重复出现的 top repo。

规则：

- 同一 repo title 出现在 3 个及以上不同主题 case 的 top accepted candidates 中，记为 `generic_repo_pollution`。
- 如果这些 case 的 object/task 不同，必须 hard fail。
- 例外：这些 case 本身都属于 SLAM / visual odometry / 3D mapping / robotics localization。

示例：

- `基于YOLOv5的钢铁表面缺陷检测研究` 出现 ORB_SLAM3：fail。
- `基于深度学习的视觉SLAM语义地图构建研究` 出现 ORB_SLAM3：allowed，但还需要 paper/dataset 或其他 SLAM 证据。

### 5.4 Validator 通过条件重写

不再使用 `new_candidates_n >= 1`。

新增字段：

- `topic_axis_pass_n`
- `paper_axis_pass_n`
- `dataset_axis_pass_n`
- `repo_axis_pass_n`
- `repo_only_candidate_n`
- `generic_repo_pollution`
- `top_repeated_repo_titles`
- `domain_route_empty`
- `fixed_fallback_seen`
- `pass_reason`
- `reject_reason`

case 通过条件：

```text
PASS:
  topic_axis_pass_n >= 2
  and paper_axis_pass_n >= 1
  and generic_repo_pollution == 0
  and domain_route_empty == false
  and fixed_fallback_seen == false
  and not repo_only_pass

WEAK:
  paper_axis_pass_n >= 1
  and generic_repo_pollution == 0
  and 有明确待补项

FAIL:
  generic_repo_pollution > 0
  or fixed_fallback_seen == true
  or domain_route_empty == true
  or repo_only_pass == true
  or topic_axis_pass_n == 0
```

### 5.5 输出必须可解释

审计报告中每个 candidate 不能只显示 score，必须显示：

```text
命中关键词：method=[YOLO], object=[steel surface], task=[defect detection]
未命中：scenario=[]
接收原因：object+task 命中，属于可参考论文
```

如果 reject：

```text
拒绝原因：仅命中 generic method，没有命中对象/任务轴
```

## 6. 强制 Loop

执行者必须按以下 Loop 做，未通过不能停。

### Loop 0：复现污染

输入 FIX-2 已有报告：

- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-2_抽样10审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-2_Balanced40_逐论文审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-2_SearchTrace_索引.md`

输出：

- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_污染复现报告.md`

必须写清：

- 哪些 case 出现 ORB_SLAM3 / open_vins / awesome-visual-slam。
- 这些 case 是否属于 SLAM。
- 污染来自 query、seed_pool、validator 还是 CSV 抽取。

### Loop A：3 个微型样例

只跑 3 个题目，必须全部通过后才能进入 Loop B。

1. `基于YOLOv5的钢铁表面缺陷检测研究`
2. `基于深度学习的视觉SLAM语义地图构建研究`
3. `基于大语言模型的医学问答答案可信度评估`

验收：

- Case 1 不得出现 ORB_SLAM3 / open_vins / awesome-visual-slam 作为 accepted。
- Case 1 应出现钢材、表面缺陷、YOLO、NEU-DET、defect detection 等相关证据。
- Case 2 可以出现 ORB_SLAM3，但必须同时有 SLAM 论文或数据集/benchmark 证据。
- Case 3 不得出现 CV/SLAM/U-Net fallback。
- 三个 case 都必须显示 topic_axis_match。

### Loop B：旧典型 5 例

跑原 Re10 FIX-2 的 TYPICAL-01 到 TYPICAL-05。

验收：

- `fixed_unet_fallback_seen=False`
- `domain_route` 不为空。
- `repo_only_pass=False`
- 每个 case 至少 1 条 paper_axis_pass。
- 不允许通用 repo 横跨多个无关 case。

### Loop C：抽样 10

跑抽样 10。

验收：

- `generic_repo_pollution=0`
- `domain_route_empty=0`
- `fixed_fallback_seen=0`
- `repo_only_pass=0`
- `PASS + WEAK >= 9/10`
- 所有 WEAK 必须有明确待补项，不能是污染通过。

### Loop D：Balanced40

跑 Balanced40。

验收：

- `PASS + WEAK >= 95%`
- `FAIL` 只能来自真实外部检索失败或题目本身信息不足。
- `generic_repo_pollution=0`
- `fixed_fallback_seen=0`
- `domain_route_empty=0`
- 抽查重复 top titles，不能出现同一通用 repo 支配多个无关 case。

Loop D 结束后必须自查一遍：

- 是否还有 ORB_SLAM3 出现在非 SLAM case。
- 是否还有 U-Net fallback 出现在 NLP / 医学 QA / 非图像题。
- 是否还有空 URL 被直接判为 fail，而不是尝试补 URL。
- 是否还有 `X` 占位符未进入补全流程。

## 7. 允许停止的条件

执行者只有在以下情况可以停下：

- 外部检索 API 全部不可用，并且已经提供 mock 复现、失败日志、重试记录。
- 需要改动 Agent 总架构才可继续，并且已经说明当前局部修复为什么无法解决。
- 关键参考工程缺失或不可读，并且已经列出缺失路径。

不能因为“一次测试没过”“prompt 不稳定”“报告不好看”停止。必须继续 Loop 内修理。

## 8. 交付物

必须生成：

- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_污染复现报告.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_典型样例审计.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_典型样例审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_Validator输出.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_抽样10审计.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_抽样10审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_Balanced40_逐论文审计.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_Balanced40_逐论文审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_Balanced40_致命问题自查.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-3_完工报告.md`

完工报告必须包含：

- 代码改了哪些模块。
- 每个 Loop 的结果。
- 仍然失败的 case 和原因。
- 是否可以进入下一阶段。

## 9. 关键参考源

执行者撞墙时必须先看这些参考，不允许闭门造车。

### AutoResearchClaw

参考路径：

- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw`

重点找：

- 多轮检索 query 生成。
- 失败后反思式 query rewrite。
- GitHub / paper / dataset 分源检索逻辑。
- 候选合并与去噪。
- search trace 的记录方式。

### academic-research-skills

参考路径：

- `C:\Users\ZYF\Desktop\Paper\academic-research-skills`

重点找：

- 文献策略 agent。
- source verification agent。
- source quality hierarchy。
- research planning prompt。
- 证据可信度与引用关系判断。

## 10. 文档同步提醒

本轮会改变检索验收口径、candidate 数据字段、Validator 通过条件。完成后需要同步更新 `/docs` 或 `Plan` 中对应设计文档：

- 候选证据字段说明。
- 检索通过 / weak / fail 标准。
- repo-only candidate 的处理规则。
- topic_axis_match 的定义。

如果执行者暂时不更新正式 docs，必须在完工报告中记录“实现与文档偏离点”。

