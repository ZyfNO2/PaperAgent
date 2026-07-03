# PaperAgent Re06 Review：评分规则与 Prompt / 流程重写

## 0. 审稿结论

Re06 当前不是“40 个题目都真的 weak”，而是 **评分器与数据流接线错误导致系统性降级**。

我不建议继续沿用 Re06 的全 weak 结论。当前目标是毕业选题资源检索，不是正式论文审稿。现阶段只需要判断：

1. 能不能搜到相关论文。
2. 论文是不是大体搜对。
3. 有没有可选 baseline / 平行论文 / 数据集或工程线索。
4. 能不能进入下一阶段“选方向 + 选 baseline + 工作建议”。

因此，评分逻辑应改为 **宽松的资源可用性分级**，而不是把缺少专属数据集、topic_atoms 缺失、core_direct_n=0 全部压成 weak。

## 1. Re06 输出审计

### 1.1 当前结果不一致

当前文件之间存在冲突：

- `PaperAgent_Re06_完工报告.md` 叙述为：`40 weak / 0 fail`，`pass+weak = 100%`。
- `tmp_re04_eval/balanced40_re06/summary.json` 实际为：`37 weak / 3 fail`，`pass+weak = 92.5%`，`sop_6_3_pass = false`。
- `PaperAgent_Re06_Balanced40_逐论文审计.csv` 也显示：`37 weak / 3 fail`。

这说明 Re06 报告不是同一份数据源生成，验收不能只看 Markdown 叙述。下一轮必须要求 summary/json/csv/md 四者一致。

### 1.2 全 weak 的核心原因

`PaperAgent_Re06_Balanced40_逐论文审计.md` 中候选级统计显示：

- `n_candidates = 424`
- `consistency_status = 419 insufficient_metadata + 5 metadata_mismatch`
- `axis_task = 424 missing`

这不是正常的审稿分布，而是说明 **轴匹配完全失效**。

根因有三层：

1. `parse_topic` prompt 输出的是 `method_terms / task_terms / object_terms`，但 Re06 的 `_build_topic_atoms()` 期望的是 `task / object / method / scenario`。
2. `_build_topic_atoms(synthesis, result)` 虽然签名传了 `result`，但实际只从 `synthesis` 里找 `topic_atoms / parsed_topic / query_matrix`，没有回退到 `result["parsed_topic"]`。
3. Re06 reclassify 使用 Re05 raw dump，但 Re05 raw dump 中 `synthesis.topic_atoms` 没有写入，导致重算时 `topic_atoms = {}`，所有候选自然都是 missing。

因此，**全 weak 不是证据全部不合格，而是评估器没有拿到题目轴**。

### 1.3 当前 Re06 评分过严

当前规则：

```python
elif (
    core_direct_n == 0
    or topic_dataset_n == 0
    or axis_missing_reasons
):
    status = "weak"
```

这条规则不适合当前阶段。

毕业选题 agent 的阶段目标是“资源检索可用”，不是“专属数据集 + 直接 core + 全轴对齐”全部满足。很多合格题目在开题阶段可以先用：

- 通用 baseline：YOLO / U-Net / PointNet++ / ORB-SLAM / BEVFusion。
- 代理数据集：NEU-DET / COCO / DOTA / KITTI / ShapeNet。
- 平行论文：同任务、同对象或相邻工程场景。

这些并不应该自动降为 weak，只应该在报告里标注“需要补专属数据集 / 需要确认实验数据来源”。

## 2. 新评分规则：毕业选题资源可用性分级

### 2.1 分级名称

保留 `pass / weak / fail / blocked`，但含义改为：

- `pass`：资源可进入下一阶段。不是说题目完美，而是“已经能开始选 baseline 和写开题方向”。
- `weak`：资源可用但必须补证。能继续，但下一阶段需要带着明确缺口处理。
- `fail`：当前检索结果不能进入下一阶段，因为前排证据错、baseline 不存在、或候选太少。
- `blocked`：题目解析失败或用户输入不足。

### 2.2 硬阻断条件

以下情况才允许 `fail`：

