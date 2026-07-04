# PaperAgent Re06 去硬编码噪声与证据一致性审计 SOP

## 0. 本阶段结论

Re05 的总体召回能力相比 Re04 有明显进步，但 **不能直接按 `pass + weak = 95%` 认定检索链路已经稳定**。当前主要问题不是“搜得不够多”，而是：

1. 候选证据进入 core / baseline / parallel 后缺少结构化一致性审计。
2. `STRONG_NOISE_TOKENS` 是本地硬编码噪声表，已经参与 `fail` 判定，违背此前 SOP 中“不得用黑名单硬过滤”的约束。
3. 部分 case 的 `pass` 仍由数量指标撑起，但直接证据不足、数据集角色不清、或 core 为空。

Re06 的目标不是继续加大功能，而是把 Re05 的结果评价从“关键词黑名单 + 数量统计”改为“候选证据一致性审计 + 角色分层统计”。

## 1. 输入材料

执行前必须阅读：

- `G:\PaperAgent\Plan\PaperAgent_Re05_Balanced40_完工报告.md`
- `G:\PaperAgent\Plan\PaperAgent_Re05_Balanced40_逐论文审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re05_检索收尾与Balanced40_SOP.md`
- `G:\PaperAgent\Plan\PaperAgent_Re04_资源检索大测试集评估与增强_SOP.md`
- `G:\PaperAgent\apps\api\app\services\agents\eval\__init__.py`
- `G:\PaperAgent\apps\api\tests\test_re04_resource_eval_offline.py`
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills`

参考重点：

- AutoResearchClaw 的多 query、多源、去重、source stats、缓存回退和严格领域审稿思路。
- academic-research-skills 的 2-4 个核心概念、同义词扩展、纳排标准、title/abstract screening、citation chaining / semantic search 分层策略。

## 2. Re05 抽样审计结论

### 2.1 `STRONG_NOISE_TOKENS` 溯源

代码位置：

- `G:\PaperAgent\apps\api\app\services\agents\eval\__init__.py`
- `G:\PaperAgent\apps\api\tests\test_re04_resource_eval_offline.py`

Git 溯源：

- 首次进入代码的提交：`4c28eb1 Re04: 100-case eval set + main entry + 5 retrieval modules + LLM online hook`
- Re05 SOP 未要求该表。
- AutoResearchClaw 与 academic-research-skills 的参考流程也没有要求本地硬编码跨领域黑名单。

问题判断：

- 这是 Re04 执行阶段加入的本地启发式表，不是用户明确要求，也不是参考项目中的必要设计。
- 注释声称“NOT used to FILTER”，但 `compute_resource_status()` 中实际存在：
  - `has_noise = any(_is_strong_noise(t) for t in core_titles)`
  - `if has_noise: status = "fail"`
- 因此它已经是运行时硬编码评估门禁，不是单纯的观测指标。

### 2.2 抽样 case 判断

#### ENG-THESIS-048：面向动态环境的视觉SLAM研究

抽样结论：当前判为 fail 是合理的，但失败原因不应依赖 `AGN` 黑名单。

观察：

- baseline 中出现 `A rich bounty of AGN in the 9 square degree Bootes survey...`
- 该候选显然是天文方向，与动态视觉 SLAM 不一致。
- Re05 报告还指出存在 Crossref metadata mismatch：标题是 AGN，摘要却像 ORB-LINE-SLAM3。

正确修复方向：

- 使用 title / abstract / source_url / DOI / query / topic atoms 的一致性检查。
- 将其标记为 `metadata_mismatch` 或 `off_topic`，禁止进入 baseline。
- 不允许靠 `AGN` 字符串命中决定失败。

#### ENG-THESIS-060：基于深度学习的车道线检测方法研究

抽样结论：当前 fail 很可能是误判。

观察：

- 报告中包含 `Agnostic Lane Detection` 这类与车道线检测相关的候选。
- `STRONG_NOISE_TOKENS` 使用 `tok.lower() in t`，会把 `AGN` 误命中到 `Agnostic`。
- 逐论文审计中还写到噪声并不在 core / baseline / parallel，而在 evidence_review 摘要侧，说明评估使用了不稳定的自由文本信号。

正确修复方向：

- `Agnostic Lane Detection` 应在车道线检测主题下通过一致性审计。
- 噪声判断不得从低门槛摘要自由文本中抽取关键词决定 case 状态。
- 评估必须基于结构化 candidate，而不是 LLM summary 里的残留词。

#### ENG-THESIS-018：基于深度学习的三维点云补全方法研究

抽样结论：状态 weak 大体合理，但数据统计存在不一致。

观察：

- 顶部表格显示 `dataset = 0`。
- core 中却出现 `PCN` 和 `ShapeNet`，方向建议里也将其作为 primary datasets。

正确修复方向：

- 需要区分 `topic_dataset_n`、`proxy_dataset_n`、`pretrain_dataset_n`、`generic_dataset_n`。
- summary 中的 dataset 数量必须与逐论文审计中的 dataset role 一致。

#### ENG-THESIS-092：海上风机叶片缺陷检测及分类

抽样结论：pass 基本可接受，但数据集角色需要标注清楚。

观察：

- core 中有 Blade-YOLOv8、GCB-YOLO 等较强领域匹配证据。
- 但报告承认 offshore-specific labeled dataset 缺失，NEU-DET / COCO / DOTA 只是迁移或预训练参考。

正确修复方向：

- 允许 pass，但必须展示“领域论文强，专属数据集缺口仍在”。
- 不允许把通用数据集直接算作同等强度的 topic dataset。

#### ENG-THESIS-093：基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究

抽样结论：当前 pass 偏乐观，建议至少降为 weak。

观察：

- `core (0)`。
- direction_recommendation 明确写道没有确认的接触网绝缘子论文或数据集。
- baseline 多为 DAMO-YOLO、HyperDefect-YOLO、YOLOPears 等通用或迁移型证据。

正确修复方向：

- `core_direct_n = 0` 且没有 topic dataset 时，不应只靠 baseline 数量判 pass。
- 必须引入 axis coverage：对象、任务、方法、场景至少要有直接覆盖或明确代理关系。

## 3. Re06 范围

### 3.1 本阶段必须做

1. 移除生产代码中的 `STRONG_NOISE_TOKENS` 运行时门禁。
2. 新建证据一致性审计模块，替代关键词黑名单。
3. 重构 `compute_resource_status()` 的状态判定逻辑。
4. 修正 dataset / baseline / parallel 的角色统计。
5. 对 Balanced40 做同代码版本重新审计，不混用旧 partial dump。
6. 输出新的逐论文审计报告，明确每个候选为什么进入 core / baseline / parallel。

### 3.2 本阶段不做

1. 不做 HumanGate。
2. 不做论文创新性判断。
3. 不做知识图谱。
4. 不做完整 100 篇全量跑通。
5. 不把本地黑名单换成更长的本地黑名单。
6. 不通过“加几个 if / 正则边界”修复根问题。

## 4. 代码整改任务

### Task A：移除硬编码噪声门禁

修改位置：

- `G:\PaperAgent\apps\api\app\services\agents\eval\__init__.py`
- `G:\PaperAgent\apps\api\tests\test_re04_resource_eval_offline.py`

要求：

- 生产代码中不得保留 `STRONG_NOISE_TOKENS`。
- 生产代码中不得保留 `_is_strong_noise()` 参与状态判定。
- 允许在测试 fixture 中保留“已知错误候选样例”，但这些样例必须放在测试数据里，而不是生产逻辑里。
- 不允许新增 `NOISE_WORDS`、`BAD_TITLES`、`BLACKLIST_TERMS`、`DOMAIN_BLOCKLIST` 等同类变体。

该模块不应该：

- 用关键词命中直接判 fail。
- 用 substring 判断候选是否跨领域。
- 用本地硬编码列表模拟审稿。
- 因为 `AGN`、`captcha`、`movie review` 等词出现就自动剔除候选。

### Task B：新增 `EvidenceConsistencyAuditor`

建议文件：

- `G:\PaperAgent\apps\api\app\services\agents\eval\evidence_consistency.py`

模块职责：

- 对单个候选证据做结构化一致性审计。
- 输入 topic atoms、candidate metadata、source metadata、retrieval query、evidence role。
- 输出可解释的审计结果。

建议数据结构：

```python
{
    "candidate_id": "c-xxxx",
    "role": "core|baseline|parallel|dataset|repo|rejected",
    "consistency_status": "aligned|proxy|generic|metadata_mismatch|off_topic|insufficient_metadata",
    "axis_coverage": {
        "task": "direct|proxy|missing",
        "object": "direct|proxy|missing",
        "method": "direct|proxy|missing",
        "scenario": "direct|proxy|missing"
    },
    "evidence_quality": {
        "has_title": true,
        "has_abstract": true,
        "has_url": true,
        "source_type": "arxiv|openalex|crossref|github|hf|cache",
        "title_abstract_consistent": true
    },
    "decision_reason": "短文本说明，必须能被逐论文审计直接展示"
}
```

硬性规则：

- `metadata_mismatch` 不得进入 core / baseline / parallel。
- `off_topic` 不得进入 core / baseline / parallel。
- `insufficient_metadata` 可以进入候选，但不能作为 pass 的核心依据。
- `proxy` 可以进入 parallel 或 dataset proxy，但页面必须标记“迁移 / 代理证据”。
- `generic` 可以保留为补充参考，但不能用于提升 pass 等级。

该模块不应该：

- 调网络。
- 调 LLM。
- 修改候选池。
- 生成新候选。
- 根据本地黑名单判定领域。

### Task C：新增 LLM 审稿式一致性审计 Prompt

建议文件：

- `G:\PaperAgent\apps\api\app\services\agents\prompts\evidence_consistency_review.md`

使用时机：

- 仅当规则审计无法确定 `aligned / proxy / off_topic / metadata_mismatch` 时调用。
- 仅处理已经有 title、abstract、url 或 source metadata 的候选。
- 不用于生成新论文候选。

Prompt 必须包含：

```text
你是工科学位论文选题助手中的证据一致性审稿员。
你的任务不是扩大召回，而是判断一个候选证据能否支持当前毕业选题。

