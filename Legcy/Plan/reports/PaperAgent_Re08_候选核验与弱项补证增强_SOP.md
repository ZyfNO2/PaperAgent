# PaperAgent Re08 候选核验与弱项补证增强 SOP

## 0. Re07 审阅结论

Re07 可以视为“评估逻辑修复通过”，但不能视为“资源检索链路最终通过”。

Re07 的有效改进：

- Balanced40 输出从 Re06 的全 weak 异常恢复为 `24 pass / 13 weak / 3 fail`，说明资源可用性分级逻辑已经不再把所有题目压成 weak。
- `axis_task missing` 从 Re06 的全量异常降到约 7.3%，说明题目轴向解析和候选继承有实质改善。
- `metadata_mismatch` 已从全局污染改为候选级隔离，方向正确。
- CSV / MD / summary 已有一致性校验脚本，说明报告生成开始进入可回归阶段。

仍然存在的问题：

- Re07 不是 fresh LLM 全链路重跑，而是基于 Re05 raw dump 再审计，所以只能证明“审计器更合理”，不能证明“检索器已经稳定”。
- 3 个 fail 主要集中在候选元数据不一致、Crossref / OpenAlex 信息不匹配、数据集/工程缺口没有补证。
- 当前仍然缺少候选级核验：论文、数据集、repo、baseline、parallel paper 是否真实、是否同题、是否只是 proxy，都应该有独立 `verification_status`。
- 部分 CSV 字段存在空值风险，例如 `score`、原始 count、baseline/dataset/repo 计数等字段如果保留，就必须真实填充；如果不再使用，就应移除。
- 完工报告、逐论文审计、CSV、summary 之间的校验还不够严格，下一阶段必须把“完工报告也纳入一致性校验”。

## 1. Re08 目标

Re08 的目标不是继续堆新 Agent，而是把资源检索结果变得更可信、更可解释、更容易进入下一阶段。

本阶段要完成：

1. 对候选论文、数据集、repo、baseline、parallel paper 做候选级核验。
2. 对 Re07 中的 fail / weak 样本做定向补证，而不是重新粗暴全量搜索。
3. 对 metadata mismatch 做修复优先，而不是直接丢弃。
4. 引入轻量引用追踪，用 verified baseline / core paper 反向寻找 parallel paper、dataset、repo。
5. 修复报告字段空值、一致性校验不足、状态解释过粗的问题。

## 2. 非目标

本阶段不做：

- 不做完整知识图谱。
- 不做 HumanGate。
- 不做复杂审稿委员会。
- 不做 100 题全量长期评测。
- 不做 UI 大改。
- 不用本地硬编码黑名单过滤噪声论文。

允许做轻量 citation edge，但只用于增强召回和解释，不构建完整 graph。

## 3. 代码修改范围

优先检查并修改以下位置，具体文件名以当前仓库实际结构为准：

- `apps/api/app/services/agents/`  
  新增或整理候选核验、弱项补证、引用追踪相关模块。
- `apps/api/app/services/agents/topic_pipeline.py` 或当前主流程文件  
  接入 Re08 的 verify / repair / enrich 步骤。
- `apps/api/app/services/retrieval/`  
  检查 OpenAlex、arXiv、GitHub、dataset 搜索 adapter 的返回字段。
- `apps/api/app/services/eval/`  
  修复 Re07 评分、状态、计数、CSV 输出字段。
- `scripts/validate_re_report_consistency.py`  
  扩展为校验 summary / CSV / MD / 完工报告四者一致。
- `Plan/`  
  产出 Re08 完工报告、逐论文审计、候选核验 CSV。

## 4. 模块设计

### 4.1 CandidateVerifier

创建模块：

`apps/api/app/services/agents/candidate_verifier.py`

职责：

- 输入一个候选资源和题目结构化信息。
- 判断候选是否真实存在。
- 判断候选是否与当前题目直接相关、间接相关、仅为基础设施、或明显无关。
- 修复 DOI / arXiv / OpenAlex / GitHub 元数据不一致问题。

建议接口：

```python
def verify_candidate(candidate: dict, topic_atoms: dict, role: str) -> dict:
    ...
```

返回字段至少包含：

```json
{
  "candidate_id": "...",
  "role": "core_paper | baseline | parallel_paper | dataset | repo",
  "verification_status": "verified | metadata_repaired | weak_metadata | metadata_mismatch | not_found | duplicate",
  "topic_relation": "direct | proxy | foundation | infrastructure | off_topic",
  "matched_keywords": [],
  "related_keywords": [],
  "missing_keywords": [],
  "metadata_sources": ["arxiv", "openalex", "crossref", "github"],
  "repair_notes": "...",
  "confidence_label": "high | medium | low"
}
```