1. `baseline_n == 0` 且没有任何可解释的 framework / repo / paper 可作为 baseline scaffold。
2. `paper_n < 4` 且没有 repo / dataset / baseline 任何补充证据。
3. `metadata_mismatch` 或 `off_topic` 候选仍留在 `core / baseline / parallel` 前排，且未被 quarantine。
4. 题目解析失败，无法得到 task/object/method 任意两类信息。
5. 检索结果主体明显跨领域，例如 5 条前排中 3 条以上与题目无关。

注意：

- `metadata_mismatch` 应优先做 candidate-level quarantine。
- 只有错误候选无法剔除、或剔除后没有可用证据，才 case-level fail。
- 不能因为没有 `topic_dataset` 就 fail。

### 2.3 宽松通过条件

满足以下条件即可 `pass`：

1. `paper_n >= 8`
2. `baseline_n >= 1`
3. `parallel_n >= 2` 或 `core_n >= 1`
4. `dataset_n + repo_n >= 1`，或存在明确的 `data_gap_note`
5. 前排 `core / baseline / parallel` 中没有未隔离的 `metadata_mismatch`

补充：

- 如果没有专属数据集，但有 proxy/pretrain dataset，仍可 pass，但 reason 必须写：`data_source_gap_needs_confirmation`。
- 如果 baseline 是通用框架，可 pass，但必须标：`baseline_scaffold_not_domain_specific`。
- 如果 core_direct_n 因 topic_atoms 缺失无法计算，不能自动降 weak，应回退使用 EvidenceReview 的 `status / relation_to_topic / matched_terms`。

### 2.4 weak 条件

以下情况标 `weak`：

1. `paper_n >= 4` 且 `baseline_n >= 1`，但 `parallel_n < 2`。
2. 有 baseline scaffold，但没有 dataset / repo / 数据来源说明。
3. 有平行论文，但 baseline 需要人工确认。
4. 有明显方向缺口，例如“攻击/防御”题目只搜到了融合感知，没有 attack/defense 论文。
5. 前排没有错证据，但大部分候选都是 proxy/generic。

### 2.5 建议内部评分表

不要在 UI 上显示一个神秘分数，但内部可以用 100 分辅助分级。

| 维度 | 分值 | 规则 |
|---|---:|---|
| 检索覆盖 | 25 | paper>=8 得10；baseline>=1 得8；parallel>=2 得4；dataset/repo/data_gap_note 得3 |
| 相关性 | 30 | direct core/baseline 得12；EvidenceReview core/candidate>=3 得8；前排无错证据得10 |
| 下一阶段可用性 | 30 | baseline 可选择得10；数据路线明确或缺口明确得8；work suggestion 绑定候选得7；repo/工程线索得5 |
| 报告一致性 | 15 | summary/csv/md 一致得5；source_url/doi/arxiv 可追溯得5；reason 可解释得5 |

分级：

- `pass`：>= 60，且无硬阻断。
- `weak`：40-59，或存在需要补证但不阻断的问题。
- `fail`：< 40，或触发硬阻断。
- `blocked`：题目解析失败。

这套分数只用于自动判定，不要作为前端主视觉展示。前端应展示“Ready / 需补证 / 需修复”和原因。

## 3. 需要修改的代码流程

### 3.1 `parse_topic` 输出 schema 错位

当前问题：

- prompt 输出 `method_terms / task_terms / object_terms`。
- Re06 评估器读取 `task / object / method / scenario`。
- 结果：topic_atoms 永远缺失。

必须改为输出：

```json
{
  "raw_topic": "...",
  "normalized_topic": "...",
  "domain_route": "...",
  "topic_atoms": {
    "task": [{"zh": "裂缝检测", "en": "crack detection", "aliases": ["defect detection", "damage detection"]}],
    "object": [{"zh": "混凝土路面", "en": "concrete pavement", "aliases": ["road pavement", "concrete surface"]}],
    "method": [{"zh": "深度学习", "en": "deep learning", "aliases": ["CNN", "YOLO", "U-Net"]}],
    "scenario": [{"zh": "道路巡检", "en": "road inspection", "aliases": ["infrastructure inspection"]}]
  },
  "query_atoms_en": ["concrete pavement crack detection", "..."],
  "query_atoms_zh": ["混凝土路面 裂缝检测", "..."]
}
```