输入包括：
1. 中文题目
2. topic atoms: task/object/method/scenario
3. candidate title
4. candidate abstract/snippet
5. source type and url
6. retrieval query
7. proposed role: core/baseline/parallel/dataset/repo

你必须输出 JSON：
{
  "consistency_status": "aligned|proxy|generic|metadata_mismatch|off_topic|insufficient_metadata",
  "axis_coverage": {
    "task": "direct|proxy|missing",
    "object": "direct|proxy|missing",
    "method": "direct|proxy|missing",
    "scenario": "direct|proxy|missing"
  },
  "role_allowed": true,
  "allowed_roles": ["core", "baseline", "parallel", "dataset", "repo", "candidate_only"],
  "reason": "...",
  "risk_note": "..."
}

判断原则：
- 如果 title 与 abstract 明显不是同一篇内容，返回 metadata_mismatch。
- 如果只是共享通用词，例如 detection / deep learning / survey，但对象和任务都不匹配，返回 off_topic。
- 如果方法相同但对象不同，返回 proxy。
- 如果对象相同但任务不同，返回 proxy 或 generic，不得作为 core。
- 如果是通用框架论文，例如 YOLO / U-Net / PointNet++，可作为 baseline scaffold，但必须说明它不是领域论文。
- 不得因为单个词命中而判定错误。
- 不得编造摘要中没有的信息。
```

参考来源：

- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw` 中的 literature screening：严格领域审稿、title/abstract screening、质量下限。
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills` 中的 systematic search：先定义核心概念与纳排标准，再做候选筛选。

### Task D：重构 `compute_resource_status()`

修改位置：

- `G:\PaperAgent\apps\api\app\services\agents\eval\__init__.py`

新状态字段：

```python
{
    "status": "pass|weak|fail|blocked",
    "paper_n": 0,
    "topic_dataset_n": 0,
    "proxy_dataset_n": 0,
    "pretrain_dataset_n": 0,
    "generic_dataset_n": 0,
    "repo_n": 0,
    "core_direct_n": 0,
    "baseline_direct_n": 0,
    "baseline_proxy_n": 0,
    "parallel_direct_n": 0,
    "parallel_proxy_n": 0,
    "critical_consistency_error_n": 0,
    "metadata_mismatch_n": 0,
    "off_topic_core_n": 0,
    "evidence_gap_reasons": []
}
```

建议判定规则：

- `fail`
  - core / baseline / parallel 中存在 `metadata_mismatch` 或 `off_topic` 且未被剔除。
  - 没有任何 baseline scaffold，也没有任何 direct / proxy 方法证据。
  - 候选池主要来自错误 source metadata，无法可信引用。

- `weak`
  - 有可用 baseline 或 parallel，但缺少 topic dataset。
  - `core_direct_n = 0`，但存在可解释的 proxy baseline。
  - 某一关键轴缺失，例如自动驾驶攻击/防御主题缺少 attack/defense 轴。

- `pass`
  - 至少存在一个 direct core 或 direct baseline。
  - 没有 critical consistency error。
  - 数据集、repo、baseline 中至少一类有可信落点。
  - 如果数据集只是 proxy / pretrain，必须在 reason 中明确提示。

不得再使用：

- `has_strong_noise_in_core`
- `strong_noise_cases`
- `strong_noise_in_core_or_baseline_or_parallel`

### Task E：数据集角色分层

建议文件：

- `G:\PaperAgent\apps\api\app\services\agents\evidence_roles.py`

角色定义：

- `topic_dataset`：对象、任务、场景至少两项直接匹配。
- `proxy_dataset`：对象或任务相邻，可用于迁移实验。
- `pretrain_dataset`：COCO、ImageNet、DOTA、KITTI 等通用预训练或常规 benchmark。
- `generic_dataset`：只提供一般视觉能力参考，不应支持 pass。
- `rejected_dataset`：元数据错误或明显无关。

要求：

- summary 表必须同时展示 topic/proxy/pretrain/generic 数量。
- 逐论文审计中每个 dataset 必须显示 role 与 reason。
- `dataset_n` 不得再混淆专属数据集、代理数据集和预训练数据集。

### Task F：Balanced40 重新审计

执行要求：

- 修复后重新生成 Balanced40 的逐论文审计。
- 不允许混合 Re04 partial dump、Re04-fix dump、Re05 old dump。
- 每个 case 必须记录：
  - run_id
  - code commit hash
  - source adapters health
  - cache hit ratio
  - candidate count by role
  - consistency error count

本阶段不要求跑 100 篇。

## 5. 必须覆盖的回归样例

### Case R1：AGN metadata mismatch

输入主题：

```text
面向动态环境的视觉SLAM研究
```

构造候选：

```text
title: A rich bounty of AGN in the 9 square degree Bootes survey: high-z obscured AGN and large-scale structure
abstract/snippet: ORB-LINE-SLAM3 / dynamic visual SLAM related text
proposed_role: baseline
```

期望：

- `consistency_status = metadata_mismatch`
- `role_allowed = false`
- 不得进入 baseline。
- case 不能因为 `AGN` 字符串命中而 fail，而应因为结构化 metadata mismatch 被剔除。

### Case R2：Agnostic Lane Detection 不得误杀

输入主题：

```text
基于深度学习的车道线检测方法研究
```

构造候选：

```text
title: Agnostic Lane Detection
abstract/snippet: lane detection / autonomous driving / road scene
proposed_role: parallel
```

期望：

- `consistency_status = aligned` 或 `proxy`
- 不得因为 `Agnostic` 包含 `AGN` 子串被标噪声。
- 不得导致 case fail。

### Case R3：core 为空不得轻易 pass

输入主题：

```text
基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究
```

候选结构：

- core = 0
- baseline = DAMO-YOLO / HyperDefect-YOLO / YOLOPears 等通用或迁移证据
- dataset = COCO / DOTA / NEU-DET / PCB proxy

期望：

- `status = weak`
- reason 必须说明：缺少接触网绝缘子 direct paper / direct dataset。
- 不得仅因 baseline 数量达到 4 而 pass。

### Case R4：数据集统计一致性

输入主题：

```text
基于深度学习的三维点云补全方法研究
```

候选：

- PCN
- ShapeNet
- KITTI

期望：

- PCN 标为 `topic_dataset` 或 completion benchmark。
- ShapeNet 标为 `pretrain_dataset` 或 `proxy_dataset`。
- KITTI 标为 `proxy_dataset`。
- summary 数量与逐论文审计一致。

### Case R5：攻击/防御轴缺失

输入主题：

```text
面向自动驾驶中多模态融合感知算法的攻击和防御
```

候选结构：

- 有多模态融合感知论文。
- 有自动驾驶感知论文。
- 缺少 attack / defense 直接证据。

期望：

- `status = weak`
- reason 必须显示 `attack_defense_axis_missing`。
- 不得因为 baseline 数量足够而 pass。

## 6. 验收标准

### 6.1 代码验收

必须满足：

- `G:\PaperAgent\apps\api\app\services\agents\eval\__init__.py` 中不存在生产运行用 `STRONG_NOISE_TOKENS`。
- `compute_resource_status()` 不再通过关键词黑名单判定 `fail`。
- 新增 `EvidenceConsistencyAuditor` 或等价模块。
- 新增 dataset role 分层字段。
- 单测覆盖 R1-R5。

不允许通过验收的情况：

- 只是把 `AGN` 改成 `\bAGN\b`。
- 新增另一个名字的黑名单。
- 将所有不确定候选都丢给 LLM，不做结构化规则审计。
- 继续用 `score 0.10` 这类不可解释分数作为主要 UI 信号。

### 6.2 报告验收

必须输出：

- `G:\PaperAgent\Plan\PaperAgent_Re06_完工报告.md`
- `G:\PaperAgent\Plan\PaperAgent_Re06_Balanced40_逐论文审计.md`

报告必须包含：

- `STRONG_NOISE_TOKENS` 移除说明。
- 新一致性审计字段说明。
- R1-R5 回归样例结果。
- Balanced40 新状态分布。
- 至少 5 个抽样 case 的人工解释。
- 源适配器健康情况：arxiv / openalex / core / github / hf / cache。

### 6.3 结果验收

建议阈值：

- Balanced40 `pass + weak >= 90%`。
- core / baseline / parallel 中 `metadata_mismatch_n = 0`。
- 已知正确候选误杀数 = 0，尤其是 `Agnostic Lane Detection`。
- core=0 且只有 generic/proxy 证据的 case 不得标 pass。
- dataset summary 与逐论文审计中的 dataset role 一致。

## 7. 执行顺序

1. 阅读 Re05 报告与逐论文审计，确认当前失败样例。
2. 删除生产代码中的硬编码噪声门禁。
3. 新建证据一致性审计模块。
4. 接入 `compute_resource_status()`。
5. 增加 dataset role 分层。
6. 编写 R1-R5 单测。
7. 重新生成 Balanced40 统一版本审计。
8. 写 Re06 完工报告。

## 8. 给执行者的硬性提醒

这次不要继续“修一个词”的局部补丁。`STRONG_NOISE_TOKENS` 的问题不是 `AGN` 边界没写好，而是本地硬编码黑名单不应该成为毕业选题检索系统的核心评估逻辑。

正确方向是：

- 多查、多留候选。
- 结构化标注候选角色。
- 对明显错配做 title / abstract / source / topic atoms 一致性审计。
- 把 proxy / generic / pretrain 与 direct evidence 分开展示。
- 让用户看到“哪些可信、哪些只是候选、哪些需要补证”，而不是用一个本地词表把结果打死。