该模块不应该：

- 用固定论文标题黑名单过滤。
- 因为 Crossref 不匹配就直接判死刑。
- 调用论文生成逻辑。
- 把 `metadata_mismatch` 直接提升为全局 fail。
- 把低相关但真实存在的候选静默删除。

核验优先级：

1. arXiv ID / DOI / URL 精确匹配。
2. arXiv 标题 + 摘要与题目关键词匹配。
3. OpenAlex 标题 + 摘要 + source venue 匹配。
4. Crossref 仅作为 DOI 元数据辅助，不作为唯一真值。
5. GitHub repo 需要 README / paper link / citation / release / stars 中至少一种证据。
6. 数据集需要官网、论文、GitHub、HuggingFace、Kaggle 或明确论文引用中的至少一种来源。

### 4.2 MetadataRepairLoop

创建模块：

`apps/api/app/services/agents/metadata_repair.py`

职责：

- 对 `metadata_mismatch`、`weak_metadata`、`not_found` 候选进行二次查找。
- 优先使用原候选的标题、DOI、arXiv id、URL、repo README 中的 paper title 进行修复。
- 修复成功的候选重新进入候选池，但必须标记 `metadata_repaired`。

该模块不应该：

- 直接把修复后的候选当作 high confidence。
- 在没有来源的情况下编造摘要、年份、作者、链接。
- 覆盖原始候选字段，必须保留 `raw_candidate`。

### 4.3 GapRepairPlanner

创建模块：

`apps/api/app/services/agents/gap_repair_planner.py`

职责：

- 只对 Re07 中的 `fail` 和关键 `weak` 样本做定向补证。
- 根据缺口生成少量高质量查询，而不是重新跑宽泛搜索。

输入：

```json
{
  "topic": "...",
  "topic_atoms": {},
  "status": "weak | fail",
  "gap_reasons": [],
  "current_candidates": []
}
```

输出：

```json
{
  "repair_plan": [
    {
      "gap": "no_dataset_or_data_gap_note",
      "queries": [],
      "tools": ["openalex", "arxiv", "github"],
      "expected_role": "dataset | repo | baseline | parallel_paper"
    }
  ]
}
```

缺口到补证策略：

- `no_dataset_or_data_gap_note`：搜索 `{object} dataset`、`{scenario} dataset`、`{method} {object} dataset`、中文对象词 + 数据集。
- `datasets_present_but_no_topic_dataset`：保留 proxy 数据集，但继续搜索 topic dataset；没有找到时输出“当前可用数据路线”。
- `all_evidence_critical_consistency_error`：先走 MetadataRepairLoop，不允许直接 broad search。
- `scenario_axis_missing`：加场景词、工况词、传感器词进行检索。
- `attack_defense_axis_missing`：加 attack / defense / adversarial / robustness / detection / mitigation 相关查询。
- `core_n=1_but_no_effective_core`：优先找 parallel paper 和 survey，不先找 dataset。

### 4.4 CitationTracker

创建模块：

`apps/api/app/services/agents/citation_tracker.py`

职责：

- 从 verified core paper / baseline paper 中提取 references / cited_by / related works。
- 只保留轻量边，不做完整知识图谱。

输出结构：

```json
{
  "citation_edges": [
    {
      "source_candidate_id": "...",
      "target_title": "...",
      "edge_type": "references | cited_by | official_repo | dataset_used | benchmarked_on",
      "source": "openalex | arxiv | github | paper_text",
      "note": "..."
    }
  ]
}
```

该模块优先用于：

- 从 baseline paper 找官方 repo。
- 从 parallel paper 找使用的数据集。
- 从 dataset paper 找常见 baseline。
- 从 survey / benchmark paper 找同领域 parallel work。

## 5. Prompt 与 Tool Call 规范

### 5.1 CandidateVerifier Prompt

执行者必须使用以下提示词模板，不允许只用 heuristic 替代。