兼容要求：

- 继续保留旧字段 `method_terms / task_terms / object_terms`，但它们只作为展示字段。
- 评估和检索必须使用 `topic_atoms`。
- `topic_atoms` 中必须包含英文 canonical atom，否则英文论文无法匹配中文题目。

### 3.2 `_build_topic_atoms()` 必须修

当前问题：

```python
def _build_topic_atoms(synthesis, result=None):
    if not isinstance(synthesis, dict):
        return {}
    ...
```

它完全没有用 `result["parsed_topic"]`。这直接导致 reclassify 旧 raw dump 时拿不到 parsed topic。

必须改为按以下顺序读取：

1. `result["parsed_topic"]["topic_atoms"]`
2. `result["query_matrix"]["parsed_topic"]`
3. `synthesis["topic_atoms"]`
4. `synthesis["parsed_topic"]["topic_atoms"]`
5. 兼容旧字段：从 `method_terms / task_terms / object_terms / domain_route` 构造 topic_atoms。

如果仍拿不到：

- `axis_status = "not_evaluable"`
- 不得把所有候选自动判为 insufficient_metadata。
- 不得因此把 case 自动降 weak。

### 3.3 `synthesize_v2` 必须把 topic_atoms 写入 synthesis

当前问题：

- `AgentResultRe02` 顶层有 `parsed_topic`。
- 但 Re06 re-audit 只看 `synthesis`。
- synthesis 里没有 `topic_atoms`。

必须在 `synthesize_v2()` 返回值中写入：

```python
synthesis["topic_atoms"] = parsed_topic["topic_atoms"]
synthesis["parsed_topic"] = parsed_topic
```

同时要求 raw dump 中保留：

```json
{
  "parsed_topic": {...},
  "synthesis": {
    "topic_atoms": {...},
    "paper_groups": {...},
    "candidate_pool": {...}
  }
}
```

### 3.4 `EvidenceConsistencyAuditor` 不能只做英文 substring

当前 `_axis_match()` 只做：

```python
direct_hits = [a for a in atoms if a in hs]
proxy_hits = [a for a in atoms if any(len(t) >= 4 and t in hs for t in a.split())]
```

这对中文题目 + 英文论文天然不友好。

必须改成：

- 每个 atom 带 `zh/en/aliases`。
- 轴匹配使用英文 canonical + aliases。
- 中文 title / 中文摘要时再使用 zh。
- 对 `YOLOv5 / YOLO / YOLOv8` 这类框架做 normalized family match。
- 对 `crack / damage / defect`、`segmentation / detection / classification` 做任务同义词组。

不允许：

- 新增本地噪声黑名单。
- 用单个 if `"检测" in topic` 将题目全部归到 CV detection。
- 用 substring 命中当成最终 truth。

### 3.5 `metadata_mismatch` 必须候选级剔除，不应直接 case fail

当前 Re06：

- 只要 core/baseline/parallel 中有 metadata_mismatch，就 `status = fail`。

这仍然过严。

正确逻辑：

1. 对 mismatch candidate 标记 `quarantined`。
2. 从 core/baseline/parallel 的有效计数中排除。
3. 重新计算有效 baseline/core/parallel。
4. 只有剔除后资源不足，才 case fail。

这样可以避免一个 Crossref 脏候选拖垮整题。

### 3.6 报告一致性校验必须加入

每次生成 Re06 / Re07 报告时必须校验：

- `summary.json.by_status`
- `Plan/*逐论文审计.csv` 的 status group
- `Plan/*逐论文审计.md` 的总览表
- `完工报告.md` 的叙述

四者必须一致；不一致直接验收失败。

## 4. 需要重写的 Agent 职位与 Prompt

### 4.1 Topic Parser Prompt

替换目标文件：

- `G:\PaperAgent\apps\api\app\services\agents\prompts\parse_topic.py`

新职责：

- 把中文题目拆成可检索、可审计的双语 topic atoms。
- 不做检索。
- 不生成论文候选。

必须使用以下系统 prompt 核心要求：

```text
You are the Topic Parser for an engineering thesis topic-selection agent.
Your job is to convert a raw Chinese or English thesis title into bilingual,
searchable, auditable topic atoms.

Return STRICT JSON only.

You MUST output:
1. topic_atoms.task
2. topic_atoms.object
3. topic_atoms.method
4. topic_atoms.scenario

Each atom MUST include:
- zh: Chinese phrase if available
- en: academic English phrase
- aliases: 2-5 English synonyms or benchmark terms

Rules:
- Do not search the web.
- Do not invent papers, datasets, repos, or baselines.
- Do not output generic atoms alone, such as "deep learning", "machine learning",
  "detection", "research", "system".
- If the title is "基于深度学习的混凝土路面裂缝检测研究",
  object is "concrete pavement", task is "crack detection", method is
  "deep learning", scenario is "road inspection / civil infrastructure".
- query_atoms_en must be 3-6 short English search phrases, each 3-6 words.
- query_atoms_zh must mirror the English atoms.

Output schema:
{
  "raw_topic": "...",
  "normalized_topic": "...",
  "domain_route": "...",
  "domain_confidence": 0.0,
  "topic_atoms": {
    "task": [{"zh": "...", "en": "...", "aliases": ["..."]}],
    "object": [{"zh": "...", "en": "...", "aliases": ["..."]}],
    "method": [{"zh": "...", "en": "...", "aliases": ["..."]}],
    "scenario": [{"zh": "...", "en": "...", "aliases": ["..."]}]
  },
  "method_terms": [],
  "task_terms": [],
  "object_terms": [],
  "query_atoms_en": [],
  "query_atoms_zh": [],
  "needs_clarification": [],
  "site_hints": []
}
```

参考：

- AutoResearchClaw `search_strategy` 要求至少 3 类策略、8 个短 query，覆盖 core topic / methods / benchmarks / applications。
- academic-research-skills `Literature Strategist Agent` 要求先识别 primary concepts、secondary concepts、discipline terminology，再构造检索式。

### 4.2 Search Planner Prompt

替换目标文件：

- `G:\PaperAgent\apps\api\app\services\agents\prompts\plan_tools.py`

新职责：

- 依据 topic_atoms 设计多轮检索。
- 不做论文筛选。
- 不把 paper title 或 repo name 硬塞成第一轮 query。

必须加入：

```text
Round 1: core topic recall
- method + object + task
- object + task
- method + task

Round 2: benchmark/dataset search
- object + dataset
- task + benchmark
- method + benchmark

Round 3: baseline/framework search
- method family + task
- canonical framework + object
- survey / review query

Round 4: repo search
- github query <= 4 words
- method + object
- framework + task

Round 5: gap repair
- generated only after seeing Round 1-4 gaps
- must target missing axis: dataset / repo / baseline / attack-defense / scenario
```

每个 call 必须包含：

```json
{
  "tool": "search_arxiv|search_openalex|search_crossref|search_github|search_huggingface",
  "query": "...",
  "target_role": "core_paper|baseline|parallel|dataset|repo|survey|gap_repair",
  "why_call": "...",
  "expected_output": "paper|dataset|repo",
  "axis_target": ["task", "object", "method", "scenario"]
}
```

MCP / tool call 规范：

- arXiv：用于论文与 baseline 搜索，优先 method/object/task query。
- OpenAlex：用于补 DOI、引用量、跨源验证。
- Crossref：只能做元数据补全，不允许作为唯一真实性来源。
- GitHub：用于 repo / official implementation，不允许长 query。
- HuggingFace：用于 dataset，但必须标 dataset role。
- Cache：只做补充，不得覆盖新鲜搜索结果。

### 4.3 Evidence Review Prompt

替换目标：

- `G:\PaperAgent\apps\api\app\services\agents\prompts\synthesize.py` 中的 `EVIDENCE_REVIEW_SYSTEM`

新职责：

- 不是“严格审稿拒绝”，而是“多给候选、分层标注”。
- 当前阶段只要能解释关系，就保留到 candidate / long_tail。

必须输出：