```text
你是工科学位论文选题系统中的候选证据核验 Agent。

任务：
判断一个候选资源是否真实存在，是否与当前题目相关，以及它应该扮演什么角色。

当前题目：
{topic}

题目结构化信息：
{topic_atoms_json}

候选资源：
{candidate_json}

可用工具：
- search_arxiv：当候选含 arXiv id、论文标题、方法名、benchmark 名时调用。
- search_openalex：当需要核验论文标题、摘要、作者、年份、引用关系时调用。
- search_github：当候选是 repo、baseline 工程、官方实现、数据集仓库时调用。
- search_web：当候选是数据集官网、项目主页、非 arXiv 论文或中文数据集时调用。

调用规则：
1. 若候选有 DOI / arXiv / URL，先用精确标识核验。
2. 若精确标识不可靠，用标题短语 + 领域关键词进行二次检索。
3. 若 Crossref 与 OpenAlex / arXiv 冲突，不要直接判错，先尝试修复。
4. 若候选真实但只是基础设施，例如 YOLO、UNet、ORB-SLAM、BERT，应标为 foundation 或 infrastructure。
5. 若候选真实但只间接相关，应保留为 proxy，不要删除。
6. 若候选标题、摘要、关键词都与题目无关，标记 off_topic。

只输出 JSON：
{
  "verification_status": "verified | metadata_repaired | weak_metadata | metadata_mismatch | not_found | duplicate",
  "topic_relation": "direct | proxy | foundation | infrastructure | off_topic",
  "role": "core_paper | baseline | parallel_paper | dataset | repo",
  "matched_keywords": [],
  "related_keywords": [],
  "missing_keywords": [],
  "reason": "",
  "repair_notes": "",
  "recommended_action": "keep | keep_as_proxy | repair | quarantine | deduplicate"
}
```

### 5.2 GapRepairPlanner Prompt

```text
你是科研资源检索补证 Planner。

目标：
不要重新做宽泛搜索，而是根据当前缺口生成 1-3 轮定向检索计划。

当前题目：
{topic}

题目结构化信息：
{topic_atoms_json}

当前缺口：
{gap_reasons_json}

现有候选摘要：
{candidate_summary_json}

可用工具：
- search_arxiv：用于找论文、baseline paper、parallel paper。
- search_openalex：用于找论文元数据、引用、相关论文。
- search_github：用于找 repo、baseline 实现、dataset repo。
- search_web：用于找中文数据集、项目主页、官网、比赛页面。

必须遵守：
1. 每个缺口最多生成 3 个查询。
2. 查询必须同时覆盖中文关键词和英文关键词。
3. 不允许用单一方法词泛搜，例如只搜 "UNet" 或 "YOLO"。
4. 数据集查询必须包含对象词或场景词。
5. baseline 查询必须包含方法词 + 对象词或任务词。
6. parallel paper 查询必须包含对象词 + 任务词 + method/benchmark/defect/detection/segmentation 等限定。

输出 JSON：
{
  "repair_plan": [
    {
      "gap": "",
      "target_role": "dataset | repo | baseline | parallel_paper",
      "queries": [
        {"query": "", "tool": "", "why": ""}
      ]
    }
  ]
}
```

### 5.3 WorkPackage Brainstorm Prompt

```text
你是工科学位论文工作包设计 Agent。

目标：
基于已核验候选资源，提出可毕业、可复现、工作量适中的论文工作包。

输入：
- 题目结构化信息
- verified / metadata_repaired 的 baseline 候选
- direct / proxy 的 parallel paper 候选
- dataset / repo 候选
- 当前缺口和风险

规则：
1. 不允许默认输出“复现 baseline + 加注意力机制”。
2. 每个工作包必须来自至少一个候选证据或明确的数据路线。
3. 如果 baseline 不确定，应输出“从候选中选择 baseline”的建议，而不是编造 baseline。
4. 如果数据集只是 proxy，必须说明 proxy 的风险和可替代路线。
5. 模块建议应来自 parallel paper、repo、survey 或 benchmark 的可观察做法。
6. 输出必须包含为什么能做、缺什么、怎么补。

输出 JSON：
{
  "work_packages": [
    {
      "name": "",
      "baseline_candidates": [],
      "parallel_paper_refs": [],
      "dataset_route": "",
      "repo_route": "",
      "suggested_modules": [],
      "why_graduation_friendly": "",
      "risks": [],
      "next_questions": []
    }
  ]
}
```

## 6. 报告与数据结构修复

### 6.1 CSV 字段必须真实可用

如果 Re08 继续保留以下字段，就必须填充，不允许空列：

- `score`
- `paper_n`
- `dataset_n`
- `repo_n`
- `baseline_n`
- `parallel_n`
- `effective_core_n`
- `effective_baseline_n`
- `effective_parallel_n`
- `verification_verified_n`
- `verification_repaired_n`
- `verification_quarantined_n`

如果 `score` 不再作为评估依据，应改名为：