```json
{
  "candidate_id": "...",
  "evidence_type": "paper|dataset|repo|survey|unknown",
  "role_hint": "core|baseline|parallel|dataset|repo|reference|long_tail|rejected",
  "status": "core|candidate|long_tail|needs_manual|rejected",
  "axis_hit": {
    "task": "direct|proxy|missing",
    "object": "direct|proxy|missing",
    "method": "direct|proxy|missing",
    "scenario": "direct|proxy|missing"
  },
  "matched_terms": [],
  "missing_terms": [],
  "relation_to_topic": "baseline|parallel|module|dataset|repo|survey|background|weak_related|unrelated",
  "exists_verdict": "exists|likely_exists|metadata_mismatch|not_found",
  "next_stage_use": "baseline_candidate|parallel_reference|dataset_candidate|repo_candidate|background_only|do_not_use",
  "reason": "..."
}
```

硬规则：

- 不要因为 weak match 就 rejected。
- 跨领域错证据必须 rejected 或 quarantined。
- baseline 可以是通用框架，但必须写 `baseline_scaffold`。
- 平行论文允许对象不同，只要 task/method 相关。
- 数据集必须分 topic/proxy/pretrain/generic。

### 4.4 Synthesis Prompt

替换目标：

- `USER_TEMPLATE_SYNTHESIZE_V2`
- `SYNTHESIZE_SYSTEM`

新职责：

- 输出下一阶段可用的方向。
- 不要把“无专属数据集”当成不能继续。
- 不要生成默认“加注意力机制”。

必须新增输出：

```json
{
  "topic_atoms": {...},
  "readiness": {
    "can_enter_next_stage": true,
    "level": "ready|needs_supplement|repair_required",
    "why": "..."
  },
  "baseline_selection": [
    {
      "candidate_id": "...",
      "baseline_type": "domain_direct|framework_scaffold|proxy_baseline",
      "why": "...",
      "risk": "..."
    }
  ],
  "data_route": {
    "topic_dataset": [],
    "proxy_dataset": [],
    "pretrain_dataset": [],
    "gap_note": "..."
  },
  "work_suggestions": [
    {
      "baseline_candidate_id": "...",
      "parallel_candidate_ids": ["..."],
      "dataset_candidate_ids": ["..."],
      "suggestion": "..."
    }
  ]
}
```

硬规则：

- work_suggestions 必须绑定 candidate_id。
- 不允许输出固定模板“复现 baseline + 加注意力机制”。
- 创新模块必须来自 parallel paper 或 candidate_pool 中真实出现的方法。
- 如果没有足够模块，只输出“下一阶段先补 parallel paper”。

### 4.5 Low-Bar Reviewer Prompt

新定位：

- 当前不是委员会严格审稿。
- 它只回答“是否能进入下一阶段”。

判定规则：

```text
pass:
- 有 baseline 或 baseline scaffold
- 有至少 8 篇 paper 或 4 篇强相关 paper
- 没有未隔离的错证据
- 有数据路线或明确数据缺口

needs_revision:
- baseline 有但需要人工确认
- 数据集缺失但论文和 repo 足够
- 平行论文不足

stop:
- 没有 baseline
- 前排错证据无法剔除
- 题目解析失败
- 检索候选太少
```

输出：

```json
{
  "review_verdict": "pass|needs_revision|stop",
  "can_continue_to_next_stage": true,
  "blocking_issues": [],
  "supplement_needed": [],
  "summary": "..."
}
```

## 5. Re07 执行 SOP

### 5.1 目标

Re07 不是继续扩大检索，而是修正 Re06 的评估与数据流，让已有结果能被正确分级。

交付目标：

1. 修复 topic_atoms 数据流。
2. 重写评分规则。
3. 重写 Topic Parser / Search Planner / Evidence Review / Synthesis / Low-Bar Reviewer prompt。
4. 重新 reclassify Balanced40。
5. 判断哪些题目是真的 weak，哪些应该是 pass。

### 5.2 必做任务

#### Task A：修复 topic_atoms 数据流

文件：

- `apps/api/app/services/agents/prompts/parse_topic.py`
- `apps/api/app/services/agents/eval/__init__.py`
- `apps/api/app/services/agents/research_agent.py`
- `apps/api/app/services/agents/re04_entry.py`

验收：