- `availability_level`
- `evidence_strength_label`
- `gap_flags`

并在报告中明确说明“不使用数值分数做决策”。

### 6.2 一致性校验必须覆盖四类文件

扩展：

`scripts/validate_re_report_consistency.py`

必须校验：

- summary JSON
- 逐论文审计 CSV
- 逐论文审计 MD
- 完工报告 MD

校验项：

- pass / weak / fail 数量一致。
- 每个 case_id 状态一致。
- fail case 列表一致。
- quarantined 计数一致。
- raw count 和 effective count 不为空。
- 完工报告中引用的百分比与源数据一致。

## 7. Re08 测试集

本阶段不跑 100 题，全量成本太高。使用 Balanced40，并对 Re07 fail / weak 做重点回归。

必测样本：

1. `ENG-THESIS-043` 无人机动态目标检测  
   目标：metadata mismatch 不得导致全局 fail，必须能核验或精确说明不可修复原因。

2. `ENG-THESIS-048` 动态视觉 SLAM  
   目标：SLAM / ORB-SLAM / DSO / VINS / visual odometry 等 foundation / baseline 资源必须能被正确归类，不应误判成无效。

3. `ENG-THESIS-075` 混凝土路面裂缝检测  
   目标：能找到至少 1 条直接或 proxy 数据路线，不能只输出“无数据集”。

4. `ENG-THESIS-066` 攻击/防御类样本  
   目标：attack / defense / robustness 轴向不能丢失。

5. `ENG-THESIS-092`、`ENG-THESIS-093`  
   目标：如果没有 topic dataset，允许 weak，但必须列出 proxy dataset、数据路线和补证建议。

6. Re07 中任意 5 个 pass 样本  
   目标：Re08 不得因为更严格核验把正常 pass 大面积降级。

## 8. 验收标准

Re08 通过必须同时满足：

- Balanced40 重新生成 Re08 报告。
- Re07 的 3 个 fail 样本全部经过 MetadataRepairLoop 和 GapRepairPlanner。
- `metadata_mismatch` 不得作为全局 fail 的唯一原因；必须有候选级修复记录。
- baseline 候选中不得存在 `verification_status=not_found` 的项目。
- `verification_status` 覆盖所有 core / baseline / parallel / dataset / repo 候选。
- `score` 字段若存在，不得为空；若不使用，必须删除或改名。
- summary / CSV / MD / 完工报告四者一致性校验通过。
- 不允许新增本地硬编码噪声标题黑名单。
- 不允许用单个关键词规则把所有题目导向 CV 检测路线。
- 完工报告必须给出：
  - Re07 -> Re08 状态变化表。
  - fail / weak 修复详情。
  - 候选核验统计。
  - 仍然无法修复的样本与原因。

## 9. 参考实现与阅读要求

执行前必须阅读：

- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw`
  - 重点看 literature search / verify / tool planning / multi-round retrieval 相关实现。
  - 学习它如何先规划检索，再分 source 拉取，再做候选验证。

- `C:\Users\ZYF\Desktop\Paper\academic-research-skills`
  - 重点看 literature strategist、research workflow、paper discovery、evidence validation 类 skill。
  - 学习它如何定义 search string、inclusion / exclusion、title / abstract screening、literature matrix。

- `G:\PaperAgent\Plan\PaperAgent_Re07_完工报告.md`
- `G:\PaperAgent\Plan\PaperAgent_Re07_Balanced40_逐论文审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re07_Balanced40_逐论文审计.csv`

## 10. 执行顺序

1. 审计 Re07 数据结构和报告字段。
2. 实现 CandidateVerifier。
3. 实现 MetadataRepairLoop。
4. 实现 GapRepairPlanner。
5. 接入 CitationTracker 的最小版本。
6. 修复 CSV / MD / summary / 完工报告一致性校验。
7. 对 Balanced40 执行 Re08。
8. 对 3 fail + 重点 weak 做逐案解释。
9. 输出 Re08 完工报告。

## 11. 最终交付物

必须产出：

- `G:\PaperAgent\Plan\PaperAgent_Re08_完工报告.md`
- `G:\PaperAgent\Plan\PaperAgent_Re08_Balanced40_逐论文审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re08_Balanced40_逐论文审计.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re08_候选核验统计.json`
- `G:\PaperAgent\Plan\PaperAgent_Re08_弱项补证明细.md`

如果执行中发现 `/docs` 与当前 Agent 流程、数据字段、报告结构不一致，需要在完工报告末尾列出“建议同步更新的 docs 章节”，但本阶段不强制改 docs。