- 新 raw dump 顶层 `parsed_topic.topic_atoms` 存在。
- `synthesis.topic_atoms` 存在。
- `_build_topic_atoms()` 能从 result 顶层 parsed_topic 回退。
- Balanced40 reclassify 后不再出现 `axis_task = 424 missing`。

#### Task B：替换评分规则

文件：

- `apps/api/app/services/agents/eval/__init__.py`

要求：

- 实现 2.1-2.5 的新分级。
- `topic_dataset_n == 0` 不能单独导致 weak。
- `core_direct_n == 0` 不能在 topic_atoms 缺失时导致 weak。
- `metadata_mismatch` 先 quarantine，再重算有效候选。

验收：

- Re06 中明显可进入下一阶段的题目应恢复为 pass。
- `ENG-THESIS-060` 车道线检测不应 fail。
- `ENG-THESIS-093` 接触网绝缘子可以 weak，因为 core/topic dataset 确实不足。
- `ENG-THESIS-018` 点云补全如果 PCN / ShapeNet / completion baselines 被识别，应至少 pass 或 high weak。

#### Task C：Prompt 全量重写

文件：

- `prompts/parse_topic.py`
- `prompts/plan_tools.py`
- `prompts/synthesize.py`
- `prompts/evidence_consistency_review.md`
- `low_bar_reviewer.py` 或其 prompt 来源

验收：

- 每个 prompt 都明确自己的职位边界。
- 每个 prompt 都禁止生成不存在的候选。
- 每个 prompt 都要求 candidate_id 绑定。
- Search Planner 明确 tool call / MCP 调用时机。
- Synthesis 不再默认输出“加注意力机制”。

#### Task D：报告一致性校验

新增脚本：

- `apps/api/scripts/validate_re_report_consistency.py`

功能：

- 读取 summary.json、case csv、md 总览、完工报告。
- 校验 status 分布一致。
- 校验 n_total 一致。
- 校验 `sop_pass` 与报告叙述一致。

验收：

- 不一致直接退出非 0。
- Re07 完工报告必须附校验结果。

#### Task E：Balanced40 复核

要求：

- 可以先不 fresh LLM run，但必须用修复后的 topic_atoms 回填旧 raw dump。
- 如果旧 raw dump 顶层有 parsed_topic，就用它重算。
- 如果旧 raw dump 没有 parsed_topic，标记 `not_evaluable`，不要强行 weak。

输出：

- `Plan/PaperAgent_Re07_Balanced40_逐论文审计.md`
- `Plan/PaperAgent_Re07_Balanced40_逐论文审计.csv`
- `Plan/PaperAgent_Re07_完工报告.md`

### 5.3 验收标准

必须满足：

- Balanced40 不允许全 weak，除非逐 case 证明每一例都不满足进入下一阶段条件。
- `axis_task missing` 比例必须显著下降，目标 < 30%。
- `insufficient_metadata` 不得超过候选总数 40%。
- summary/json/csv/md 状态分布一致。
- 至少 10 个 case 给出人工抽样解释，其中包括：
  - ENG-THESIS-018
  - ENG-THESIS-048
  - ENG-THESIS-060
  - ENG-THESIS-075
  - ENG-THESIS-092
  - ENG-THESIS-093

建议通过分布：

- pass：应出现一批，不要求多数。
- weak：允许存在，尤其是专属数据集缺失的题目。
- fail：只允许真实错证据或资源严重不足。

## 6. 给执行者的硬性提醒

本轮不要继续把“严格”当成质量。用户当前要的是毕业选题 agent 的资源检索能力：**搜得到、搜得对、能进入下一阶段**。

所以：

- 不要全 weak。
- 不要全 pass。
- 不要用专属数据集缺失一票否决。
- 不要用 topic_atoms 缺失惩罚候选。
- 不要用硬编码黑名单。
- 不要让一个脏 Crossref 候选拖垮整题。
- 必须把每个 agent 职位、prompt 输入输出、工具调用边界写清楚。

正确的 Re07 应该让系统开始像一个“宽松但诚实的毕业选题助手”：相关的放前面，不确定的放候选，错误的隔离，缺口明确告诉用户。
